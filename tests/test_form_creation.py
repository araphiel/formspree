import json

from formspree import settings
from formspree.app_globals import DB
from formspree.forms.helpers import HASH
from formspree.users.models import User, Email, Plan
from formspree.forms.models import Form, Submission


def test_form_creation(client, msend):
    # register user
    r = client.post(
        "/register", data={"email": "colorado@springs.com", "password": "banana"}
    )
    assert r.status_code == 302
    assert 1 == User.query.count()

    # fail to create form
    r = client.post(
        "/api-int/forms",
        headers={"Content-type": "application/json", "Referer": settings.SERVICE_URL},
        data=json.dumps({"email": "hope@springs.com"}),
    )
    assert r.status_code == 402
    assert "error" in json.loads(r.data.decode("utf-8"))
    assert 0 == Form.query.count()

    # upgrade user manually
    user = User.query.filter_by(email="colorado@springs.com").first()
    user.plan = Plan.gold
    DB.session.add(user)
    DB.session.commit()

    # verify email
    email = Email.query.filter_by(
        address="colorado@springs.com", owner_id=user.id
    ).first()
    email.verified = True
    DB.session.add(email)
    DB.session.commit()

    # successfully create form
    msend.reset_mock()
    r = client.post(
        "/api-int/forms",
        headers={
            "Accept": "application/json",
            "Content-type": "application/json",
            "Referer": settings.SERVICE_URL,
        },
        data=json.dumps({"email": "colorado@springs.com"}),
    )

    # no email should have been sent
    assert not msend.called

    # should return success payload
    resp = json.loads(r.data.decode("utf-8"))
    assert r.status_code == 201
    assert "submission_url" in resp
    assert "hashid" in resp
    form_endpoint = resp["hashid"]
    assert resp["hashid"] in resp["submission_url"]

    # a form should now exist in the db
    assert 1 == Form.query.count()
    assert Form.query.first().id == Form.get_with(hashid=resp["hashid"]).id
    assert Form.query.first().confirmed

    # post to the form
    r = client.post(
        "/" + form_endpoint,
        headers={"Referer": "http://testsite.com"},
        data={"name": "bruce"},
        follow_redirects=True,
    )

    # Should get thank-you page
    assert "Thanks!" in r.data.decode("utf-8")
    assert "You're only one step away" not in msend.call_args[1]["text"]

    # send 5 forms (monthly limits should not apply to the gold user)
    assert settings.MONTHLY_SUBMISSIONS_LIMIT == 2
    for i in range(5):
        r = client.post(
            "/" + form_endpoint,
            headers={"Referer": "http://testsite.com"},
            data={"name": "ana", "submission": "__%s__" % i},
        )

    # form should now have 6 submissions
    form = Form.query.first()
    assert form.counter == 6

    # check last submission email
    assert "ana" in msend.call_args[1]["text"]
    assert "__4__" in msend.call_args[1]["text"]
    assert "past the limit" not in msend.call_args[1]["text"]

    # submit form from a different host -- this is OK now
    r = client.post(
        "/" + form_endpoint,
        headers={"Referer": "http://different.com"},
        data={"name": "permitted"},
        follow_redirects=True,
    )
    assert r.status_code == 200
    assert "permitted" in msend.call_args[1]["text"]

    # submit form without a Referer -- this is OK now
    r = client.post(
        "/" + form_endpoint, data={"name": "permitted"}, follow_redirects=True
    )
    assert r.status_code == 200
    assert "permitted" in msend.call_args[1]["text"]
    assert "unknown webpage" in msend.call_args[1]["text"]


def test_form_creation_without_registered_email(client, msend):
    # register user
    r = client.post(
        "/register", data={"email": "user@testsite.com", "password": "banana"}
    )

    # upgrade user manually
    user = User.query.filter_by(email="user@testsite.com").first()
    user.plan = Plan.gold
    DB.session.add(user)
    DB.session.commit()

    # create form without a confirmed email should throw an error
    msend.reset_mock()
    r = client.post(
        "/api-int/forms",
        headers={
            "Accept": "application/json",
            "Content-type": "application/json",
            "Referer": settings.SERVICE_URL,
        },
        data=json.dumps(
            {
                "email": "email@testsite.com",
                "url": "https://www.testsite.com/contact.html",
            }
        ),
    )
    resp = json.loads(r.data.decode("utf-8"))
    assert "error" in resp
    assert not msend.called

    # no forms should have been created
    assert Form.query.count() == 0


def test_form_settings(client, msend):
    # register and upgrade user
    client.post("/register", data={"email": "texas@springs.com", "password": "water"})
    user = User.query.filter_by(email="texas@springs.com").first()
    user.plan = Plan.gold
    DB.session.add(user)
    DB.session.commit()

    # verify email
    email = Email.query.filter_by(address="texas@springs.com", owner_id=user.id).first()
    email.verified = True
    DB.session.add(email)
    DB.session.commit()

    # create and confirm form
    r = client.post(
        "/api-int/forms",
        headers={
            "Accept": "application/json",
            "Content-type": "application/json",
            "Referer": settings.SERVICE_URL,
        },
        data=json.dumps({"email": "texas@springs.com"}),
    )
    resp = json.loads(r.data.decode("utf-8"))
    form_endpoint = resp["hashid"]

    # disable email notifications on this form
    msend.reset_mock()
    client.patch(
        "/api-int/forms/" + form_endpoint,
        headers={"Referer": settings.SERVICE_URL},
        content_type="application/json",
        data=json.dumps({"disable_email": True}),
    )
    assert Form.query.first().disable_email

    # post to form
    client.post(
        "/" + form_endpoint,
        headers={"Referer": "http://testsite.com"},
        data={"name": "bruce"},
    )
    # make sure it doesn't send the email
    assert not msend.called

    # disable archive storage on this form
    client.patch(
        "/api-int/forms/" + form_endpoint,
        headers={"Referer": settings.SERVICE_URL},
        content_type="application/json",
        data=json.dumps({"disable_storage": True}),
    )
    assert Form.query.first().disable_storage

    # make sure that we know there's one submission in database from first submission
    assert 1 == Submission.query.count()

    # make sure that the submission wasn't stored in the database
    # post to form
    client.post(
        "/" + form_endpoint,
        headers={"Referer": "http://testsite.com"},
        data={"name": "wayne"},
    )
    assert 1 == Submission.query.count()

    # enable email notifications on this form
    client.patch(
        "/api-int/forms/" + form_endpoint,
        headers={"Referer": settings.SERVICE_URL},
        content_type="application/json",
        data=json.dumps({"disable_email": False}),
    )
    assert not Form.query.first().disable_email

    # make sure that our form still isn't storing submissions
    assert 1 == Submission.query.count()

    # enable archive storage again
    client.patch(
        "/api-int/forms/" + form_endpoint,
        headers={"Referer": settings.SERVICE_URL},
        content_type="application/json",
        data=json.dumps({"disable_storage": False}),
    )
    assert not Form.query.first().disable_storage

    # post to form again this time it should store the submission
    client.post(
        "/" + form_endpoint,
        headers={"Referer": "http://testsite.com"},
        data={"name": "luke"},
    )
    assert 2 == Submission.query.filter_by(form_id=Form.query.first().id).count()

    # check captcha disabling
    assert not Form.query.first().captcha_disabled

    client.patch(
        "/api-int/forms/" + form_endpoint,
        headers={"Referer": settings.SERVICE_URL},
        content_type="application/json",
        data=json.dumps({"captcha_disabled": True}),
    )
    assert Form.query.first().captcha_disabled

    client.patch(
        "/api-int/forms/" + form_endpoint,
        headers={"Referer": settings.SERVICE_URL},
        content_type="application/json",
        data=json.dumps({"captcha_disabled": False}),
    )
    assert not Form.query.first().captcha_disabled
