import re
import uuid
import json

import requests
import google.oauth2.credentials
import googleapiclient.errors
from googleapiclient.discovery import build
from sqlalchemy import UniqueConstraint
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.dialects.postgresql import JSONB
from flask import g, url_for, render_template

from formspree import settings
from formspree.app_globals import DB, redis_store
from formspree.email_templates import render_email
from formspree.utils import send_email, is_valid_email
from .helpers import (
    dispatch_webhook,
    call_it_a_failure,
    format_value,
    isodate_to_spreadsheet,
    PLUGINFAILURE_KEY,
    HUMAN_DATE,
    make_format_submissions,
    make_format_protected,
    make_format_autoresize,
)


class PluginKind(DB.Enum):
    google_sheets = "google-sheets"
    webhook = "webhook"
    trello = "trello"
    slack = "slack"
    mailchimp = "mailchimp"

    kinds = [google_sheets, webhook, trello, slack, mailchimp]


class Plugin(DB.Model):
    __tablename__ = "plugins"

    id = DB.Column(DB.String, primary_key=True)
    kind = DB.Column(DB.Enum(*PluginKind.kinds, name="pluginkind"), nullable=False)
    enabled = DB.Column(DB.Boolean, default=True, nullable=False)
    form_id = DB.Column(
        DB.Integer, DB.ForeignKey("forms.id"), nullable=False, index=True
    )
    access_token = DB.Column(DB.String)
    plugin_data = DB.Column(MutableDict.as_mutable(JSONB))

    # hidden 'form' property maps to the form referenced at form_id
    # this dirty magic is defined in the subscriptions DB.Relationship at Form.

    __table_args__ = (
        UniqueConstraint("form_id", "kind", name="one_plugin_of_each_kind"),
        {},
    )

    def __init__(self, form_id, kind):
        self.id = str(uuid.uuid4())
        self.form_id = form_id
        self.kind = kind

    def serialize(self):
        return {
            "kind": self.kind,
            "enabled": self.enabled,
            "authed": bool(self.access_token) or self.kind == "webhook",
            "info": self.plugin_data or {},
        }

    def external_failure(self, submission):
        call_it_a_failure(self.id)
        submission.append_error("Failed to dispatch plugin.", plugin_kind=self.kind)

    def dispatch(self, submission, sorted_keys):
        key = PLUGINFAILURE_KEY(id=self.id)
        nfailures = redis_store.get(key) or b"0"
        nfailures = int(nfailures.decode("ascii"))

        if nfailures >= settings.PLUGINS_MAX_FAILURES:
            g.log.debug(
                "Disabling plugin due to an excess of failures.",
                kind=self.kind,
                form=self.form_id,
                failures=nfailures,
            )
            redis_store.delete(key)
            self.enabled = False
            DB.session.add(self)
            DB.session.commit()

            # notify them through email
            render_args = dict(
                plugin_kind=self.kind,
                form_name=self.form.hashid,
                nfailures=nfailures,
                form_plugins_link=url_for(
                    "form-page-section",
                    hashid=self.form.hashid,
                    s="plugins",
                    _external=True,
                ),
            )
            send_email(
                to=self.form.email,
                subject="Plugin disabled due to delivery failure",
                text=render_template(
                    "email/plugin-disabled-notification.txt", **render_args
                ),
                html=render_email("plugin-disabled-notification.html", **render_args),
                sender=settings.DEFAULT_SENDER,
            )
        else:
            g.log.debug(
                "Dispatching submission to plugin.",
                kind=self.kind,
                form=self.form_id,
                failures=nfailures,
            )
            {
                PluginKind.google_sheets: self.dispatch_google_sheets,
                PluginKind.webhook: self.dispatch_webhook,
                PluginKind.trello: self.dispatch_trello,
                PluginKind.slack: self.dispatch_slack,
                PluginKind.mailchimp: self.dispatch_mailchimp,
            }[self.kind](submission, sorted_keys)

    def dispatch_webhook(self, submission, sorted_keys=None):
        dispatch_webhook.delay(
            self.id,
            self.plugin_data["target_url"],
            self.form.hashid,
            submission.submitted_at,
            submission.data,
            sorted_keys,
        )

    def dispatch_google_sheets(self, submission, sorted_keys):
        google_creds = json.loads(self.access_token)
        credentials = google.oauth2.credentials.Credentials(**google_creds)

        sheets = build(
            "sheets", "v4", credentials=credentials, cache_discovery=False
        ).spreadsheets()

        try:
            spreadsheet_data = sheets.get(
                spreadsheetId=self.plugin_data["spreadsheet_id"]
            ).execute()
            worksheet_exists = False
            worksheet_name = "Sheet1"
            worksheet_rows = 0
            for wk in spreadsheet_data["sheets"]:
                if wk["properties"]["sheetId"] == self.plugin_data["worksheet_id"]:
                    worksheet_exists = True
                    worksheet_name = wk["properties"]["title"]
                    worksheet_rows = wk["properties"]["gridProperties"]["rowCount"]
                    break

            if not worksheet_exists:
                # delete the plugin and send an email notice
                pass

            range_name = "%s!A1:ZZ1" % worksheet_name
            toprow = (
                sheets.values()
                .get(
                    spreadsheetId=self.plugin_data["spreadsheet_id"],
                    range=range_name,
                    valueRenderOption="UNFORMATTED_VALUE",
                )
                .execute()
            )

            old_keys = []
            new_keys = []
            if "values" in toprow:
                old_keys = toprow["values"][0]
                new_keys = old_keys + [k for k in sorted_keys if k not in old_keys]
            else:
                new_keys = sorted_keys

            if "_date" not in new_keys:
                new_keys.insert(0, "_date")

            if new_keys != old_keys:
                try:
                    sheets.values().update(
                        spreadsheetId=self.plugin_data["spreadsheet_id"],
                        range=range_name,
                        body={"range": range_name, "values": [new_keys]},
                        valueInputOption="USER_ENTERED",
                    ).execute()
                except googleapiclient.errors.Error as e:
                    g.log.warning(
                        "Error updating sheet columns.", plugin_id=self.id, exc=e
                    )
                    self.external_failure(submission)
                    return

            values = [format_value(submission.data.get(k, "")) for k in new_keys]
            values[0] = isodate_to_spreadsheet(submission.submitted_at)

            g.log.info(
                "Pushing to Google Sheet.",
                sheet=self.plugin_data["spreadsheet_id"],
                wk=self.plugin_data["worksheet_id"],
                plugin=self.id,
            )
            sheets.values().append(
                spreadsheetId=self.plugin_data["spreadsheet_id"],
                range=range_name,
                body={"range": range_name, "values": [values]},
                valueInputOption="USER_ENTERED",
            ).execute()

            if worksheet_rows == 1:
                # adding our first submission, so format submissions
                update_body = {"requests": []}
                update_body["requests"].append(
                    make_format_submissions(
                        self.plugin_data["worksheet_id"], len(new_keys), 1
                    )
                )
                update_body["requests"].append(
                    make_format_protected(self.plugin_data["worksheet_id"])
                )
                update_body["requests"].append(
                    make_format_autoresize(self.plugin_data["worksheet_id"])
                )
                sheets.batchUpdate(
                    spreadsheetId=self.plugin_data["spreadsheet_id"], body=update_body
                ).execute()
        except googleapiclient.errors.Error as e:
            g.log.warning(
                "Error pushing row to Google Sheet.", plugin_id=self.id, exc=e
            )
            self.external_failure(submission)
            return

    def dispatch_trello(self, submission, sorted_keys):
        g.log.info(
            "Creating Trello card.",
            board=self.plugin_data["board_id"],
            list=self.plugin_data["list_id"],
            plugin=self.id,
        )

        try:
            r = requests.post(
                "https://api.trello.com/1/cards",
                params={
                    "key": settings.TRELLO_API_KEY,
                    "token": self.access_token,
                    "name": submission.data.get(
                        "_subject",
                        "Submission from form {}".format(
                            self.form.name or self.form.hashid
                        ),
                    ),
                    "pos": "top",
                    "desc": "Submitted at {}: \n\n".format(
                        submission.submitted_at.strftime(HUMAN_DATE)
                    )
                    + "\n".join(
                        [
                            "__{}__: {}".format(k, format_value(submission.data[k]))
                            for k in sorted_keys
                        ]
                    )
                    + "\n\n"
                    + url_for(
                        "form-page-section",
                        hashid=self.form.hashid,
                        s="submissions",
                        _external=True,
                        _scheme="https",
                    ),
                    "due": submission.submitted_at.isoformat(),
                    "idList": self.plugin_data["list_id"],
                },
            )
            r.raise_for_status()
        except requests.exceptions.RequestException as e:
            g.log.warning("Trello error.", exc=e, t=r.text)
            self.external_failure(submission)

    def dispatch_slack(self, submission, sorted_keys):
        g.log.info(
            "Posting to Slack.",
            team=self.plugin_data["team_name"],
            channel=self.plugin_data["incoming_webhook"]["channel"],
            plugin=self.id,
        )
        try:
            r = requests.post(
                self.plugin_data["incoming_webhook"]["url"],
                data=json.dumps(
                    {
                        "mrkdwn": True,
                        "attachments": [
                            {
                                "title": submission.data.get("_subject"),
                                "pretext": "New submission from form {}".format(
                                    self.form.name or self.form.hashid
                                ),
                                "mrkdwn_in": ["text", "pretext"],
                                "text": "\n".join(
                                    [
                                        "*{}*: {}".format(
                                            k, format_value(submission.data[k])
                                        )
                                        for k in sorted_keys
                                    ]
                                )
                                + "\n\n"
                                + url_for(
                                    "form-page-section",
                                    hashid=self.form.hashid,
                                    s="submissions",
                                    _external=True,
                                    _scheme="https",
                                ),
                            }
                        ],
                    }
                ),
                headers={"Content-Type": "application/json"},
            )
            r.raise_for_status()
        except requests.exceptions.RequestException as e:
            g.log.warning("Slack error.", exc=e, t=r.text)
            self.external_failure(submission)

    def dispatch_mailchimp(self, submission, sorted_keys=None):
        api_url = self.plugin_data["api_endpoint"]
        list_id = self.plugin_data["list_id"]
        email_address = submission.data.get(
            "_replyto", submission.data.get("email", "")
        )
        if not is_valid_email(email_address):
            g.log.debug("Mailchimp: submission data doesn't contain an email.")
            return

        g.log.info(
            "Adding to Mailchimp.", list=list_id, email=email_address, plugin=self.id
        )

        # first get merge fields
        r = requests.get(
            api_url + "/3.0/lists/" + list_id + "/merge-fields",
            auth=("anystring", self.access_token),
            headers={"Content-Type": "application/json"},
        )
        r.raise_for_status()
        fieldnames = [f["tag"] for f in r.json().get("merge_fields", [])]
        fields = {}
        name = submission.data.get("_name", submission.data.get("name"))
        if name:
            if "FULLNAME" in fieldnames:
                fields["FULLNAME"] = name
            nameparts = re.sub(r"[^\w ]", "", name).strip().split(" ")
            if "FNAME" in fieldnames:
                fields["FNAME"] = nameparts[0]
            if "LNAME" in fieldnames:
                fields["LNAME"] = nameparts[-1]
        if "_fname" in submission.data and "FNAME" in fieldnames:
            fields["FNAME"] = submission.data["_fname"]
        if "_lname" in submission.data and "LNAME" in fieldnames:
            fields["LNAME"] = submission.data["_lname"]
        if "_address" in submission.data and "ADDRESS" in fieldnames:
            fields["ADDRESS"] = submission.data["_address"]
        if "_phone" in submission.data and "PHONE" in fieldnames:
            fields["PHONE"] = submission.data["_phone"]

        # check if the list has double_optin
        r = requests.get(
            api_url + "/3.0/lists/" + list_id,
            auth=("anystring", self.access_token),
            headers={"Content-Type": "application/json"},
        )
        double_optin = r.json().get("double_optin", False) if r.ok else False

        try:
            r = requests.post(
                api_url + "/3.0/lists/" + list_id,
                auth=("anystring", self.access_token),
                data=json.dumps(
                    {
                        "members": [
                            {
                                "email_address": email_address,
                                "status_if_new": (
                                    "pending" if double_optin else "subscribed"
                                ),
                                "merge_fields": fields,
                            }
                        ],
                        "update_existing": True,
                    }
                ),
                headers={"Content-Type": "application/json"},
            )
            r.raise_for_status()
        except requests.exceptions.RequestException as e:
            g.log.warning("Mailchimp error.", exc=e, t=r.text)
            self.external_failure(submission)
