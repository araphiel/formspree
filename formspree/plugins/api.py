import datetime

import requests
from flask import request, jsonify, g
from flask_login import login_required

from formspree import settings
from formspree.app_globals import DB, redis_store
from formspree.utils import prevent_xsrf, requires_feature
from formspree.forms.helpers import form_control
from .models import Plugin, PluginKind
from .helpers import webhook_probe, PLUGINFAILURE_KEY


@prevent_xsrf
@login_required
@form_control
@requires_feature("plugins")
def webhook_create(hashid, form):
    data = request.get_json()

    g.log = g.log.new(form=form.hashid, target_url=data["target_url"])
    g.log.debug("Creating webhook plugin.")
    plugin = Plugin(form_id=form.id, kind=PluginKind.webhook)
    plugin.plugin_data = {"target_url": data["target_url"]}

    success = webhook_probe(form, plugin)

    if success:
        DB.session.add(plugin)
        DB.session.commit()
        g.log.debug("Webhook created successfully.")
        return jsonify({"ok": True}), 201

    return (
        jsonify(
            {
                "ok": False,
                "error": (
                    "Confirmation failed. "
                    "Expected the handler to mirror the X-Hook-Secret header."
                ),
            }
        ),
        400,
    )


@prevent_xsrf
@login_required
@form_control
@requires_feature("plugins")
def trello_create(hashid, form):
    data = request.get_json()

    g.log = g.log.new(form=form.hashid)
    g.log.debug("Creating Trello plugin.")

    plugin = Plugin(form_id=form.id, kind=PluginKind.trello)
    plugin.access_token = data["token"]
    plugin.enabled = False
    DB.session.add(plugin)
    DB.session.commit()

    return jsonify({"ok": True}), 201


@prevent_xsrf
@login_required
@form_control
@requires_feature("plugins")
def trello_load_options(hashid, form):
    plugin = form.plugins.filter_by(kind=PluginKind.trello).first()
    if not plugin:
        return jsonify({"error": "Trello plugin doesn't exist for this form."}), 404

    # fetch boards and lists to choose from
    r = requests.get(
        "https://api.trello.com/1/members/me/boards",
        params={
            "key": settings.TRELLO_API_KEY,
            "token": plugin.access_token,
            "filter": "open",
            "fields": "id,name,pinned,dateLastActivity,url",
            "lists": "all",
            "list_fields": "id,name,closed,pos",
        },
    )
    if not r.ok:
        g.log.debug("Trello load options failure.", text=r.text)
        return jsonify({"error": "Unable to fetch board data from Trello."}), 500

    return jsonify(
        [
            {
                "name": b["name"],
                "id": b["id"],
                "lists": [
                    {"name": l["name"], "id": l["id"]}
                    for l in sorted(b["lists"], key=lambda l: (l["closed"], l["pos"]))
                ],
            }
            for b in sorted(
                r.json(),
                key=lambda b: (
                    b["pinned"],
                    (
                        b["dateLastActivity"]
                        or datetime.datetime.fromtimestamp(
                            int(b["id"][0:8], 16)
                        ).isoformat()
                    ),
                ),
                reverse=True,
            )
        ]
    )


@prevent_xsrf
@login_required
@form_control
@requires_feature("plugins")
def trello_set(hashid, form):
    plugin = form.plugins.filter_by(kind=PluginKind.trello).first()
    if not plugin:
        return jsonify({"error": "Trello plugin doesn't exist for this form."}), 404

    data = request.get_json()
    plugin.plugin_data = {"board_id": data["board_id"], "list_id": data["list_id"]}
    plugin.enabled = True
    DB.session.add(plugin)
    DB.session.commit()

    return jsonify({"ok": True})


@prevent_xsrf
@login_required
@form_control
@requires_feature("plugins")
def mailchimp_load_lists(hashid, form):
    plugin = form.plugins.filter_by(kind=PluginKind.mailchimp).first()
    if not plugin:
        return jsonify({"error": "Mailchimp plugin doesn't exist for this form."}), 404

    # fetch lists to choose from
    r = requests.get(
        plugin.plugin_data["api_endpoint"] + "/3.0/lists",
        auth=("anystring", plugin.access_token),
    )
    if not r.ok:
        g.log.debug("Mailchimp load options failure.", text=r.text)
        return jsonify({"error": "Unable to fetch board data from Mailchimp."}), 500

    return jsonify([{"id": l["id"], "name": l["name"]} for l in r.json()["lists"]])


@prevent_xsrf
@login_required
@form_control
@requires_feature("plugins")
def mailchimp_set(hashid, form):
    plugin = form.plugins.filter_by(kind=PluginKind.mailchimp).first()
    if not plugin:
        return jsonify({"error": "Mailchimp plugin doesn't exist for this form."}), 404

    data = request.get_json()
    plugin.plugin_data["list_id"] = data["list_id"]
    plugin.enabled = True
    DB.session.add(plugin)
    DB.session.commit()

    return jsonify({"ok": True})


@prevent_xsrf
@login_required
@form_control
@requires_feature("plugins")
def plugin_update(hashid, form, kind):
    plugin = form.plugins.filter_by(kind=kind).first()
    if plugin:
        data = request.get_json()

        for attr in ["enabled"]:
            if attr in data:
                setattr(plugin, attr, data[attr])

        DB.session.add(plugin)
        DB.session.commit()

        # reset failure count
        redis_store.delete(PLUGINFAILURE_KEY(id=plugin.id))

        return jsonify({"ok": True})
    else:
        return jsonify({"ok": False}), 400


@prevent_xsrf
@login_required
@form_control
def plugin_delete(hashid, form, kind):
    plugin = form.plugins.filter_by(kind=kind).first()
    if plugin:
        DB.session.delete(plugin)
        DB.session.commit()
        return jsonify({"ok": True})
    else:
        return jsonify({"ok": False}), 400
