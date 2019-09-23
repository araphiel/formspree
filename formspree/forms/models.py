import hmac
import uuid
import random
import hashlib
import inspect
import datetime
import traceback

import pystache

from flask import url_for, render_template, g
from sqlalchemy import func, DDL, Index, event
from sqlalchemy.sql import text
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.exc import IntegrityError
from premailer import transform

from formspree import settings
from formspree.app_globals import DB, celery, spam_serializer
from formspree.email_templates import render_email
from formspree.utils import send_email, next_url, is_valid_email, referrer_to_path
from .helpers import (
    HASH,
    HASHIDS_CODEC,
    KEYS_NOT_STORED,
    KEYS_EXCLUDED_FROM_EMAIL,
    store_first_submission,
    fetch_first_submission,
    get_replyto,
    get_monthly_counter,
    increase_monthly_counter,
)


class Form(DB.Model):
    __tablename__ = "forms"

    id = DB.Column(DB.Integer, primary_key=True)
    hash = DB.Column(DB.String(32), unique=True)
    name = DB.Column(DB.String)
    email = DB.Column(DB.String(120), index=True)
    host = DB.Column(DB.String(300), index=True)
    sitewide = DB.Column(DB.Boolean)
    disabled = DB.Column(DB.Boolean)
    confirm_sent = DB.Column(DB.Boolean)
    confirmed = DB.Column(DB.Boolean)
    counter = DB.Column(DB.Integer)
    apikey = DB.Column(DB.String)
    owner_id = DB.Column(DB.Integer, DB.ForeignKey("users.id"), index=True)
    captcha_disabled = DB.Column(DB.Boolean)
    uses_ajax = DB.Column(DB.Boolean)
    disable_email = DB.Column(DB.Boolean)
    disable_storage = DB.Column(DB.Boolean)
    created_at = DB.Column(DB.DateTime, default=DB.func.now())

    Index("ix_forms_normalized_host", func.normalize_host(host))
    Index("ix_forms_normalized_email", func.normalize_email(email))

    # this property is basically useless. use .controllers
    owner = DB.relationship("User")  # direct owner, defined by 'owner_id'

    template = DB.relationship("EmailTemplate", uselist=False, back_populates="form")
    submissions = DB.relationship(
        "Submission",
        backref="form",
        lazy="dynamic",
        order_by=lambda: Submission.id.desc(),
    )
    plugins = DB.relationship("Plugin", backref="form", lazy="dynamic")
    routing_rules = DB.relationship("RoutingRule", backref="form", lazy="dynamic")

    """
    When the form is created by a spontaneous submission, it is added to
    the table with a `host`, an `email` and a `hash` made of these two
    (+ a secret nonce).

    `hash` is UNIQUE because it is used to query these spontaneous forms
    when the form is going to be confirmed and whenever a new submission arrives.

    When a registered user POSTs to /forms, a new form is added to the table
    with an `email` (provided by the user) and an `owner_id`. Later, when this
    form receives its first submission and confirmation, `host` is added, so
    we can ensure that no one will submit to this same form from another host.

    `hash` is never added to these forms, because they could conflict with other
    forms, created by the spontaneous process, with the same email and host. So
    for these forms a different confirmation method is used (see below).
    """

    STATUS_SUBMISSION_ENQUEUED = "ENQUEUED"
    STATUS_SUBMISSION_EMPTY = "EMPTY_FORM"
    STATUS_REPLYTO_ERROR = "REPLYTO_ERROR"

    STATUS_CONFIRMATION_SENT = "CONFIRMATION_SENT"
    STATUS_CONFIRMATION_DUPLICATED = "CONFIRMATION_DUPLICATED"
    STATUS_CONFIRMATION_FAILED = "CONFIRMATION_FAILED"

    SUBJECT_ACTIVATION = "Action Required: Activate %s on %s"

    def __init__(
        self, email, confirmed, host=None, owner=None, name=None, normalize=False
    ):
        if host is not None:
            self.hash = HASH(email, host)
        elif owner:
            self.owner_id = owner.id
        else:
            raise Exception(
                "cannot create form without a host or an owner. provide one of these."
            )

        self.created_at = datetime.datetime.utcnow()
        self.email = email
        self.name = name

        if confirmed:
            self.confirmed = True
        else:
            self.confirm_sent = False
            self.confirmed = False

        self.counter = 0
        self.disabled = False
        self.captcha_disabled = False

        if normalize:
            self.host = func.normalize_host(host)
            DB.session.add(self)
            DB.session.flush()
        else:
            # forms created with a host (from endpoint.py) should
            # be normalized. the non-normalized version is supported
            # for testing backward-compatibility cases.
            self.host = host

    def __repr__(self):
        confirmed = "[✓]" if self.confirmed else "[ ]"

        if self.name:
            return "<Form %s email=%s name=%s %s>" % (
                self.id,
                self.email,
                self.name,
                confirmed,
            )
        return "<Form %s email=%s host=%s %s>" % (
            self.id,
            self.email,
            self.host,
            confirmed,
        )

    @property
    def controllers(self):
        from formspree.users.models import User, Email

        by_email = (
            DB.session.query(User)
            .join(Email, User.id == Email.owner_id)
            .join(Form, func.normalize_email(Form.email) == Email.address)
            .filter(Form.id == self.id)
        )
        by_creation = (
            DB.session.query(User)
            .join(Form, User.id == Form.owner_id)
            .filter(Form.id == self.id)
        )
        return by_email.union(by_creation)

    @property
    def features(self):
        return set.union(*[set(cont.features) for cont in self.controllers])

    @property
    def apikey_readonly(self):
        return (
            hashlib.new("ripemd160", self.apikey.encode("utf-8")).hexdigest()
            if self.apikey
            else None
        )

    def controlled_by(self, user):
        for cont in self.controllers:
            if cont.id == user.id:
                return True
        return False

    def has_feature(self, feature):
        c = [user for user in self.controllers if user.has_feature(feature)]
        return len(c) > 0

    @classmethod
    def get_with(cls, email=None, host=None, hashid=None):
        if hashid:
            try:
                id = HASHIDS_CODEC.decode(hashid)[0]
                return cls.query.get(id)
            except IndexError:
                return None
        else:
            # see https://twist.com/a/66930/inbox/t/660857 for what
            # we're trying to do here.
            return (
                DB.session.query(cls)
                .from_statement(
                    text(
                        "SELECT * FROM ( "
                        "  SELECT *, 0 AS priority FROM forms "
                        "  WHERE email = :email AND host = :host AND confirmed "
                        "UNION ALL "
                        "  SELECT *, 1 AS priority FROM forms "
                        "  WHERE email = :email AND normalize_host(host) = normalize_host(:host)"
                        ")x "
                        "ORDER BY confirmed DESC, priority, char_length(host)"
                        "LIMIT 1 "
                    )
                )
                .params(email=email, host=host)
                .first()
            )

    def reset_apikey(self):
        self.apikey = str(uuid.uuid1()).replace("-", "")

    def serialize(self):
        return {
            "name": self.name,
            "sitewide": self.sitewide,
            "hashid": self.hashid,
            "hash": self.hash,
            "counter": self.counter,
            "email": self.email,
            "host": self.host,
            "apikey": self.apikey,
            "apikey_readonly": self.apikey_readonly,
            "template": self.template.serialize() if self.template else None,
            "plugins": [p.serialize() for p in self.plugins],
            "routing_rules": [r.serialize() for r in self.routing_rules],
            "features": {f: True for f in self.features},
            "confirm_sent": self.confirm_sent,
            "confirmed": self.confirmed,
            "disabled": self.disabled,
            "captcha_disabled": self.captcha_disabled,
            "disable_email": self.disable_email,
            "disable_storage": self.disable_storage,
            "api_enabled": bool(self.apikey),
            "is_public": bool(self.hash),
            "url": "{S}/{E}".format(S=settings.SERVICE_URL, E=self.hashid),
            "created_at": self.created_at,
        }

    def submissions_with_fields(
        self,
        since=None,
        limit=None,
        with_ids=True,
        with_errors=False,
        filter={"spam": False},
    ):
        """
        Fetch all submissions, extract all fields names from every submission
        into a single fields list, excluding the KEYS_NOT_STORED values, because
        they are worthless.
        Add the special 'date' field to every submission entry, based on
        .submitted_at, and use this as the first field on the fields array.
        """

        filter_ops = []
        if since:
            filter_ops += [Submission.submitted_at >= since]
        if "spam" in filter.keys():
            filter_ops += (
                [Submission.spam == True]
                if filter["spam"]
                else [Submission.spam.isnot(True)]
            )

        query = self.submissions.filter(*filter_ops).limit(limit)

        submissions = []
        sub_fields = set()
        for s in query:
            data = s.data.copy()
            sub_fields.update(data.keys())
            data["_date"] = s.submitted_at.isoformat()
            if with_ids:
                data["_id"] = s.id
            for k in KEYS_NOT_STORED:
                data.pop(k, None)
            if with_errors and s.errors is not None:
                errors = [e.get("message") for e in s.errors if e.get("message")]
                data["_errors"] = ", ".join(errors)
            submissions.append(data)

        fields = []
        if with_ids:
            fields += ["_id"]
        fields += ["_date"]
        fields = fields + sorted(sub_fields - KEYS_NOT_STORED)
        if with_errors:
            fields += ["_errors"]

        return submissions, fields

    def submit(self, data, keys, referrer):
        """
        Submits a form.
        Ensure data is well-formed. Create a new submission. Dispatch to worker to process submission.
        """

        keys = [k for k in keys if k not in KEYS_EXCLUDED_FROM_EMAIL]
        next = next_url(referrer, data.get("_next"))

        # prevent submitting empty form
        if not any(data.values()):
            return {"code": Form.STATUS_SUBMISSION_EMPTY}

        # return a fake success for spam
        if data.get("_gotcha", None):
            g.log.info("Submission rejected.", gotcha=data.get("_gotcha"))
            return {"code": Form.STATUS_SUBMISSION_ENQUEUED, "next": next}

        # validate reply_to, if it is not a valid email address, reject
        reply_to = get_replyto(data)
        if reply_to and not is_valid_email(reply_to):
            g.log.info("Submission rejected. Reply-To is invalid.", reply_to=reply_to)
            return {
                "code": Form.STATUS_REPLYTO_ERROR,
                "address": reply_to,
                "referrer": referrer,
            }

        # the Submission object
        submission = Submission(self.id)
        submission.data = {key: data[key] for key in data if key not in KEYS_NOT_STORED}
        submission.host = referrer
        DB.session.add(submission)
        DB.session.commit()
        process_and_commit_submission.delay(submission.id, list(keys))
        g.log.info(
            "Submission enqueued.",
            form_id=self.id,
            submission_id=submission.id,
            email=self.email,
        )
        return {"code": Form.STATUS_SUBMISSION_ENQUEUED, "next": next}

    def update_counters(self):
        # increase the monthly counter
        monthly_counter = increase_monthly_counter(self.id)

        # increment the forms global counter
        self.counter = Form.counter + 1

        return monthly_counter

    def get_monthly_counter(self):
        return get_monthly_counter(self.id)

    def delete_over_archive_limit(self):
        # For free users, sometimes we'll delete all archived submissions over the limit
        DB.session.query(Submission.id).from_statement(
            text(
                "WITH n_to_delete AS ( "
                "  SELECT CASE WHEN c > :keep THEN c - :keep ELSE 0 END AS n FROM ( "
                "    SELECT count(*) AS c FROM submissions "
                "    WHERE form_id = :form_id "
                "  )x "
                "), ids_to_delete AS ( "
                "  SELECT id FROM submissions "
                "  WHERE form_id = :form_id "
                "  ORDER BY submitted_at "
                "  LIMIT (SELECT n FROM n_to_delete) "
                ") "
                "DELETE FROM submissions WHERE id in (SELECT id FROM ids_to_delete) "
                "RETURNING id "
            )
        ).params(keep=settings.ARCHIVED_SUBMISSIONS_LIMIT, form_id=self.id).all()

    def send_confirmation(self, store_data=None, sorted_keys=[]):
        """
        Helper that actually creates confirmation nonce
        and sends the email to associated email. Renders
        different templates depending on the result
        """

        g.log = g.log.new(form=self.id, to=self.email, host=self.host)
        g.log.debug("Confirmation.")
        if not self.host:
            g.log.error("Trying to send confirmation without host.")

        if self.confirm_sent:
            g.log.debug("Previously sent.")
            return {"code": Form.STATUS_CONFIRMATION_DUPLICATED}

        # the nonce for email confirmation will be the hash
        # (we only send confirmation emails for legacy forms created
        #  automatically now)
        nonce = self.hash
        link = url_for("confirm_email", nonce=nonce, _external=True)

        def render_content(ext):
            if store_data:
                store_first_submission(nonce, store_data, sorted_keys)

            params = dict(
                email=self.email, host=referrer_to_path(self.host), nonce_link=link
            )
            if ext == "html":
                return render_email("confirm.html", **params)
            elif ext == "txt":
                return render_template("email/confirm.txt", **params)

        DB.session.add(self)
        try:
            DB.session.flush()
        except IntegrityError:
            return {"code": Form.STATUS_CONFIRMATION_DUPLICATED}

        result = send_email(
            to=self.email,
            subject=self.SUBJECT_ACTIVATION % (settings.SERVICE_NAME, self.host),
            text=render_content("txt"),
            html=render_content("html"),
            sender=settings.DEFAULT_SENDER,
            headers={
                "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
                "List-Unsubscribe": "<"
                + url_for(
                    "unconfirm_form",
                    form_id=self.id,
                    digest=self.unconfirm_digest(),
                    _external=True,
                )
                + ">",
            },
        )
        g.log.debug("Confirmation email queued.")

        if not result[0]:
            return {"code": Form.STATUS_CONFIRMATION_FAILED}

        self.confirm_sent = True
        DB.session.add(self)
        DB.session.commit()

        return {"code": Form.STATUS_CONFIRMATION_SENT}

    @classmethod
    def confirm(cls, nonce):
        # normal form, nonce is HASH(email, host)
        form = cls.query.filter_by(hash=nonce).first()

        if form:
            form.confirmed = True
            DB.session.add(form)
            DB.session.commit()

            stored_data, sorted_keys = fetch_first_submission(nonce)
            if stored_data:
                # NOTE: form.host may be null. This is only used for the subject field
                form.submit(stored_data, sorted_keys, form.host)

            return form

    @property
    def hashid(self):
        # A unique identifier for the form that maps to its id,
        # but doesn't seem like a sequential integer
        try:
            return self._hashid
        except AttributeError:
            if not self.id:
                raise Exception("this form doesn't have an id yet, commit it first.")
            self._hashid = HASHIDS_CODEC.encode(self.id)
        return self._hashid

    def unconfirm_digest(self):
        return hmac.new(
            settings.NONCE_SECRET,
            "id={}".format(self.id).encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def unconfirm_with_digest(self, digest):
        if (
            hmac.new(
                settings.NONCE_SECRET,
                "id={}".format(self.id).encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()
            != digest
        ):
            return False

        self.confirmed = False
        DB.session.add(self)
        DB.session.commit()
        return True


drop_normalize_host = "DROP FUNCTION normalize_host(text)"
create_normalize_host = """
CREATE FUNCTION normalize_host(host text) RETURNS text AS $$
  BEGIN
    host = CASE WHEN left(host, 4) = 'www.'
      THEN substring(host from 5)
      ELSE host
    END;

    host = CASE WHEN right(host, 11) = '/index.html'
      THEN substring(host from 0 for char_length(host) - 10)
      ELSE host
    END;

    host = CASE WHEN right(host, 5) = '.html'
      THEN substring(host from 0 for char_length(host) - 4)
      ELSE host
    END;

    RETURN rtrim(host, '/');
  END;
$$ LANGUAGE plpgsql IMMUTABLE RETURNS NULL ON NULL INPUT;"""
event.listen(Form.metadata, "before_create", DDL(create_normalize_host))
event.listen(Form.metadata, "after_drop", DDL(drop_normalize_host))


drop_normalize_email = "DROP FUNCTION normalize_email(text)"
create_normalize_email = """
CREATE FUNCTION normalize_email(email text) RETURNS text AS $$
  BEGIN
    RETURN regexp_replace(email, '\+[^@]*@', '@');
  END;
$$ LANGUAGE plpgsql IMMUTABLE RETURNS NULL ON NULL INPUT;"""
event.listen(Form.metadata, "before_create", DDL(create_normalize_email))
event.listen(Form.metadata, "after_drop", DDL(drop_normalize_email))


class EmailTemplate(DB.Model):
    __tablename__ = "email_templates"

    id = DB.Column(DB.Integer, primary_key=True)
    form_id = DB.Column(
        DB.Integer, DB.ForeignKey("forms.id"), unique=True, nullable=False
    )
    subject = DB.Column(DB.Text)
    from_name = DB.Column(DB.Text)
    style = DB.Column(DB.Text)
    body = DB.Column(DB.Text)

    form = DB.relationship("Form", back_populates="template")

    def __init__(self, form_id):
        self.submitted_at = datetime.datetime.utcnow()
        self.form_id = form_id

    def __repr__(self):
        return "<Email Template %s, form=%s>" % (
            self.id or "with an id to be assigned",
            self.form_id,
        )

    @classmethod
    def make_preview(
        cls,
        style,
        body,
        from_name="Formspree Team",
        subject="New submission from {{ _host }}",
    ):
        t = cls(0)
        t.from_name = from_name
        t.subject = subject
        t.style = style
        t.body = body
        return t.render_with_sample_context()

    @classmethod
    def make_mustache_context(cls, data, host, keys, now, unconfirm_url):
        context = data.copy()
        context.update(
            {
                "_fields": [
                    {"_name": f, "_value": data[f]} for f in keys if f in data.keys()
                ],
                "_time": now,
                "_host": host,
                "_unsubscribe": unconfirm_url,
            }
        )
        return context

    def serialize(self):
        result = {}
        if self.from_name:
            result["from_name"] = self.from_name
        if self.subject:
            result["subject"] = self.subject
        if self.style:
            result["style"] = self.style
        if self.body:
            result["body"] = self.body
        return result

    def render_body(self, data, unconfirm_url):
        html = pystache.render("<style>" + self.style + "</style>" + self.body, data)
        inlined = transform(html)
        if unconfirm_url not in inlined:
            suffix = """<table width="100%"><tr><td>If you no longer wish to receive these emails <a href="{unconfirm_url}">click here to unsubscribe</a>.</td></tr></table>""".format(
                unconfirm_url=unconfirm_url
            )
            return inlined + suffix
        return inlined

    def render_subject(self, data):
        subject = pystache.render(self.subject, data)
        return subject

    def render_with_sample_context(self):
        data = EmailTemplate.make_mustache_context(
            data={
                "name": "Irwin Jones",
                "_replyto": "i.jones@example.com",
                "message": "Hello!\n\nThis is a preview message!",
            },
            host="example.com/",
            keys=["name", "_replyto", "message"],
            now=datetime.datetime.utcnow().strftime("%I:%M %p UTC - %d %B %Y"),
            unconfirm_url="#",
        )
        body = self.render_body(data, "#") if self.body else None
        subject = self.render_subject(data) if self.subject else None
        return body, subject


class RoutingRule(DB.Model):
    __tablename__ = "routing_rules"

    id = DB.Column(DB.String, primary_key=True)
    form_id = DB.Column(DB.Integer, DB.ForeignKey("forms.id"), nullable=False)
    trigger = DB.Column(MutableDict.as_mutable(JSON))
    email = DB.Column(DB.String)

    # hidden 'form' property maps to the form referenced at form_id
    # this dirty magic is defined in the rules DB.Relationship at Form.

    functions = ["exists", "contains", "doesntexist", "doesntcontain", "true"]

    def __init__(self, form_id):
        self.id = str(uuid.uuid4())
        self.form_id = form_id

    def __repr__(self):
        return "<RoutingRule %s, form=%s>" % (self.id, self.form_id)

    def serialize(self):
        return {"id": self.id, "trigger": self.trigger, "email": self.email}

    def matches(self, submission):
        fn_name = self.trigger["fn"]
        field = self.trigger["field"]
        params = self.trigger["params"]

        val = (
            None
            if not field
            else (
                submission.host
                if field == "_host"
                else submission.submitted_at
                if field == "_date"
                else submission.data.get(field, "")
            )
        )

        return getattr(RoutingRule, fn_name)(val, *params)

    @staticmethod
    def serialize_function(fn_name):
        fn = getattr(RoutingRule, fn_name)
        params = [
            p
            for p in inspect.signature(fn).parameters.values()
            if p.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD
        ]
        doc = inspect.getdoc(fn)

        return {
            "name": fn_name,
            "doc": doc,
            "uses_field": len(params) > 0,
            "params": [p.name for p in params[1:]],
        }

    @staticmethod
    def contains(field, substring="", *args):
        "Match if contained in"
        return substring in field if field else False

    @staticmethod
    def doesntcontain(field, substring="", *args):
        "Match if not contained in"
        return substring not in field if field else True

    @staticmethod
    def exists(field, *args):
        "Match if not empty"
        return field and field != ""

    @staticmethod
    def doesntexist(field, *args):
        "Match if empty"
        return not field

    @staticmethod
    def true(*args):
        "Always match"
        return True


class SubmissionStatus(DB.Enum):
    pending = "pending"
    processed = "processed"
    statuses = [pending, processed]


@celery.task()
def process_and_commit_submission(sub_id, *args):
    g.log.bind(sub=sub_id)
    sub = Submission.query.filter_by(id=sub_id).first()
    if not sub:
        g.log.warning("Submission not found with id.")
        return

    g.log = g.log.bind(form=sub.form.hashid)
    try:
        sub.process(*args)
        sub.status = SubmissionStatus.processed
    except:
        sub.append_error(
            "Unexpected Error, please contact support", debug_msg=traceback.format_exc()
        )
        raise

    finally:
        # if submission storage is disabled, remove submission after processing
        # note that if there are errors, they won't be captured
        if sub.form.has_feature("dashboard") and sub.form.disable_storage:
            DB.session.delete(sub)
        else:
            DB.session.add(sub)
        DB.session.commit()


class Submission(DB.Model):
    SUBJECT_SUBMISSION = "New submission from %s"
    SUBJECT_APPROACHING_LIMIT = "Formspree Notice: Approaching Submission Limit"
    SUBJECT_OVER_LIMIT = "Formspree Notice: Submission Limit Reached"
    UNKNOWN_REFERRER = "an unknown webpage"

    __tablename__ = "submissions"

    id = DB.Column(DB.Integer, primary_key=True)
    submitted_at = DB.Column(DB.DateTime)
    form_id = DB.Column(
        DB.Integer, DB.ForeignKey("forms.id"), nullable=False, index=True
    )
    data = DB.Column(MutableDict.as_mutable(JSON))
    host = DB.Column(DB.Text)
    spam = DB.Column(DB.Boolean)
    errors = DB.Column(JSON)
    status = DB.Column(
        DB.Enum(*SubmissionStatus.statuses, name="submission_status"),
        nullable=False,
        default="pending",
    )

    # hidden 'form' property maps to the form referenced at form_id
    # this dirty magic is defined in the subscriptions DB.Relationship at Form.

    def __init__(self, form_id):
        self.submitted_at = datetime.datetime.utcnow()
        self.form_id = form_id

    def __repr__(self):
        return "<Submission %s, form=%s, date=%s, keys=%s>" % (
            self.id or "with an id to be assigned",
            self.form_id,
            self.submitted_at.isoformat(),
            self.data.keys(),
        )

    def get_host_path(self):
        return referrer_to_path(self.host) if self.host else self.UNKNOWN_REFERRER

    def append_error(self, message, plugin_kind=None, rule_id=None, debug_msg=None):
        self.errors = self.errors or []
        self.errors.append(
            {
                "message": message,
                "plugin": plugin_kind,
                "rule": rule_id,
                "debug": debug_msg,
            }
        )

    def serialize(self):
        data = self.data.copy()
        data["_date"] = self.submitted_at.isoformat()
        data["_id"] = self.id
        data["_host"] = self.host
        data["_errors"] = ", ".join(
            [e.get("message") for e in self.errors if e.get("message")]
        )
        data["_status"] = self.status
        for k in KEYS_NOT_STORED:
            data.pop(k, None)
        return data

    @property
    def spam_hash(self):
        return spam_serializer.dumps(self.id)

    def dispatch_plugins(self, keys):
        # dispatch webhooks to subscriptions
        for plugin in self.form.plugins.filter_by(enabled=True):
            try:
                plugin.dispatch(self, sorted_keys=keys)
            except Exception as e:
                # an unknown exception (known exceptions should be
                # handled inside the plugin call)
                # it's important to catch exceptions here so the failure
                # of one plugin doesn't interfere with everything else.
                g.log.error(
                    "Unknown exception in plugin dispatch.",
                    submission=self.id,
                    kind=plugin.kind,
                    exc=e,
                )
                self.append_error(
                    "Unknown exception in plugin dispatch. Please contact support.",
                    plugin_kind=plugin.kind,
                    debug_msg=traceback.format_exc(),
                )

    def check_over_submission_limit(self, unconfirm_url):
        # check if the forms are over the counter and the user has unlimited submissions
        monthly_counter = self.form.update_counters()
        monthly_limit = (
            settings.MONTHLY_SUBMISSIONS_LIMIT
            if self.form.id > settings.FORM_LIMIT_DECREASE_ACTIVATION_SEQUENCE
            else settings.GRANDFATHER_MONTHLY_LIMIT
        )
        overlimit = monthly_counter > monthly_limit and not self.form.has_feature(
            "unlimited"
        )

        if overlimit:
            g.log.info("Form over limit.", monthly_counter=monthly_counter)

        # send overlimit or approaching limit emails

        if monthly_counter == int(monthly_limit * 0.9) and not self.form.has_feature(
            "unlimited"
        ):
            # send email notification
            send_email(
                to=self.form.email,
                subject=self.SUBJECT_APPROACHING_LIMIT,
                text=render_template(
                    "email/90-percent-warning.txt",
                    unconfirm_url=unconfirm_url,
                    limit=monthly_limit,
                ),
                html=render_email(
                    "90-percent-warning.html",
                    unconfirm_url=unconfirm_url,
                    limit=monthly_limit,
                ),
                sender=settings.DEFAULT_SENDER,
            )

        # send an overlimit notification for the first x overlimit emails
        # after that, return an error so the user can know the website owner is not
        # going to read his message.
        if (
            overlimit
            and monthly_counter
            <= monthly_limit + settings.OVERLIMIT_NOTIFICATION_QUANTITY
        ):
            send_email(
                to=self.form.email,
                subject=self.SUBJECT_OVER_LIMIT,
                text=render_template(
                    "email/overlimit-notification.txt",
                    host=self.get_host_path(),
                    unconfirm_url=unconfirm_url,
                    limit=monthly_limit,
                ),
                html=render_email(
                    "overlimit-notification.html",
                    host=self.get_host_path(),
                    unconfirm_url=unconfirm_url,
                    limit=monthly_limit,
                ),
                sender=settings.DEFAULT_SENDER,
            )

        return overlimit

    def process(self, keys):
        """
        Processes a submission, including sending submission to target email.
        Assumes sender's email has been verified.

        NOTE: shouldn't call DB.commit() when processing a submission. All actions are
        committed after processing by process_and_commit_submission()
        """

        # url to request_unconfirm_form page
        unconfirm_url = url_for(
            "request_unconfirm_form", form_id=self.form.id, _external=True
        )
        spam_url = url_for("mark-spam", id=self.spam_hash, _external=True)

        if (
            not self.form.has_feature("archive")
            and random.random() < settings.EXPENSIVELY_WIPE_SUBMISSIONS_FREQUENCY
        ):
            self.form.delete_over_archive_limit()

        if self.check_over_submission_limit(unconfirm_url) is True:
            self.append_error("Over submission limit")
            return

        self.dispatch_plugins(keys)

        # build the list of recipients: for normal forms it will be just
        # form.email; for forms with routing rules we ignore that and use
        # the results from the routing rules instead.
        if (
            self.form.has_feature("submission_routing")
            and self.form.routing_rules.count()
        ):
            recipients = {
                (rule.email, rule.id)
                for rule in self.form.routing_rules
                if rule.matches(self)
            }
            g.log.info("Got recipients from route matching", n=len(recipients))
        else:
            # if emails are disabled, don't send email notification
            # (but routing rules are applied anyway)
            if self.form.has_feature("dashboard") and self.form.disable_email:
                g.log.info("Form has email disabled, will not send.")
                return
            else:
                recipients = {(self.form.email, None)}
                g.log.info("Will send to simple recipient", recipient=self.form.email)

        # prepare email properties -----------------------------------------------

        # set variables used for sending a submission

        reply_to = get_replyto(self.data)
        subject = self.data.get("_subject") or self.get_host_path()

        cc = self.data.get("_cc", None)
        format = self.data.get("_format", None)
        from_name = None

        # turn cc emails into array
        if cc:
            cc = [e.strip() for e in cc.split(",")]

        now = datetime.datetime.utcnow().strftime("%I:%M %p UTC - %d %B %Y")

        text = render_template(
            "email/form.txt",
            data=self.data,
            host=self.get_host_path(),
            keys=keys,
            now=now,
            unconfirm_url=unconfirm_url,
        )

        template_data = EmailTemplate.make_mustache_context(
            data=self.data,
            host=self.get_host_path(),
            keys=keys,
            now=now,
            unconfirm_url=unconfirm_url,
        )

        # if there's a custom email template we should use it
        # otherwise check if the user wants a new or old version of the email
        if (
            self.form.has_feature("whitelabel")
            and self.form.template
            and self.form.template.body
        ):
            html = self.form.template.render_body(template_data, unconfirm_url)
        elif format == "plain":
            html = render_template(
                "email/plain_form.html",
                data=self.data,
                host=self.get_host_path(),
                keys=keys,
                now=now,
                unconfirm_url=unconfirm_url,
            )
        else:
            html = render_email(
                "form.html",
                data=self.data,
                host=self.get_host_path(),
                keys=keys,
                now=now,
                unconfirm_url=unconfirm_url,
                submission_count=self.form.counter,
                upgraded=self.form.has_feature("dashboard"),
                spam_url=spam_url,
            )

        # override other email properties if there's a template
        if self.form.has_feature("whitelabel") and self.form.template:
            subject = (
                self.form.template.render_subject(template_data)
                if self.form.template.subject
                else subject
            )
            from_name = self.form.template.from_name or from_name

        # send the emails ----------------------------------------------------------

        for to, rule_id in recipients:
            g.log.info("Submitting.", target=to)
            result = send_email(
                to=to,
                subject=subject,
                text=text,
                html=html,
                sender=settings.DEFAULT_SENDER,
                from_name=from_name,
                reply_to=reply_to,
                cc=cc,
                headers={
                    "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
                    "List-Unsubscribe": "<"
                    + url_for(
                        "unconfirm_form",
                        form_id=self.form.id,
                        digest=self.form.unconfirm_digest(),
                        _external=True,
                    )
                    + ">",
                },
            )

            if not result[0]:
                g.log.warning("Failed to send email.", reason=result[1], code=result[2])
                # self.errors.append("Couldn't send email. " + result[1])
                self.append_error(
                    "Could not send email",
                    debug_msg=f"code {result[2]}: {result[1]}",
                    rule=rule_id,
                )
