import requests
import datetime
import calendar
import json
import re
from urllib.parse import urlparse, urlunparse
from functools import wraps, partial

from flask import request, url_for, jsonify, g
from flask_login import current_user

from formspree import settings

CAPTCHA_URL = "https://www.google.com/recaptcha/api/siteverify"
CAPTCHA_VAL = "g-recaptcha-response"

def is_valid_email(addr):
    return re.match(r"[^@]+@[^@]+\.[^@]+", addr) is not None


def valid_url(url):
    parsed = urlparse(url)
    return (
        len(parsed.scheme) > 0 and len(parsed.netloc) > 0 and not "javascript:" in url
    )


def request_wants_json():
    if (
        request.headers.get("X_REQUESTED_WITH", "").lower() == "xmlhttprequest"
        or request.headers.get("X-REQUESTED-WITH", "").lower() == "xmlhttprequest"
    ):
        return True
    if accept_better("json", "html"):
        return True
    if "json" in request.headers.get("Content-Type", "") and not accept_better(
        "html", "json"
    ):
        return True
    return False


def accept_better(subject, against):
    if "Accept" in request.headers:
        accept = request.headers["Accept"].lower()
        try:
            isub = accept.index(subject)
        except ValueError:
            return False

        try:
            iaga = accept.index(against)
        except ValueError:
            return True

        return isub < iaga
    else:
        return False


def url_domain(url):
    parsed = urlparse(url)
    return ".".join(parsed.netloc.split(".")[-2:])


def unflattenUrlParams(params):
    """ converts url params of the form obj.param=val into {"obj": {"param": "val"}} """
    result = params.copy()
    for k, v in params.items():
        parts = k.split(".")
        if len(parts) > 1:
            if not parts[0] in result or not type(result[parts[0]]) == dict:
                result[parts[0]] = dict()
            result[parts[0]][parts[1]] = json.loads(v)
            del result[k]
    return result


def unix_time_for_12_months_from_now(now=None):
    now = now or datetime.date.today()
    month = now.month - 1 + 12
    next_year = now.year + int(month / 12)
    next_month = month % 12 + 1
    start_of_next_month = datetime.datetime(next_year, next_month, 1, 0, 0)
    return calendar.timegm(start_of_next_month.utctimetuple())


def next_url(referrer=None, next=None):
    referrer = referrer if referrer is not None else ""

    if next:
        # use the referrer as base, replace its parts with the provided
        # parts from _next. so, if _next is only a path it will just use
        # that path. if it is a netloc without a scheme, will use that
        # netloc, but reuse the scheme from base and so on.
        parsed_next = urlparse(next)
        base = urlparse(referrer)

        return urlunparse(
            [
                parsed_next.scheme or base.scheme,
                parsed_next.netloc or base.netloc,
                parsed_next.path or base.path,
                parsed_next.params or base.params,
                parsed_next.query or base.query,
                parsed_next.fragment or base.fragment,
            ]
        )
    else:
        return url_for("thanks", next=referrer)


def send_email(
    to=None,
    subject=None,
    text=None,
    html=None,
    sender=None,
    cc=None,
    reply_to=None,
    headers=None,
    from_name=None,
):
    g.log = g.log.new(to=to, sender=sender)

    if None in [to, subject, text, sender]:
        raise ValueError("to, subject text and sender required to send email")

    data = {
        "api_user": settings.SENDGRID_USERNAME,
        "api_key": settings.SENDGRID_PASSWORD,
        "to": to,
        "subject": subject,
        "text": text,
        "html": html,
    }

    # parse 'from_name' from 'sender' if it is
    # formatted like "Name <name@email.com>"
    try:
        bracket = sender.index("<")
        data.update(
            {"from": sender[bracket + 1 : -1], "fromname": sender[:bracket].strip()}
        )
    except ValueError:
        data.update({"from": sender})

    if from_name:
        data.update({"fromname": from_name})

    if headers:
        data.update({"headers": json.dumps(headers)})

    if reply_to:
        data.update({"replyto": reply_to})

    if cc:
        valid_emails = [email for email in cc if is_valid_email(email)]
        data.update({"cc": valid_emails})

    result = requests.post("https://api.sendgrid.com/api/mail.send.json", data=data)

    errmsg = ""
    if result.status_code / 100 != 2:
        try:
            errmsg = "; \n".join(result.json().get("errors"))
        except ValueError:
            errmsg = result.text
        g.log.warning("Could not send email.", err=errmsg)
    else:
        g.log.info("Sent email.", to=to)

    return result.status_code / 100 == 2, errmsg, result.status_code


def referrer_to_path(r):
    if not r:
        return ""
    parsed = urlparse(r)
    n = parsed.netloc + parsed.path
    return n


def referrer_to_baseurl(r):
    if not r:
        return ""
    parsed = urlparse(r)
    n = parsed.netloc
    return n


def prevent_xsrf(func):
    @wraps(func)
    def decorated_view(*args, **kwargs):
        referrer = referrer_to_baseurl(request.referrer)
        service = referrer_to_baseurl(settings.SERVICE_URL)
        if referrer != service:
            return jsonify({"ok": False, "error": "Improper request."}), 400
        else:
            return func(*args, **kwargs)

    return decorated_view


def verify_captcha(form_data, remote_ip):
    if not CAPTCHA_VAL in form_data:
        return False

    try:
        r = requests.post(
            CAPTCHA_URL,
            data={
                "secret": settings.RECAPTCHA_SECRET,
                "response": form_data[CAPTCHA_VAL],
                "remoteip": remote_ip,
            },
            timeout=2,
        )
        return r.ok and r.json().get("success")
    except requests.exceptions.ConnectionError:
        # when google or us are failing, assume everything is ok so the user don't get sad
        return True


def requires_feature(*args, **kwargs):
    if "feature" not in kwargs:
        return partial(requires_feature, feature=args[0])

    func = args[0]
    feature = kwargs["feature"]

    @wraps(func)
    def decorated_view(*args, **kwargs):
        if "form" in kwargs:
            if not kwargs["form"].has_feature(feature):
                return (
                    jsonify({"error": "Feature unavailable for this form's plan."}),
                    402,
                )
        else:
            if not current_user.has_feature(feature):
                return (
                    jsonify({"error": "Feature unavailable for current logged user."}),
                    402,
                )

        return func(*args, **kwargs)

    return decorated_view
