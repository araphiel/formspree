import formspree.forms.views as fv
import formspree.forms.api as fa
import formspree.forms.endpoint as fe
import formspree.users.views as uv
import formspree.users.api as ua
import formspree.static_pages.views as sv
import formspree.plugins.views as pv
import formspree.plugins.api as pa


def configure_routes(app):
    app.add_url_rule("/", "index", view_func=sv.default, methods=["GET"])
    app.add_url_rule("/favicon.ico", view_func=sv.favicon)

    # public forms
    app.add_url_rule("/<email_or_string>", view_func=fe.post, methods=["GET", "POST"])
    app.add_url_rule(
        "/unblock/<email>",
        "unblock_email",
        view_func=fv.unblock_email,
        methods=["GET", "POST"],
    )
    app.add_url_rule(
        "/resend/<email>",
        "resend_confirmation",
        view_func=fv.resend_confirmation,
        methods=["POST"],
    )
    app.add_url_rule(
        "/confirm/<nonce>", "confirm_email", view_func=fv.confirm_email, methods=["GET"]
    )
    app.add_url_rule(
        "/unconfirm/<form_id>",
        "request_unconfirm_form",
        view_func=fv.request_unconfirm_form,
        methods=["GET"],
    )
    app.add_url_rule(
        "/unconfirm/multiple",
        "unconfirm_multiple",
        view_func=fv.unconfirm_multiple,
        methods=["POST"],
    )
    app.add_url_rule(
        "/unconfirm/<digest>/<form_id>",
        "unconfirm_form",
        view_func=fv.unconfirm_form,
        methods=["GET", "POST"],
    )
    app.add_url_rule("/thanks", "thanks", view_func=fv.thanks, methods=["GET"])

    # dashboard
    app.add_url_rule("/plans", "plans", view_func=sv.serve_plans, methods=["GET"])
    app.add_url_rule(
        "/dashboard", "dashboard", view_func=sv.serve_dashboard, methods=["GET"]
    )
    app.add_url_rule("/forms", "forms", view_func=sv.serve_dashboard, methods=["GET"])
    app.add_url_rule(
        "/forms/<hashid>", "form-page", view_func=sv.serve_dashboard, methods=["GET"]
    )
    app.add_url_rule(
        "/forms/<hashid>/<path:s>",
        "form-page-section",
        view_func=sv.serve_dashboard,
        methods=["GET"],
    )
    app.add_url_rule(
        "/account", "account", view_func=sv.serve_dashboard, methods=["GET"]
    )
    app.add_url_rule("/account/billing", view_func=sv.serve_dashboard, methods=["GET"])

    # login stuff
    app.add_url_rule(
        "/register", "register", view_func=uv.register, methods=["GET", "POST"]
    )
    app.add_url_rule("/login", "login", view_func=uv.login, methods=["GET", "POST"])
    app.add_url_rule(
        "/login/reset",
        "forgot-password",
        view_func=uv.forgot_password,
        methods=["GET", "POST"],
    )
    app.add_url_rule(
        "/login/reset/<digest>",
        "reset-password",
        view_func=uv.reset_password,
        methods=["GET", "POST"],
    )
    app.add_url_rule("/logout", "logout", view_func=uv.logout, methods=["GET"])

    # users
    app.add_url_rule(
        "/account/billing/invoice/<invoice_id>", view_func=uv.invoice, methods=["GET"]
    )
    app.add_url_rule(
        "/account/verify",
        "verify-account-email",
        view_func=uv.verify_account_email,
        methods=["GET", "POST"],
    )
    app.add_url_rule("/api-int/buy", view_func=ua.buy, methods=["POST"])
    app.add_url_rule("/api-int/cancel", view_func=ua.cancel, methods=["POST"])
    app.add_url_rule("/api-int/resubscribe", view_func=ua.resubscribe, methods=["POST"])
    app.add_url_rule("/api-int/account", view_func=ua.get_account, methods=["GET"])
    app.add_url_rule("/api-int/account", view_func=ua.update_account, methods=["PATCH"])
    app.add_url_rule(
        "/api-int/account/emails", view_func=ua.add_email, methods=["POST"]
    )
    app.add_url_rule(
        "/api-int/account/emails/<address>",
        view_func=ua.delete_email,
        methods=["DELETE"],
    )
    app.add_url_rule("/api-int/account/cards", view_func=ua.add_card, methods=["POST"])
    app.add_url_rule(
        "/api-int/account/cards/<cardid>/default",
        view_func=ua.change_default_card,
        methods=["PUT"],
    )
    app.add_url_rule(
        "/api-int/account/cards/<cardid>", view_func=ua.delete_card, methods=["DELETE"]
    )

    # users' forms
    app.add_url_rule(
        "/forms/<hashid>.<format>", view_func=fv.export_submissions, methods=["GET"]
    )
    app.add_url_rule(
        "/api-int/forms/whitelabel/preview",
        view_func=fa.custom_template_preview_render,
        methods=["POST"],
    )
    app.add_url_rule("/api-int/forms", view_func=fa.list_forms, methods=["GET"])
    app.add_url_rule("/api-int/forms", view_func=fa.create_form, methods=["POST"])
    app.add_url_rule("/api-int/forms/<hashid>", view_func=fa.get_form, methods=["GET"])
    app.add_url_rule(
        "/api-int/forms/<hashid>", view_func=fa.update_form, methods=["PATCH"]
    )
    app.add_url_rule(
        "/api-int/forms/<hashid>", view_func=fa.delete_form, methods=["DELETE"]
    )
    app.add_url_rule(
        "/api-int/forms/<hashid>/fields", view_func=fa.list_fields, methods=["GET"]
    )
    app.add_url_rule(
        "/api-int/forms/<hashid>/rules",
        view_func=fa.add_or_update_rule,
        methods=["POST"],
    )
    app.add_url_rule(
        "/api-int/forms/<hashid>/rules/<ruleid>",
        view_func=fa.add_or_update_rule,
        methods=["PUT"],
    )
    app.add_url_rule(
        "/api-int/forms/<hashid>/rules/<ruleid>",
        view_func=fa.delete_rule,
        methods=["DELETE"],
    )
    app.add_url_rule(
        "/api-int/forms/<hashid>/submissions",
        view_func=fa.submission_list,
        methods=["GET"],
    )
    app.add_url_rule(
        "/api-int/spam", view_func=fa.mark_submission_spam, methods=["PATCH"]
    )
    app.add_url_rule(
        "/api-int/forms/<hashid>/reset-apikey",
        view_func=fa.reset_apikey,
        methods=["POST"],
    )
    app.add_url_rule(
        "/api-int/forms/<hashid>/submissions",
        view_func=fa.submission_delete,
        methods=["DELETE"],
    )
    app.add_url_rule(
        "/api-int/forms/<hashid>/submissions",
        view_func=fa.submission_set,
        methods=["PATCH"],
    )
    app.add_url_rule(
        "/api-int/forms/<hashid>/whitelabel",
        view_func=fa.custom_template_set,
        methods=["PUT"],
    )

    # plugins
    app.add_url_rule(
        "/fragment-postmessage", view_func=pv.fragment_postmessage, methods=["GET"]
    )
    app.add_url_rule(
        "/forms/<hashid>/plugins/google-sheets/auth",
        view_func=pv.google_call,
        methods=["GET"],
    )
    app.add_url_rule("/callback/google", view_func=pv.google_callback, methods=["GET"])
    app.add_url_rule(
        "/forms/<hashid>/plugins/trello/auth", view_func=pv.trello_call, methods=["GET"]
    )
    app.add_url_rule(
        "/forms/<hashid>/plugins/slack/auth", view_func=pv.slack_call, methods=["GET"]
    )
    app.add_url_rule("/callback/slack", view_func=pv.slack_callback, methods=["GET"])
    app.add_url_rule(
        "/forms/<hashid>/plugins/mailchimp/auth",
        view_func=pv.mailchimp_call,
        methods=["GET"],
    )
    app.add_url_rule(
        "/mark-spam", "mark-spam", view_func=fv.spam_marking_page, methods=["GET"]
    )
    app.add_url_rule(
        "/callback/mailchimp", view_func=pv.mailchimp_callback, methods=["GET"]
    )

    app.add_url_rule(
        "/api-int/forms/<hashid>/plugins/<kind>",
        view_func=pa.plugin_delete,
        methods=["DELETE"],
    )
    app.add_url_rule(
        "/api-int/forms/<hashid>/plugins/<kind>",
        view_func=pa.plugin_update,
        methods=["PATCH"],
    )
    app.add_url_rule(
        "/api-int/forms/<hashid>/plugins/trello",
        view_func=pa.trello_load_options,
        methods=["GET"],
    )
    app.add_url_rule(
        "/api-int/forms/<hashid>/plugins/trello",
        view_func=pa.trello_create,
        methods=["POST"],
    )
    app.add_url_rule(
        "/api-int/forms/<hashid>/plugins/trello",
        view_func=pa.trello_set,
        methods=["PUT"],
    )
    app.add_url_rule(
        "/api-int/forms/<hashid>/plugins/mailchimp",
        view_func=pa.mailchimp_load_lists,
        methods=["GET"],
    )
    app.add_url_rule(
        "/api-int/forms/<hashid>/plugins/mailchimp",
        view_func=pa.mailchimp_set,
        methods=["PUT"],
    )
    app.add_url_rule(
        "/api-int/forms/<hashid>/plugins/webhook",
        view_func=pa.webhook_create,
        methods=["POST"],
    )

    # public api
    app.add_url_rule("/api/0/forms/<hashid>", view_func=fa.v0_form, methods=["GET"])
    app.add_url_rule(
        "/api/0/forms/<hashid>/submissions",
        view_func=fa.v0_submissions,
        methods=["GET"],
    )

    # incoming webhooks
    app.add_url_rule("/webhooks/stripe", view_func=uv.stripe_webhook, methods=["POST"])

    # any other static pages and 404
    app.add_url_rule(
        "/<path:template>", "default", view_func=sv.default, methods=["GET"]
    )
