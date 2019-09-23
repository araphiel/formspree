import json
import base64

from flask_login import logout_user

from formspree import settings
from formspree.app_globals import DB
from formspree.users.models import User, Plan
from formspree.forms.models import Form

from .helpers import create_user_and_form


def test_api_setup(client, msend):
    (user, form) = create_user_and_form(client)

    user.plan = Plan.free
    DB.session.add(user)
    DB.session.commit()

    # enable api (should fail for non-paying users)
    r = client.patch(
        f"/api-int/forms/{form.hashid}",
        data=json.dumps({"api_enabled": True}),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Referer": settings.SERVICE_URL,
        },
    )
    assert r.status_code == 402

    user.plan = Plan.gold
    DB.session.add(user)
    DB.session.commit()

    # should work now
    r = client.patch(
        f"/api-int/forms/{form.hashid}",
        data=json.dumps({"api_enabled": True}),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Referer": settings.SERVICE_URL,
        },
    )
    assert r.status_code == 200

    key = Form.query.get(form.id).apikey
    assert key

    # reset api key
    r = client.post(
        f"/api-int/forms/{form.hashid}/reset-apikey",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Referer": settings.SERVICE_URL,
        },
    )
    assert r.status_code == 200
    assert json.loads(r.get_data())["key"] == Form.query.get(form.id).apikey != key


def test_submissions_api_v0(client, msend):
    (user, form) = create_user_and_form(client)
    form.apikey = "xyz"
    DB.session.add(form)
    DB.session.commit()
    logout_user()

    # submit the form multiple times
    for i, name in enumerate(["anna", "bradley", "camila", "dylan"]):
        r = client.post(
            "/" + form.hashid,
            data={"index": i, "name": name, f"field{i}": name},
            headers={"Referer": "https://example.com"},
        )
        assert r.status_code == 302

    # try basic fetching with master and readonly api keys
    for key in [form.apikey, form.apikey_readonly]:
        # with both basic auth and bearer token
        for authorization in [
            "Bearer " + key,
            "Basic " + base64.b64encode(b":" + key.encode("ascii")).decode("ascii"),
        ]:
            # fetch submissions in ascending order
            r = client.get(
                f"/api/0/forms/{form.hashid}/submissions?order=asc",
                headers={"Authorization": authorization},
            )
            resp = json.loads(r.get_data())
            assert resp["submissions"][0]["index"] == "0"
            assert resp["submissions"][3]["field3"] == "dylan"
            assert resp["submissions"][2]["name"] == "camila"
            assert resp["submissions"][1]["name"] == "bradley"

            # fetch single submission
            submission = resp["submissions"][3]
            r = client.get(
                f"/api/0/forms/{form.hashid}/submissions?limit=1&since={submission['_date']}",
                headers={"Authorization": authorization},
            )
            assert r.status_code == 200
            assert json.loads(r.get_data())["submissions"] == [submission]

    # fail to fetch with wrong api key
    r = client.get(
        f"/api/0/forms/{form.hashid}/submissions",
        headers={"Authorization": "Bearer 1234"},
    )
    assert int(r.status_code / 100) == 4
    assert json.loads(r.get_data())["ok"] == False

    # fail to fetch with no api key
    r = client.get(f"/api/0/forms/{form.hashid}/submissions")
    assert int(r.status_code / 100) == 4
    assert json.loads(r.get_data())["ok"] == False

    # fail to fetch if downgraded from paid plan
    user.plan = Plan.free
    DB.session.add(user)
    DB.session.commit()

    r = client.get(
        f"/api/0/forms/{form.hashid}/submissions",
        headers={"Authorization": form.apikey},
    )
    assert int(r.status_code / 100) == 4
    assert json.loads(r.get_data())["ok"] == False


def test_form_api_v0(client, msend):
    (user, form) = create_user_and_form(client)
    form.apikey = "xyz"
    DB.session.add(form)
    DB.session.commit()
    logout_user()

    # submit the form 4 times
    for i in range(4):
        r = client.post(
            "/" + form.hashid,
            data={"index": i, "name": "test"},
            headers={"Referer": "https://example.com"},
        )

    # fetch basic form data
    r = client.get(
        f"/api/0/forms/{form.hashid}",
        headers={"Authorization": "bearer " + form.apikey_readonly},
    )

    assert json.loads(r.get_data()) == {
        "ok": True,
        "submission_url": settings.API_ROOT + "/" + form.hashid,
        "total_submissions": 4,
    }
