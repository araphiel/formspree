from urllib.parse import urljoin

from flask import request, render_template, redirect, jsonify, g
from flask_cors import cross_origin
from jinja2.exceptions import TemplateNotFound

from formspree import settings
from formspree.utils import (
    request_wants_json,
    is_valid_email,
    url_domain,
    referrer_to_path,
    verify_captcha,
)
from formspree.forms import errors
from formspree.forms.errors import SubmitFormError
from formspree.forms.helpers import (
    http_form_to_dict,
    ordered_storage,
    temp_store_hostname,
    get_temp_hostname,
)
from formspree.forms.models import Form


def get_host_and_referrer(received_data):
    """
    Looks for stored hostname in redis (from captcha).
    If it doesn't exist, uses the referer header.
    """

    try:
        return get_temp_hostname(received_data["_host_nonce"])
    except KeyError:
        return referrer_to_path(request.referrer), request.referrer
    except ValueError as err:
        g.log.error("Invalid hostname stored on Redis.", err=err)
        raise SubmitFormError(
            (
                render_template(
                    "error.html",
                    title="Unable to submit form",
                    text="<p>We had a problem identifying to whom we should have submitted this form. "
                    "Please try submitting again. If it fails once more, please let us know at {email}</p>".format(
                        email=settings.CONTACT_EMAIL
                    ),
                ),
                500,
            )
        )


def validate_user_form(hashid):
    """
    Gets a form from a hashid, created on the dashboard.
    Checks to make sure the submission can be accepted by this form.
    """

    form = Form.get_with(hashid=hashid)

    if not form:
        raise SubmitFormError(errors.bad_hashid_error(hashid))

    if form.disabled:
        raise SubmitFormError(errors.disabled_error())

    return form


def get_or_create_form(email, host):
    """
    Gets the form if it already exits, otherwise checks to ensure
    that this is a valid new form submission. If so, creates a
    new form.
    """

    form = Form.get_with(email=email, host=host)

    if not form:
        if request_wants_json():
            # Can't create a new ajax form unless from the dashboard
            ajax_error_str = (
                "To prevent spam, only "
                + settings.UPGRADED_PLAN_NAME
                + " accounts may create AJAX forms."
            )
            raise SubmitFormError((jsonify({"error": ajax_error_str}), 400))

        if (
            url_domain(settings.SERVICE_URL) in host
            and host.rstrip("/") != settings.TEST_URL
        ):
            # Bad user is trying to submit a form spoofing formspree.io
            g.log.info(
                "User attempting to create new form spoofing SERVICE_URL. Ignoring."
            )
            raise SubmitFormError(
                (
                    render_template(
                        "error.html", title="Unable to submit form", text="Sorry."
                    ),
                    400,
                )
            )

        # all good, create form
        form = Form(email, host=host, confirmed=False, normalize=True)

    if form.disabled:
        raise SubmitFormError(errors.disabled_error())

    return form


def check_captcha(form, email_or_string, received_data, sorted_keys):
    """
    Checks to see if a captcha page is required, if so renders it.
    """

    captcha_verified = verify_captcha(received_data, request.remote_addr)

    # TODO: Write tests that disable testing state so we can at least test that the captcha is rendered
    needs_captcha = not (
        (form.has_feature("dashboard") and form.captcha_disabled)
        or captcha_verified
        or (
            request_wants_json()
            and form.id <= settings.FORM_AJAX_DISABLE_ACTIVATION_SEQUENCE
        )
        or settings.TESTING
    )

    if needs_captcha:
        if request_wants_json():
            return (
                jsonify(
                    {
                        "error": (
                            "In order to submit via AJAX reCAPTCHA protection must "
                            "first be disabled in this form's settings page."
                        )
                    }
                ),
                403,
            )

        data_copy = received_data.copy()
        # Temporarily store hostname in redis while doing captcha
        nonce = temp_store_hostname(form.host, request.referrer)
        data_copy["_host_nonce"] = nonce
        action = urljoin(settings.API_ROOT, email_or_string)
        try:
            if "_language" in received_data:
                return render_template(
                    "forms/captcha_lang/{}.html".format(received_data["_language"]),
                    data=data_copy,
                    sorted_keys=sorted_keys,
                    action=action,
                    lang=received_data["_language"],
                )
        except TemplateNotFound:
            g.log.warning(
                "Requested language not found for reCAPTCHA page, defaulting to English",
                referrer=request.referrer,
                lang=received_data["_language"],
            )
            pass

        return (
            render_template(
                "forms/captcha.html",
                data=data_copy,
                sorted_keys=sorted_keys,
                action=action,
                lang=None,
            ),
            401,
        )


def email_sent_success(status):
    if request_wants_json():
        return jsonify({"success": "email sent", "next": status["next"]})

    return redirect(status["next"], code=302)


def confirmation_sent_success(form, host, status):
    if request_wants_json():
        return jsonify({"success": "confirmation email sent"})

    return render_template(
        "forms/confirmation_sent.html",
        email=form.email,
        host=host,
        resend=status["code"] == Form.STATUS_CONFIRMATION_DUPLICATED,
    )


def response_for_status(form, host, referrer, status):

    g.log.info("Responding with status", code=status["code"])

    if status["code"] == Form.STATUS_SUBMISSION_ENQUEUED:
        return email_sent_success(status)

    if status["code"] == Form.STATUS_SUBMISSION_EMPTY:
        return errors.empty_form_error(referrer)

    if (
        status["code"] == Form.STATUS_CONFIRMATION_SENT
        or status["code"] == Form.STATUS_CONFIRMATION_DUPLICATED
    ):
        return confirmation_sent_success(form, host, status)

    if status["code"] == Form.STATUS_REPLYTO_ERROR:
        return errors.malformed_replyto_error(status)

    return errors.generic_send_error(status)


@cross_origin(
    allow_headers=["Accept", "Content-Type", "X-Requested-With", "Authorization"]
)
@ordered_storage
def post(email_or_string):
    """
    Main endpoint, and first stage of submission handling.
    Responsible for finding or creating the form, and checking form state.
    Then decides whether to send submission or activation email, or do nothing.
    """

    g.log = g.log.bind(target=email_or_string)

    if request.method == "GET":
        return errors.bad_method_error()

    if request.form:
        received_data, sorted_keys = http_form_to_dict(request.form)
    else:
        received_data = request.get_json(force=True, silent=True) or {}
        sorted_keys = list(received_data.keys())

    try:
        # NOTE: host in this function generally refers to the referrer hostname.
        host, referrer = get_host_and_referrer(received_data)
    except SubmitFormError as vfe:
        return vfe.response

    g.log = g.log.bind(host=host)

    if not is_valid_email(email_or_string):
        # in this case it can be a hashid identifying a
        # form generated from the dashboard
        try:
            form = validate_user_form(email_or_string)
        except SubmitFormError as vfe:
            return vfe.response
    else:
        # in this case, it is a normal email
        if not host:
            return errors.no_referrer_error()

        try:
            form = get_or_create_form(email_or_string.lower(), host)
        except SubmitFormError as vfe:
            return vfe.response

    captcha_page = check_captcha(form, email_or_string, received_data, sorted_keys)
    if captcha_page:
        g.log.info("Redirect to captcha")
        return captcha_page

    # If form exists and is confirmed, send email
    # otherwise send a confirmation email
    if form.confirmed:
        status = form.submit(received_data, sorted_keys, referrer)
    else:
        status = form.send_confirmation(
            store_data=received_data, sorted_keys=sorted_keys
        )

    return response_for_status(form, host, referrer, status)
