from lxml.html import rewrite_links

from flask import request, jsonify, g
from flask_cors import cross_origin
from flask_login import current_user, login_required

from formspree import settings
from formspree.app_globals import DB, spam_serializer
from formspree.utils import prevent_xsrf, requires_feature
from .helpers import form_control
from .models import Form, Submission, EmailTemplate, RoutingRule
from ..utils import unflattenUrlParams


@prevent_xsrf
@login_required
def list_forms():
    # grab all the forms this user controls
    if current_user.has_feature("dashboard"):
        forms = current_user.forms.order_by(Form.id.desc()).all()
    else:
        forms = []

    return jsonify({"ok": True, "forms": [f.serialize() for f in forms]})


@prevent_xsrf
@login_required
@requires_feature("dashboard")
def create_form():
    name = request.get_json().get("name")
    email = request.get_json().get("email")
    g.log = g.log.bind(email=email, name=name)

    if email not in current_user.verified_addresses:
        g.log.info("Failed to create form. Address not verified.")
        return (jsonify({"error": "The provided email address isn't verified."}), 400)

    g.log.info("Creating a new form from the dashboard.")

    email = email.lower().strip()  # case-insensitive
    form = Form(email, confirmed=True, owner=current_user, name=name)
    DB.session.add(form)
    DB.session.commit()

    return (
        jsonify(
            {
                "ok": True,
                "hashid": form.hashid,
                "submission_url": settings.API_ROOT + "/" + form.hashid,
                "confirmed": form.confirmed,
            }
        ),
        201,
    )


@prevent_xsrf
@login_required
@form_control
@requires_feature("dashboard")
def get_form(hashid, form):
    return jsonify(form.serialize())


@prevent_xsrf
@login_required
@form_control
@requires_feature("dashboard")
def update_form(hashid, form):
    patch = request.get_json()

    if "email" in patch and patch["email"] not in current_user.verified_addresses:
        return jsonify({"ok": False, "error": "Email not verified."}), 403

    for attr in [
        "name",
        "email",
        "disable_storage",
        "disabled",
        "disable_email",
        "captcha_disabled",
    ]:
        if attr in patch:
            setattr(form, attr, patch[attr])

    if "api_enabled" in patch:
        if not form.has_feature("api_access"):
            return jsonify({"ok": False, "error": "Please upgrade your account."}), 402

        if patch["api_enabled"] == True:
            if form.apikey:
                pass
            else:
                form.reset_apikey()
        else:
            form.apikey = None

    DB.session.add(form)
    DB.session.commit()
    return jsonify({"ok": True})


@prevent_xsrf
@login_required
@form_control
@requires_feature("submission_routing")
def add_or_update_rule(hashid, form, ruleid=None):
    rule_data = request.get_json()
    if {"email", "trigger"} != rule_data.keys() or {
        "fn",
        "field",
        "params",
    } != rule_data["trigger"].keys():
        return jsonify({"ok": False, "error": "Missing required parameters."}), 400

    if rule_data["trigger"]["fn"] not in RoutingRule.functions:
        return jsonify({"ok": False, "error": "Invalid function."}), 400

    if rule_data["email"] not in current_user.verified_addresses:
        return jsonify({"ok": False, "error": "Email not verified."}), 403

    rule = (
        form.routing_rules.filter_by(id=ruleid).first()
        if ruleid
        else RoutingRule(form_id=form.id)
    )
    rule.trigger = rule_data["trigger"]
    rule.email = rule_data["email"]
    DB.session.add(rule)
    DB.session.commit()
    return jsonify({"ok": True, "id": rule.id}), 200 if ruleid else 201


@prevent_xsrf
@login_required
@form_control
@requires_feature("submission_routing")
def delete_rule(ruleid, hashid, form):
    rule = form.routing_rules.filter_by(id=ruleid).first()
    DB.session.delete(rule)
    DB.session.commit()
    return jsonify({"ok": True})


@prevent_xsrf
@login_required
@form_control
@requires_feature("api_access")
def reset_apikey(hashid, form):
    form.reset_apikey()
    DB.session.add(form)
    DB.session.commit()

    return jsonify({"ok": True, "key": form.apikey})


@prevent_xsrf
@login_required
@form_control
@requires_feature("dashboard")
def delete_form(hashid, form):
    for submission in form.submissions:
        DB.session.delete(submission)

    for plugin in form.plugins:
        DB.session.delete(plugin)

    DB.session.delete(form)
    DB.session.commit()

    return jsonify({"ok": True})


@prevent_xsrf
@login_required
@form_control
@requires_feature("dashboard")
def list_fields(hashid, form):
    submissions, fields = form.submissions_with_fields(
        with_ids=False, with_errors=False, limit=100
    )

    if not submissions:
        return []

    return jsonify(fields)


@prevent_xsrf
@login_required
@form_control
@requires_feature("archive")
def submission_list(hashid, form):
    params = unflattenUrlParams(request.args)
    filter = params.get("filter", {"spam": False})
    submissions, fields = form.submissions_with_fields(
        with_ids=True, with_errors=True, filter=filter
    )
    return jsonify({"submissions": submissions, "fields": fields})


@prevent_xsrf
def mark_submission_spam():
    data = request.get_json()
    submission = Submission.query.get(spam_serializer.loads(data.get("id")))
    submission.spam = data.get("spam")
    DB.session.add(submission)
    DB.session.commit()
    return jsonify({"ok": True})


@prevent_xsrf
@login_required
@form_control
@requires_feature("archive")
def submission_delete(hashid, form):
    data = request.get_json()
    ids = data.get("submissions", [])

    # Note: this could be optimised by using filter().delete().
    # Although faster, we wouldn't be able to catch bad ids before decrementing
    # form counter, allowing a greater chance form counter will go out of sync.
    subs = form.submissions.filter(Submission.id.in_(ids)).all()

    for sub in subs:
        DB.session.delete(sub)
        # spam submissions aren't counted
        if not sub.spam:
            form.counter -= 1

    DB.session.add(form)
    DB.session.commit()
    return jsonify({"ok": True, "deleted": len(subs), "counter": form.counter})


@prevent_xsrf
@login_required
@form_control
@requires_feature("archive")
def submission_set(hashid, form):
    data = request.get_json()
    op = data.get("operation", {})
    ids = data.get("submissions", [])

    # Note: this could be optimised by using filter().update().
    # Although faster, we wouldn't be able to check each id before inc/dec
    # form counter, allowing a greater chance form counter will go out of sync.
    subs = form.submissions.filter(Submission.id.in_(ids)).all()

    for sub in subs:
        spam = op.get("spam", sub.spam)
        # Only inc/dec counter when spam value changes. However, just checking
        # that spam != sub.spam doesn't work when spam == False and sub.spam == None
        if spam and not sub.spam:
            form.counter -= 1
        if not spam and sub.spam:
            form.counter += 1
        sub.spam = spam
        DB.session.add(sub)

    DB.session.add(form)
    DB.session.commit()
    return jsonify({"ok": True, "updated": len(subs), "counter": form.counter})


@prevent_xsrf
@login_required
@form_control
@requires_feature("custom_emails")
def custom_template_set(hashid, form):
    template = form.template
    if not template:
        template = EmailTemplate(form_id=form.id)

    data = request.get_json()
    template.from_name = data.get("from_name", template.from_name)
    template.subject = data.get("subject", template.subject)
    template.style = data.get("style", template.style)
    template.body = data.get("body", template.body)

    if template.body or template.subject:
        try:
            template.render_with_sample_context()
        except Exception as e:
            print(e)
            return jsonify({"error": "Failed to render. The template has errors."}), 406

    DB.session.add(template)
    DB.session.commit()
    return jsonify({"ok": True})


@prevent_xsrf
@login_required
@requires_feature("custom_emails")
def custom_template_preview_render():
    data = request.form
    body, _ = EmailTemplate.make_preview(
        from_name=data.get("from_name"),
        subject=data.get("subject"),
        style=data.get("style"),
        body=data.get("body"),
    )

    return rewrite_links(body, lambda x: "#" + x)


@cross_origin(allow_headers=["Accept", "Content-Type", "Authorization"])
@form_control(api_type="public", allow_readonly=True)
@requires_feature("api_access")
def v0_form(hashid, form):
    return jsonify(
        {
            "ok": True,
            "submission_url": settings.API_ROOT + "/" + form.hashid,
            "total_submissions": form.counter,
        }
    )


@cross_origin(allow_headers=["Accept", "Content-Type", "Authorization"])
@form_control(api_type="public", allow_readonly=True)
@requires_feature("api_access")
def v0_submissions(hashid, form):
    order = request.args.get("order", "desc")
    limit = request.args.get("limit")
    since = request.args.get("since")

    submissions, fields = form.submissions_with_fields(
        with_ids=False, since=since, limit=limit
    )
    return jsonify(
        {
            "ok": True,
            "submissions": submissions
            if order == "desc"
            else [s for s in reversed(submissions)],
            "fields": fields,
        }
    )
