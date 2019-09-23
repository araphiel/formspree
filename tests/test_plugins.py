import json

from formspree import settings
from formspree.plugins.models import PluginKind

from .helpers import create_user_and_form


def test_webhook(client, msend, requests_mock, mocker):
    m_dispatch = mocker.patch("formspree.plugins.helpers.dispatch_webhook.delay")

    user, form = create_user_and_form(client)

    # create a subscription
    requests_mock.post("https://x.com/", headers={"X-Hook-Secret": form.hashid})
    r = client.post(
        f"/api-int/forms/{form.hashid}/plugins/webhook",
        data=json.dumps({"target_url": "https://x.com/"}),
        headers={"Content-Type": "application/json", "Referer": settings.SERVICE_URL},
    )
    assert r.status_code == 201

    # submit the form multiple times
    for i, name in enumerate(["anna", "bradley", "camila", "dylan"]):
        r = client.post(
            "/" + form.hashid,
            data={"index": i, "name": name},
            headers={"Referer": "http://example.com"},
        )
        assert r.status_code == 302

    # the webhook must have been dispatched multiple times
    assert m_dispatch.call_count == 4
    assert m_dispatch.call_args_list[0][0][1] == "https://x.com/"
    assert m_dispatch.call_args_list[0][0][2] == form.hashid
    assert m_dispatch.call_args_list[0][0][4] == {"index": "0", "name": "anna"}
    assert m_dispatch.call_args_list[1][0][4] == {"index": "1", "name": "bradley"}
    assert m_dispatch.call_args_list[2][0][4] == {"index": "2", "name": "camila"}


def test_mailchimp(client, msend, requests_mock):
    user, form = create_user_and_form(client)

    # get mailchimp auth url
    r = client.get(f"/forms/{form.hashid}/plugins/mailchimp/auth")
    assert r.status_code == 302
    assert r.location.startswith("https://login.mailchimp.com/oauth2/authorize")

    # authorize mailchimp
    requests_mock.post(
        "https://login.mailchimp.com/oauth2/token", json={"access_token": "xyz"}
    )
    requests_mock.get(
        "https://login.mailchimp.com/oauth2/metadata",
        json={"api_endpoint": "https://fakeapi.mailchimp.com", "dc": "fakeapi"},
    )
    r = client.get(f"/callback/mailchimp?state={form.hashid}")
    assert r.status_code == 200

    plugin = form.plugins.filter_by(kind=PluginKind.mailchimp).first()
    assert plugin is not None
    assert plugin.plugin_data == {
        "dc": "fakeapi",
        "api_endpoint": "https://fakeapi.mailchimp.com",
    }

    # set list and enable mailchimp
    r = client.put(
        f"/api-int/forms/{form.hashid}/plugins/mailchimp",
        data=json.dumps({"list_id": "ihj"}),
        headers={"Referer": settings.SERVICE_URL, "Content-Type": "application/json"},
    )
    assert r.status_code == 200
    plugin = form.plugins.filter_by(kind=PluginKind.mailchimp).first()
    assert plugin.plugin_data["list_id"] == "ihj"

    # on each mailchimp call we get the list merge_fields
    requests_mock.get(
        f"{plugin.plugin_data['api_endpoint']}/3.0/lists/{plugin.plugin_data['list_id']}/merge-fields",
        json={"merge_fields": [{"tag": "FULLNAME"}, {"tag": "LNAME"}]},
    )
    # and the double-optin thing
    requests_mock.get(
        f"{plugin.plugin_data['api_endpoint']}/3.0/lists/{plugin.plugin_data['list_id']}",
        json={"double_optin": True},
    )
    # then we call the api to include a new address
    requests_mock.post(
        f"{plugin.plugin_data['api_endpoint']}/3.0/lists/{plugin.plugin_data['list_id']}",
        json={"double_optin": True},
    )

    # submit the form multiple times
    for i, name in enumerate(["anna", "bradley", "camila", "dylan"]):
        r = client.post(
            "/" + form.hashid,
            data={"_replyto": f"{name}@test.com", "name": name},
            headers={"Referer": "http://example.com"},
        )
        assert r.status_code == 302
        requests_mock.last_request.json()["members"][0][
            "email_address"
        ] == f"{name}@test.com"
        requests_mock.last_request.json()["members"][0]["merge_fields"] == {
            "FULLNAME": name,
            "LNAME": name,
        }
        requests_mock.last_request.json()["members"][0]["status_if_new"] == "pending"

    assert requests_mock.call_count == 2 + 8 + 4


def test_trello(client, msend, requests_mock):
    user, form = create_user_and_form(client)

    # get trello auth url
    r = client.get(f"/forms/{form.hashid}/plugins/trello/auth")
    assert r.status_code == 302
    assert r.location.startswith("https://trello.com/1/authorize")

    # all the authorization flow happens between the client and trello
    # the server just gets a trello token somehow
    r = client.post(
        f"/api-int/forms/{form.hashid}/plugins/trello",
        data=json.dumps({"token": "mno"}),
        headers={"Content-Type": "application/json", "Referer": settings.SERVICE_URL},
    )
    assert r.status_code == 201

    # set board/list and enable trello
    r = client.put(
        f"/api-int/forms/{form.hashid}/plugins/trello",
        data=json.dumps({"board_id": "efg", "list_id": "ihj"}),
        headers={"Referer": settings.SERVICE_URL, "Content-Type": "application/json"},
    )
    assert r.status_code == 200
    plugin = form.plugins.filter_by(kind=PluginKind.trello).first()
    assert plugin.access_token == "mno"
    assert plugin.plugin_data["board_id"] == "efg"
    assert plugin.plugin_data["list_id"] == "ihj"

    # submit the form multiple times
    requests_mock.post("https://api.trello.com/1/cards")
    for i, name in enumerate(["anna", "bradley", "camila", "dylan"]):
        r = client.post(
            "/" + form.hashid,
            data={"_replyto": f"{name}@test.com", "name": name, "message": i},
            headers={"Referer": "http://example.com"},
        )
        assert f"from form {form.name}" in requests_mock.last_request.qs["name"][0]
        assert r.status_code == 302

    assert requests_mock.call_count == 4
