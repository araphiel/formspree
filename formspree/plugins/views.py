import json
import requests
from urllib.parse import urlencode

import google.oauth2.credentials
import google_auth_oauthlib.flow
from flask_login import current_user, login_required
from flask import request, url_for, redirect, session

from formspree import settings
from formspree.utils import requires_feature
from formspree.app_globals import DB
from formspree.forms.models import Form
from .helpers import script_data, script_error, create_google_sheet
from .models import Plugin, PluginKind


@login_required
@requires_feature("plugins")
def google_call(hashid):
    form = Form.get_with(hashid=hashid)
    session["ggl:form"] = form.hashid

    hint = form.email
    if not form.email.endswith("@gmail.com") and current_user.email.endswith(
        "@gmail.com"
    ):
        hint = current_user.email

    flow = google_auth_oauthlib.flow.Flow.from_client_config(
        settings.GOOGLE_CLIENT_CONFIG,
        scopes=["https://www.googleapis.com/auth/drive.file"],
    )
    flow.redirect_uri = url_for(
        "google_callback",
        _external=True,
        _scheme="https",  # can't figure out how to get this to honor PREFERRED_URL_SCHEME
    )
    authorization_url, _ = flow.authorization_url(
        access_type="offline",
        login_hint=hint,
        prompt="consent",
        state=hashid,
        include_granted_scopes="true",
    )
    return redirect(authorization_url)


@login_required
@requires_feature("plugins")
def google_callback():
    hashid = session["ggl:form"]
    del session["ggl:form"]
    if hashid != request.args.get("state"):
        return script_error("oauth-failed")

    form = Form.get_with(hashid=hashid)

    flow = google_auth_oauthlib.flow.Flow.from_client_config(
        settings.GOOGLE_CLIENT_CONFIG,
        state=hashid,
        scopes=["https://www.googleapis.com/auth/drive.file"],
    )

    flow.redirect_uri = url_for("google_callback", _external=True, _scheme="https")

    flow.fetch_token(authorization_response=request.url.replace("http://", "https://"))

    plugin = Plugin(form_id=form.id, kind=PluginKind.google_sheets)
    plugin.access_token = json.dumps(
        {
            "token": flow.credentials.token,
            "refresh_token": flow.credentials.refresh_token,
            "token_uri": flow.credentials.token_uri,
            "id_token": flow.credentials.id_token,
            "client_id": flow.credentials.client_id,
            "client_secret": flow.credentials.client_secret,
        }
    )

    spreadsheet_title = (
        form.name
        if form.name
        else f"{settings.SERVICE_NAME} submissions for {form.hashid}"
    )[:128]

    google_creds = json.loads(plugin.access_token)
    credentials = google.oauth2.credentials.Credentials(**google_creds)
    spreadsheet_id, worksheet_id = create_google_sheet(
        form, spreadsheet_title, credentials
    )

    plugin.plugin_data = {
        "spreadsheet_id": spreadsheet_id,
        "worksheet_id": worksheet_id,
    }
    DB.session.add(plugin)
    DB.session.commit()

    return script_data({"spreadsheet_id": spreadsheet_id})


@login_required
@requires_feature("plugins")
def trello_call(hashid):
    form = Form.get_with(hashid=hashid)
    session["trl:form"] = form.hashid

    return redirect(
        "https://trello.com/1/authorize?{}".format(
            urlencode(
                {
                    "return_url": url_for(
                        "fragment_postmessage", _external=True, _scheme="https"
                    ),
                    "expiration": "never",
                    "scope": "read,write",
                    "name": settings.SERVICE_NAME,
                    "key": settings.TRELLO_API_KEY,
                    "callback_method": "fragment",
                    "response_type": "fragment",
                }
            )
        )
    )


@login_required
@requires_feature("plugins")
def slack_call(hashid):
    form = Form.get_with(hashid=hashid)
    session["slk:form"] = form.hashid

    return redirect(
        "https://slack.com/oauth/authorize?"
        + urlencode(
            {
                "client_id": settings.SLACK_CLIENT_ID,
                "scope": "incoming-webhook",
                "redirect_uri": url_for(
                    "slack_callback", _external=True, _scheme="https"
                ),
                "state": form.hashid,
            }
        )
    )


@login_required
@requires_feature("plugins")
def slack_callback():
    error = request.args.get("error")
    if error:
        return script_error(error if error == "access-denied" else "oauth-failed")

    hashid = session["slk:form"]
    del session["slk:form"]
    if hashid != request.args.get("state"):
        return script_error("oauth-failed")

    code = request.args.get("code")
    r = requests.get(
        "https://slack.com/api/oauth.access",
        params={
            "client_id": settings.SLACK_CLIENT_ID,
            "client_secret": settings.SLACK_CLIENT_SECRET,
            "code": code,
            "redirect_uri": url_for("slack_callback", _external=True, _scheme="https"),
        },
    )
    if not r.ok:
        return script_error("oauth-failed")

    data = r.json()

    form = Form.get_with(hashid=hashid)
    plugin = Plugin(form_id=form.id, kind=PluginKind.slack)
    plugin.access_token = data["access_token"]
    plugin.plugin_data = {
        "team_name": data["team_name"],
        "team_id": data["team_id"],
        "incoming_webhook": data["incoming_webhook"],
    }
    plugin.enabled = True
    DB.session.add(plugin)
    DB.session.commit()

    return script_data(
        {"channel": data["incoming_webhook"]["channel"], "team": data["team_name"]}
    )


@login_required
@requires_feature("plugins")
def mailchimp_call(hashid):
    form = Form.get_with(hashid=hashid)
    session["mcp:form"] = form.hashid

    return redirect(
        "https://login.mailchimp.com/oauth2/authorize?"
        + urlencode(
            {
                "response_type": "code",
                "client_id": settings.MAILCHIMP_CLIENT_ID,
                "redirect_uri": url_for(
                    "mailchimp_callback", _external=True, _scheme="https"
                ),
                "state": form.hashid,
            }
        )
    )


@login_required
@requires_feature("plugins")
def mailchimp_callback():
    error = request.args.get("error")
    if error:
        return script_error(error if error == "access-denied" else "oauth-failed")

    hashid = session["mcp:form"]
    del session["mcp:form"]
    if hashid != request.args.get("state"):
        return script_error("oauth-failed")

    code = request.args.get("code")
    r = requests.post(
        "https://login.mailchimp.com/oauth2/token",
        data={
            "grant_type": "authorization_code",
            "client_id": settings.MAILCHIMP_CLIENT_ID,
            "client_secret": settings.MAILCHIMP_CLIENT_SECRET,
            "code": code,
            "redirect_uri": url_for(
                "mailchimp_callback", _external=True, _scheme="https"
            ),
        },
    )
    if not r.ok:
        return script_error("oauth-failed")

    data = r.json()
    form = Form.get_with(hashid=hashid)
    plugin = Plugin(form_id=form.id, kind=PluginKind.mailchimp)

    r = requests.get(
        "https://login.mailchimp.com/oauth2/metadata",
        headers={"Authorization": "OAuth " + data["access_token"]},
    )
    if not r.ok:
        return script_error("oauth-failed")

    meta = r.json()

    plugin.access_token = data["access_token"]
    plugin.plugin_data = {"api_endpoint": meta["api_endpoint"], "dc": meta["dc"]}
    plugin.enabled = False
    DB.session.add(plugin)
    DB.session.commit()

    return script_data({"ok": True})


def fragment_postmessage():
    return script_data({})
