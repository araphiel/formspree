import json
import datetime

import requests
from googleapiclient.discovery import build
from flask import g, render_template

from formspree.app_globals import celery, redis_store

PLUGINFAILURE_KEY = "plugin-failure:{id}".format
HUMAN_DATE = "%B %d %Y %I:%M:%S %p"


def isodate_to_spreadsheet(date):
    if type(date) is str:
        date = datetime.datetime.strptime(date, "%Y-%m-%dT%H:%M:%S.%f")

    return date.strftime("%Y-%m-%d %H:%M:%S")


def format_value(value):
    if type(value) == str:
        return value
    return json.dumps(value)


def script_data(data):
    return render_template("static_pages/postmessage.html", data=data)


def script_error(error_id):
    return script_data({"error": error_id})


def call_it_a_failure(plugin_id):
    key = PLUGINFAILURE_KEY(id=plugin_id)
    nfailures = redis_store.incr(key)
    g.log.warn("Call it a failure", key=key, nfailures=nfailures)


def webhook_probe(form, plugin):
    """
    Sends a blank request with X-Hook-Secret: <hashid>
    and expects that same X-Hook-Secret in the response.
    """
    try:
        r = requests.post(
            plugin.plugin_data["target_url"],
            headers={"X-Hook-Secret": form.hashid},
            timeout=10,
            allow_redirects=False,
        )
    except Exception as e:
        g.log.debug("Webhook confirmation failed.", exc=e)
        return False

    if not r.ok or r.headers.get("X-Hook-Secret") != form.hashid:
        g.log.debug("Webhook confirmation failed.")
        return False

    return True


@celery.task
def dispatch_webhook(
    plugin_id,
    target_url,
    form_hashid,
    submitted_at,
    submission_data,
    sorted_keys,
    attempt=0,
):
    try:
        g.log.info(
            "Attempting Webhook.", url=target_url, plugin=plugin_id, attempt=attempt
        )
        r = requests.post(
            target_url,
            headers={"Content-Type": "application/json"},
            data=json.dumps(
                {
                    "form": form_hashid,
                    "submission": dict(_date=submitted_at, **submission_data),
                    "keys": sorted_keys,
                }
            ),
            timeout=3,
            allow_redirects=False,
        )
        r.raise_for_status()
    except requests.exceptions.RequestException as e:
        if attempt < 4:
            g.log.debug("Will try again.", exc=e, plugin=plugin_id)
            dispatch_webhook.apply_async(
                (
                    plugin_id,
                    target_url,
                    form_hashid,
                    submitted_at,
                    submission_data,
                    sorted_keys,
                    attempt + 1,
                ),
                countdown=2 ** ((attempt + 1) * 4),
            )
        else:
            call_it_a_failure(plugin_id)
            return


def make_format_submissions(sheet_id, num_fields, num_submissions):
    return {
        "updateCells": {
            "start": {"rowIndex": 1, "columnIndex": 0, "sheetId": sheet_id},
            "rows": [
                {
                    "values": [
                        {
                            "userEnteredFormat": {
                                "wrapStrategy": "WRAP",
                                "textFormat": {"fontFamily": "Cambria"},
                            }
                        }
                        for _ in range(num_fields)
                    ]
                }
                for _ in range(num_submissions)
            ],
            "fields": "userEnteredFormat(wrapStrategy,textFormat.fontFamily)",
        }
    }


def make_format_header(sheet_id, num_fields):
    return {
        "updateCells": {
            "start": {"rowIndex": 0, "columnIndex": 0, "sheetId": sheet_id},
            "rows": [
                {
                    "values": [
                        {
                            "userEnteredFormat": {
                                "wrapStrategy": "CLIP",
                                "textFormat": {"fontFamily": "Poppins"},
                                "horizontalAlignment": "CENTER",
                            }
                        }
                        for _ in range(num_fields)
                    ]
                }
            ],
            "fields": "userEnteredFormat(wrapStrategy,textFormat.fontFamily, horizontalAlignment)",
        }
    }


def make_format_protected(sheet_id):
    return {
        "addProtectedRange": {
            "protectedRange": {
                "description": "Data being updated by Formspree.",
                "range": {"sheetId": sheet_id, "startRowIndex": 0},
                "warningOnly": True,
            }
        }
    }


def make_format_autoresize(sheet_id):
    return {
        "autoResizeDimensions": {
            "dimensions": {
                "sheetId": sheet_id,
                "dimension": "COLUMNS",
                "startIndex": 0,
                "endIndex": 0,
            }
        }
    }


def create_google_sheet(form, title, credentials):
    sheets = build(
        "sheets", "v4", credentials=credentials, cache_discovery=False
    ).spreadsheets()

    submissions, fields = form.submissions_with_fields(with_ids=False)

    # create the sheet
    params = {
        "developerMetadata": [
            {
                "metadataId": 1,
                "visibility": "DOCUMENT",
                "metadataKey": "formId",
                "metadataValue": str(form.id),
            },
            {
                "metadataId": 2,
                "visibility": "DOCUMENT",
                "metadataKey": "formHashid",
                "metadataValue": form.hashid,
            },
        ],
        "properties": {"title": title},
        "sheets": [
            {
                "properties": {
                    "title": title,
                    "tabColor": {
                        "red": 196 / 255,
                        "green": 0,
                        "blue": 26 / 255,
                        "alpha": 1,
                    },
                    "gridProperties": {
                        "columnCount": len(fields),
                        "rowCount": 1 + len(submissions),
                    },
                }
            }
        ],
    }
    response = sheets.create(body=params).execute()
    spreadsheet_id = response["spreadsheetId"]
    sheet_id = response["sheets"][0]["properties"]["sheetId"]

    range_name = "%s!A:ZZ" % title

    def row(s):
        r = [format_value(s.get(k, "")) for k in fields]
        r[0] = isodate_to_spreadsheet(r[0])
        return r

    values = [row(s) for s in reversed(submissions)]

    # post initial values as USER_ENTERED
    sheets.values().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={
            "valueInputOption": "USER_ENTERED",
            "data": [{"range": range_name, "values": [fields] + values}],
        },
    ).execute()

    # format headers, format body, resize first column and protect the sheet

    update_body = {"requests": []}

    update_body["requests"].append(make_format_header(sheet_id, len(fields)))
    update_body["requests"].append(make_format_protected(sheet_id))

    if len(submissions) > 0:
        update_body["requests"].append(
            make_format_submissions(sheet_id, len(fields), len(submissions))
        )
        update_body["requests"].append(make_format_autoresize(sheet_id))

    sheets.batchUpdate(spreadsheetId=spreadsheet_id, body=update_body).execute()

    return spreadsheet_id, sheet_id
