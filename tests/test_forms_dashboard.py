import json
import urllib

from formspree import settings
from formspree.app_globals import DB
from formspree.users.models import User, Plan, Email
from formspree.forms.models import Form, Submission

from .helpers import create_user_and_form, PASSWORD


def test_form_creation(client, msend):
    # register user
    r = client.post(
        "/register", data={"email": "hope@springs.com", "password": "banana"}
    )
    assert r.status_code == 302
    assert 1 == User.query.count()

    email = Email.query.first()
    email.verified = True
    DB.session.add(email)
    DB.session.commit()

    # fail to create form
    r = client.post(
        "/api-int/forms",
        headers={"Content-type": "application/json", "Referer": settings.SERVICE_URL},
        data={"email": "hope@springs.com"},
    )
    assert r.status_code == 402
    assert "error" in json.loads(r.data.decode("utf-8"))
    assert 0 == Form.query.count()

    # upgrade user manually
    user = User.query.first()
    user.plan = Plan.gold
    DB.session.add(user)
    DB.session.commit()

    # successfully create form
    r = client.post(
        "/api-int/forms",
        headers={"Content-type": "application/json", "Referer": settings.SERVICE_URL},
        data=json.dumps({"email": "hope@springs.com"}),
    )
    resp = json.loads(r.data.decode("utf-8"))
    assert r.status_code == 201
    assert "submission_url" in resp
    assert "hashid" in resp
    form_endpoint = resp["hashid"]
    assert resp["hashid"] in resp["submission_url"]
    assert 1 == Form.query.count()
    assert Form.query.first().id == Form.get_with(hashid=resp["hashid"]).id

    # post to form, already confirmed because it was created from the dashboard
    r = client.post(
        "/" + form_endpoint,
        headers={
            "Referer": "http://formspree.io",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data=urllib.parse.urlencode({"name": "bruce"}),
        follow_redirects=True,
    )
    assert "Thanks!" in r.data.decode("utf-8")
    assert (
        "Someone just submitted your form on {}".format("formspree.io")
        in msend.call_args[1]["text"]
    )
    assert 1 == Form.query.count()

    # send 5 forms (monthly limits should not apply to the gold user)
    assert settings.MONTHLY_SUBMISSIONS_LIMIT == 2
    for i in range(5):
        r = client.post(
            "/" + form_endpoint,
            headers={"Referer": "formspree.io"},
            data={"name": "ana", "submission": "__%s__" % i},
        )
    form = Form.query.first()
    assert form.counter == 6
    assert form.get_monthly_counter() == 6
    assert "ana" in msend.call_args[1]["text"]
    assert "__4__" in msend.call_args[1]["text"]
    assert "past the limit" not in msend.call_args[1]["text"]

    # submit from a different host
    r = client.post(
        "/" + form_endpoint,
        headers={"Referer": "http://different.com"},
        data={"name": "ignored"},
        follow_redirects=True,
    )
    assert r.status_code == 200
    assert "Thanks!" in r.data.decode("utf-8")
    assert (
        "Someone just submitted your form on {}".format("different.com")
        in msend.call_args[1]["text"]
    )
    assert 1 == Form.query.count()

    # test submissions endpoint with the user downgraded
    user.plan = Plan.free
    DB.session.add(user)
    DB.session.commit()
    r = client.get(
        "/api-int/forms/" + form_endpoint, headers={"Referer": settings.SERVICE_URL}
    )
    assert r.status_code == 402  # it should fail

    # test submissions endpoint without a logged user
    client.get("/logout")
    r = client.get(
        "/api-int/forms/" + form_endpoint, headers={"Referer": settings.SERVICE_URL}
    )
    assert r.status_code == 401  # should return a json error (via flask login)
    assert "error" in r.json


def test_form_submissions_list(client, msend):
    (user, form) = create_user_and_form(client)

    # submit the form
    for i, name in enumerate(["jerome", "julia"]):
        r = client.post(
            "/" + form.hashid,
            data={"index": i, "name": name},
            headers={"Referer": "https://example.com/contact"},
        )
        assert r.status_code == 302

    # forms endpoint
    r = client.get(
        f"/api-int/forms",
        headers={"Referer": settings.SERVICE_URL, "Accept": "application/json"},
    )
    data = json.loads(r.get_data())
    assert "ok" in data
    assert "forms" in data
    assert len(data["forms"]) == 1

    formresp = data["forms"][0]
    assert "submissions" not in formresp
    assert not formresp["disabled"]
    assert not formresp["disable_email"]
    assert not formresp["disable_storage"]
    assert "dashboard" in formresp["features"]
    assert formresp["hashid"] == form.hashid

    # fetch form submissions
    r = client.get(
        f"/api-int/forms/{form.hashid}/submissions",
        headers={"Referer": settings.SERVICE_URL, "Accept": "application/json"},
    )
    data = json.loads(r.get_data())

    assert data["fields"] == ["_id", "_date", "index", "name", "_errors"]
    assert data["submissions"][0]["name"] == "julia"
    assert data["submissions"][1]["index"] == "0"


def test_exporting(client, msend):
    (user, form) = create_user_and_form(client)

    # submit the form
    for i, name in enumerate(["james", "joan"]):
        r = client.post(
            "/" + form.hashid,
            data={"index": i, "name": name},
            headers={"Referer": "https://example.com/contact"},
        )
        assert r.status_code == 302

    # test exporting feature (both json and csv file downloads)
    r = client.get("/forms/" + form.hashid + ".json")
    submissions = json.loads(r.data.decode("utf-8"))["submissions"]
    assert len(submissions) == 2
    assert submissions[0]["name"] == "joan"
    assert submissions[0]["index"] == "1"

    r = client.get("/forms/" + form.hashid + ".csv")
    lines = r.data.decode("utf-8").splitlines()
    assert len(lines) == 3
    assert lines[0] == "_date,index,name"
    assert ",0," in lines[2]
    assert ",james" in lines[2]


def test_form_toggle(client, msend):
    (user, form) = create_user_and_form(client)

    # disable the form
    r = client.patch(
        "/api-int/forms/" + form.hashid,
        headers={"Referer": settings.SERVICE_URL, "Content-Type": "application/json"},
        data=json.dumps({"disabled": True}),
    )
    assert 200 == r.status_code
    assert r.json["ok"]
    assert Form.query.first().disabled
    assert 0 == Form.query.first().counter

    # logout and attempt to enable the form
    client.get("/logout")
    r = client.patch(
        "/api-int/forms/" + form.hashid,
        headers={"Content-Type": "application/json", "Referer": settings.SERVICE_URL},
        data=json.dumps({"disabled": True}),
    )
    assert 401 == r.status_code
    assert "error" in json.loads(r.data.decode("utf-8"))
    assert Form.query.first().disabled

    # fail when attempting to post to form
    r = client.post(
        "/" + form.hashid,
        headers={"Referer": "http://formspree.io"},
        data={"name": "bruce"},
    )
    assert 403 == r.status_code
    assert 0 == Form.query.first().counter

    # log back in and re-enable form
    client.post("/login", data={"email": user.email, "password": PASSWORD})
    r = client.patch(
        "/api-int/forms/" + form.hashid,
        headers={"Referer": settings.SERVICE_URL, "Content-Type": "application/json"},
        data=json.dumps({"disabled": False}),
    )
    assert 200 == r.status_code
    assert not Form.query.first().disabled

    # successfully post to form
    r = client.post(
        "/" + form.hashid, headers={"Referer": "formspree.io"}, data={"name": "bruce"}
    )
    assert 1 == Form.query.first().counter
    assert 302 == r.status_code


def test_form_and_submission_deletion(client, msend):
    user, form = create_user_and_form(client)
    originalemail = user.email
    originalpassword = PASSWORD

    # increase the submission limit
    old_submission_limit = settings.ARCHIVED_SUBMISSIONS_LIMIT
    settings.ARCHIVED_SUBMISSIONS_LIMIT = 10

    # make 5 submissions
    for i in range(5):
        r = client.post(
            "/" + form.hashid,
            headers={"Referer": "formspree.io"},
            data={"name": "ana", "submission": "__%s__" % i},
        )

    assert 5 == Submission.query.count()

    # delete a submission in form
    first_submission = Submission.query.first()
    r = client.delete(
        "/api-int/forms/" + form.hashid + "/submissions",
        headers={"Referer": settings.SERVICE_URL},
        json={"submissions": [first_submission.id]},
    )
    assert 200 == r.status_code
    assert 4 == Submission.query.count()
    assert DB.session.query(Submission.id).filter_by(id="0").scalar() is None
    # make sure you've deleted the submission

    # logout user
    client.get("/logout")

    # attempt to delete form you don't have access to (while logged out)
    r = client.delete(
        "/api-int/forms/" + form.hashid, headers={"Referer": settings.SERVICE_URL}
    )
    assert 401 == r.status_code
    assert 1 == Form.query.count()

    # create different user
    r = client.post("/register", data={"email": "john@usa.com", "password": "america"})
    u = User.query.filter_by(email="john@usa.com").first()
    u.plan = Plan.gold
    DB.session.add(u)
    DB.session.commit()

    # attempt to delete form ()
    r = client.delete(
        "/api-int/forms/" + form.hashid, headers={"Referer": settings.SERVICE_URL}
    )
    assert 401 == r.status_code
    assert 1 == Form.query.count()

    client.get("/logout")

    # log back in to original account
    client.post("/login", data={"email": originalemail, "password": originalpassword})

    # delete the form created
    r = client.delete(
        "/api-int/forms/" + form.hashid, headers={"Referer": settings.SERVICE_URL}
    )
    assert 200 == r.status_code
    assert 0 == Form.query.count()

    # reset submission limit
    settings.ARCHIVED_SUBMISSIONS_LIMIT = old_submission_limit
