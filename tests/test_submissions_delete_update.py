import json

from formspree import settings
from formspree.app_globals import DB
from formspree.users.models import Plan

from .helpers import create_user_and_form


def test_submissions_delete(client, msend):
    (user, form) = create_user_and_form(client)

    user.plan = Plan.gold
    DB.session.add(user)
    DB.session.commit()

    # submit the form multiple times
    for i, name in enumerate(["anna", "bradley", "camila", "dylan"]):
        r = client.post(
            "/" + form.hashid,
            data={"index": i, "name": name},
            headers={"Referer": "https://example.com"},
        )
        assert r.status_code == 302

    # get submissions
    r = client.get(
        f"/api-int/forms/{form.hashid}/submissions",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Referer": settings.SERVICE_URL,
        },
    )
    assert r.status_code == 200
    ids = [s.get("_id") for s in r.json.get("submissions")]

    # delete some submissions
    r = client.delete(
        f"/api-int/forms/{form.hashid}/submissions",
        data=json.dumps({"submissions": ids[0:2]}),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Referer": settings.SERVICE_URL,
        },
    )
    assert r.status_code == 200
    assert r.json.get("deleted") == 2
    assert r.json.get("counter") == 2

    assert form.counter == 2


def test_submissions_set_spam(client, msend):
    (user, form) = create_user_and_form(client)

    user.plan = Plan.gold
    DB.session.add(user)
    DB.session.commit()

    # submit the form multiple times
    for i, name in enumerate(
        ["anna", "bradley", "camila", "dylan", "spammer-1", "spammer-2"]
    ):
        r = client.post(
            "/" + form.hashid,
            data={"index": i, "name": name},
            headers={"Referer": "https://example.com"},
        )
        assert r.status_code == 302

    # get submissions
    r = client.get(
        f"/api-int/forms/{form.hashid}/submissions",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Referer": settings.SERVICE_URL,
        },
    )
    assert r.status_code == 200
    ids = [
        s.get("_id")
        for s in r.json.get("submissions")
        if s.get("name").startswith("spammer")
    ]
    assert len(ids) == 2

    # set some submissions as spam
    r = client.patch(
        f"/api-int/forms/{form.hashid}/submissions",
        data=json.dumps({"submissions": ids, "operation": {"spam": True}}),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Referer": settings.SERVICE_URL,
        },
    )
    assert r.status_code == 200
    assert r.json.get("updated") == 2
    assert r.json.get("counter") == 4

    for sub in form.submissions.all():
        assert sub.spam == (
            True if sub.data.get("name").startswith("spammer") else None
        )
    assert form.counter == 4

    # get submissions, should not include spam
    r = client.get(
        f"/api-int/forms/{form.hashid}/submissions",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Referer": settings.SERVICE_URL,
        },
    )
    assert r.status_code == 200
    assert len(r.json.get("submissions")) == 4

    # get just spam submissions
    r = client.get(
        f"/api-int/forms/{form.hashid}/submissions?filter.spam=true",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Referer": settings.SERVICE_URL,
        },
    )
    assert r.status_code == 200
    spams = [s for s in r.json.get("submissions")]
    assert len(ids) == 2

    # set a submission as not spam
    r = client.patch(
        f"/api-int/forms/{form.hashid}/submissions",
        data=json.dumps(
            {"submissions": [spams[0].get("_id")], "operation": {"spam": False}}
        ),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Referer": settings.SERVICE_URL,
        },
    )
    assert r.status_code == 200
    assert r.json.get("updated") == 1
    assert r.json.get("counter") == 5

    for sub in form.submissions.all():
        if sub.data.get("name") == spams[0].get("name"):
            assert sub.spam is False
    assert form.counter == 5
