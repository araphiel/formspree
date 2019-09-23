import json

from formspree import settings
from formspree.app_globals import DB
from formspree.forms.helpers import HASH
from formspree.users.models import User, Email, Plan
from formspree.forms.models import Form, Submission


def test_xsrf_failure_and_success(client, msend):
    email = "apiuser@example.com"
    password = "xxxxxxx"

    user, _ = User.register(email, password)
    user.plan = Plan.gold
    user.emails[0].verified = True
    DB.session.add(user)
    DB.session.commit()

    client.post("/login", data={"email": email, "password": password})

    # fail because it doesn't come from the correct referrer
    r = client.post(
        "/api-int/forms",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"email": "apiuser@example.com"}),
    )
    assert r.status_code == 400
    assert json.loads(r.get_data())["error"] == "Improper request."

    # succeeed
    r = client.post(
        "/api-int/forms",
        headers={"Content-Type": "application/json", "Referer": settings.SERVICE_URL},
        data=json.dumps({"email": "apiuser@example.com"}),
    )
    assert r.status_code == 201
    assert json.loads(r.get_data())["ok"]
