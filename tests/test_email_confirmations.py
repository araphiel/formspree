import json

from formspree import settings
from formspree.app_globals import DB
from formspree.users.models import User, Email, Plan
from formspree.forms.models import Form

from .helpers import parse_confirmation_link_sent


def test_user_registers_and_adds_emails(client, msend):
    # register
    r = client.post(
        "/register", data={"email": "alice@springs.com", "password": "canada"}
    )
    assert r.status_code == 302
    assert r.location.endswith("/dashboard")
    assert 1 == User.query.count()

    user = User.query.filter_by(email="alice@springs.com").first()

    # ensure that we've sent verification email
    assert "alice@springs.com" in msend.call_args[1]["html"]

    # ensure that an unverified email has been added
    assert Email.query.count() == 1
    assert Email.query.get(["alice@springs.com", user.id]).verified is False

    # click the verification link. Check to make sure we get captcha page
    link, qs = parse_confirmation_link_sent(msend.call_args[1]["text"])
    r = client.get(link, query_string=qs, follow_redirects=True)
    assert "Almost There" in r.data.decode("utf-8")

    # add user to the gold plan
    u = User.query.filter_by(email="alice@springs.com").first()
    u.plan = Plan.gold
    DB.session.add(u)
    DB.session.commit()

    # add more emails
    emails = [
        (202, "alice@example.com", 2),
        (400, "inva...lid", 2),
        (202, "team@alice.com", 3),
        (403, "toomany@alice.com", 3),
    ]
    for (cexp, addr, count) in emails:
        r = client.post(
            "/api-int/account/emails",
            headers={
                "Content-Type": "application/json",
                "Referer": settings.SERVICE_URL,
            },
            data=json.dumps({"address": addr}),
        )
        assert r.status_code == cexp
        assert Email.query.count() == count
        if cexp >= 300:
            continue

        email = Email.query.get([addr, user.id])
        assert email is not None
        assert email.owner_id == user.id


def test_user_gets_previous_forms_assigned_to_him(client, msend):
    # verify a form for márkö@example.com
    client.post(
        u"/márkö@example.com",
        headers={"Referer": "tomatoes.com"},
        data={"name": "alice"},
    )
    f = Form.get_with(host="tomatoes.com", email="márkö@example.com")
    f.confirm_sent = True
    f.confirmed = True
    DB.session.add(f)
    DB.session.commit()

    # register márkö@example.com
    r = client.post(
        "/register", data={"email": "márkö@example.com", "password": "russia"}
    )

    # confirm that the user account doesn't have access to the form
    r = client.get(
        "/api-int/forms",
        headers={"Accept": "application/json", "Referer": settings.SERVICE_URL},
    )
    forms = json.loads(r.data.decode("utf-8"))["forms"]
    assert 0 == len(forms)

    # verify user email
    link, qs = parse_confirmation_link_sent(msend.call_args[1]["text"])
    client.get(link, query_string=qs)

    # confirm that the user has no access to the form since he is not gold
    r = client.get(
        "/api-int/forms",
        headers={"Accept": "application/json", "Referer": settings.SERVICE_URL},
    )
    forms = json.loads(r.data.decode("utf-8"))["forms"]
    assert 0 == len(forms)

    # upgrade user
    user = User.query.filter_by(email="márkö@example.com").first()
    user.plan = Plan.gold
    DB.session.add(user)
    DB.session.commit()

    # confirm that the user account has access to the form
    r = client.get(
        "/api-int/forms",
        headers={"Accept": "application/json", "Referer": settings.SERVICE_URL},
    )
    forms = json.loads(r.data.decode("utf-8"))["forms"]
    assert 1 == len(forms)
    assert forms[0]["email"] == "márkö@example.com"
    assert forms[0]["host"] == "tomatoes.com"

    # verify a form for another address
    r = client.post(
        "/contact@mark.com", headers={"Referer": "mark.com"}, data={"name": "luke"}
    )
    f = Form.get_with(host="mark.com", email="contact@mark.com")
    f.confirm_sent = True
    f.confirmed = True
    DB.session.add(f)
    DB.session.commit()

    # confirm that the user account doesn't have access to the form
    r = client.get(
        "/api-int/forms",
        headers={"Accept": "application/json", "Referer": settings.SERVICE_URL},
    )
    forms = json.loads(r.data.decode("utf-8"))["forms"]
    assert 1 == len(forms)

    # add this other email address to user account
    client.post(
        "/api-int/account/emails",
        headers={"Content-Type": "application/json", "Referer": settings.SERVICE_URL},
        data=json.dumps({"address": "contact@mark.com"}),
    )

    link, qs = parse_confirmation_link_sent(msend.call_args[1]["text"])
    client.get(link, query_string=qs)

    # confirm that the user account now has access to the form
    r = client.get(
        "/api-int/forms",
        headers={"Accept": "application/json", "Referer": settings.SERVICE_URL},
    )
    forms = json.loads(r.data.decode("utf-8"))["forms"]
    assert 2 == len(forms)
    assert (
        forms[0]["email"] == "contact@mark.com"
    )  # forms are sorted by -id, so the newer comes first
    assert forms[0]["host"] == "mark.com"

    # create a new form spontaneously with an email already verified
    r = client.post(
        u"/márkö@example.com",
        headers={"Referer": "elsewhere.com"},
        data={"name": "luke"},
    )
    f = Form.get_with(host="elsewhere.com", email="márkö@example.com")
    f.confirm_sent = True
    f.confirmed = True
    DB.session.add(f)
    DB.session.commit()

    # confirm that the user has already accessto that form
    r = client.get(
        "/api-int/forms",
        headers={"Accept": "application/json", "Referer": settings.SERVICE_URL},
    )
    forms = json.loads(r.data.decode("utf-8"))["forms"]
    assert 3 == len(forms)
    assert forms[0]["email"] == "márkö@example.com"
    assert forms[0]["host"] == "elsewhere.com"
