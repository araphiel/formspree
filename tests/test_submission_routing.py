import json

import pytest

from formspree import settings
from formspree.app_globals import DB
from formspree.users.models import Plan, Email
from formspree.forms.models import RoutingRule

from .helpers import create_user_and_form


def test_rules_api(client, msend):
    user1, form = create_user_and_form(client)

    ruledef = {
        "trigger": {"fn": "exists", "field": "important", "params": []},
        "email": "important@example.com",
    }

    # fail to create rule as gold user
    r = client.post(
        f"/api-int/forms/{form.hashid}/rules",
        data=json.dumps(ruledef),
        headers={"Referer": settings.SERVICE_URL, "Content-Type": "application/json"},
    )
    assert r.status_code == 402

    # upgrade to platinum
    user1.plan = Plan.platinum
    DB.session.add(user1)
    DB.session.commit()

    # fail to create rule with an email address not registered
    r = client.post(
        f"/api-int/forms/{form.hashid}/rules",
        data=json.dumps(ruledef),
        headers={"Referer": settings.SERVICE_URL, "Content-Type": "application/json"},
    )
    assert r.status_code == 403

    # register email address on a different account
    user2, _ = create_user_and_form(client, login=False)
    email = Email(address=ruledef["email"], owner_id=user2.id, verified=True)
    DB.session.add(email)
    DB.session.commit()

    # fail again, address must be under the user control
    r = client.post(
        f"/api-int/forms/{form.hashid}/rules",
        data=json.dumps(ruledef),
        headers={"Referer": settings.SERVICE_URL, "Content-Type": "application/json"},
    )
    assert r.status_code == 403

    # get email under control of the correct user
    email = Email(address=ruledef["email"], owner_id=user1.id, verified=True)
    DB.session.add(email)
    DB.session.commit()

    # should succeed now
    r = client.post(
        f"/api-int/forms/{form.hashid}/rules",
        data=json.dumps(ruledef),
        headers={"Referer": settings.SERVICE_URL, "Content-Type": "application/json"},
    )
    assert r.status_code == 201

    q = RoutingRule.query.filter_by(form_id=form.id)
    assert q.count() == 1
    rule = q.first()
    assert rule.email == ruledef["email"]
    assert rule.trigger == ruledef["trigger"]

    # edit routing rule
    ruledef["trigger"]["field"] = "useless"
    r = client.put(
        f"/api-int/forms/{form.hashid}/rules/{rule.id}",
        data=json.dumps(ruledef),
        headers={"Content-Type": "application/json", "Referer": settings.SERVICE_URL},
    )
    assert r.status_code == 200

    q = RoutingRule.query.filter_by(form_id=form.id)
    assert q.count() == 1
    rule = q.first()
    assert rule.email == ruledef["email"]
    assert rule.trigger == ruledef["trigger"]

    # editing the email should fail if address isn't linked and verified
    newemail = Email(address="useless@example.com", owner_id=user1.id, verified=False)
    DB.session.add(newemail)
    DB.session.commit()
    r = client.put(
        f"/api-int/forms/{form.hashid}/rules/{rule.id}",
        data=json.dumps({"email": newemail.address, "trigger": ruledef["trigger"]}),
        headers={"Content-Type": "application/json", "Referer": settings.SERVICE_URL},
    )
    assert r.status_code == 403

    # fail to remove email if rule exists
    r = client.delete(
        f"/api-int/account/emails/{ruledef['email']}",
        headers={"Referer": settings.SERVICE_URL},
    )
    assert r.status_code == 403

    # remove rule
    r = client.delete(
        f"/api-int/forms/{form.hashid}/rules/{rule.id}",
        headers={"Referer": settings.SERVICE_URL},
    )
    assert r.status_code == 200

    # can remove linked email now
    r = client.delete(
        f"/api-int/account/emails/{ruledef['email']}",
        headers={"Referer": settings.SERVICE_URL},
    )
    assert r.status_code == 200


def test_rules(client, msend):
    user, form = create_user_and_form(client)
    user.plan = Plan.platinum
    DB.session.add(user)
    DB.session.commit()

    email = Email(address="customerdept@example.com", owner_id=user.id, verified=True)
    DB.session.add(email)
    DB.session.commit()

    # create rule
    r = client.post(
        f"/api-int/forms/{form.hashid}/rules",
        data=json.dumps(
            {
                "trigger": {"fn": "contains", "field": "dept", "params": ["customer"]},
                "email": "customerdept@example.com",
            }
        ),
        headers={"Referer": settings.SERVICE_URL, "Content-Type": "application/json"},
    )
    assert r.status_code == 201

    # send submissions
    msend.reset_mock()
    r = client.post(f"/{form.hashid}", data={"hello": "world"})
    assert r.status_code == 302
    assert not msend.called

    msend.reset_mock()
    r = client.post(
        f"/{form.hashid}", data={"hello": "world", "dept": "customer-department"}
    )
    assert r.status_code == 302
    assert msend.called
    assert msend.call_args[1]["to"] == "customerdept@example.com"


cases = [
    (
        "mysite.com/contact",
        {"kind": "fruit", "x": "1"},
        {"x@example.com", "fruits@example.com"},
    ),
    (
        "mysite.com/about",
        {"kind": "lettuce", "x": "1"},
        {"x@example.com", "rest@example.com"},
    ),
    (None, {"kind": "meat"}, {"rest@example.com"}),
    ("mysite.com/contact", {"x": "1"}, {"x@example.com", "rest@example.com"}),
    (
        "mysite.com/",
        {"kind": "fruit", "y": "1"},
        {"y@example.com", "fruits@example.com"},
    ),
    ("mysite.com", {"kind": "fruit"}, {"fruits@example.com"}),
    (
        "mysite.com/fruits",
        {"kind": "lettuce"},
        {"fruits@example.com", "rest@example.com"},
    ),
    (
        "mysite.com/fruits/index.html",
        {"kind": "water", "w": "1", "y": "1"},
        {"fruits@example.com", "rest@example.com", "y@example.com", "w@example.com"},
    ),
]


@pytest.mark.parametrize("case", cases)
def test_multiple_cases(client, msend, case):
    user, form = create_user_and_form(client)
    user.plan = Plan.platinum
    DB.session.add(user)

    emailx = Email(address="x@example.com", owner_id=user.id, verified=True)
    DB.session.add(emailx)
    emaily = Email(address="y@example.com", owner_id=user.id, verified=True)
    DB.session.add(emaily)
    emailw = Email(address="w@example.com", owner_id=user.id, verified=True)
    DB.session.add(emailw)
    emailfruits = Email(address="fruits@example.com", owner_id=user.id, verified=True)
    DB.session.add(emailfruits)
    emailrest = Email(address="rest@example.com", owner_id=user.id, verified=True)
    DB.session.add(emailrest)
    emailalways = Email(address="always@example.com", owner_id=user.id, verified=True)
    DB.session.add(emailalways)

    r1 = RoutingRule(form_id=form.id)
    r1.email = emailx.address
    r1.trigger = {"fn": "exists", "field": "x", "params": []}
    DB.session.add(r1)

    r2 = RoutingRule(form_id=form.id)
    r2.email = emaily.address
    r2.trigger = {"fn": "exists", "field": "y", "params": []}
    DB.session.add(r2)

    r3 = RoutingRule(form_id=form.id)
    r3.email = emailw.address
    r3.trigger = {"fn": "exists", "field": "w", "params": []}
    DB.session.add(r3)

    r4 = RoutingRule(form_id=form.id)
    r4.email = emailfruits.address
    r4.trigger = {"fn": "contains", "field": "_host", "params": ["/fruits"]}
    DB.session.add(r4)

    r5 = RoutingRule(form_id=form.id)
    r5.email = emailfruits.address
    r5.trigger = {"fn": "contains", "field": "kind", "params": ["fruit"]}
    DB.session.add(r5)

    r6 = RoutingRule(form_id=form.id)
    r6.email = emailrest.address
    r6.trigger = {"fn": "doesntcontain", "field": "kind", "params": ["fruit"]}
    DB.session.add(r6)

    r7 = RoutingRule(form_id=form.id)
    r7.email = emailalways.address
    r7.trigger = {"fn": "true", "field": None, "params": []}
    DB.session.add(r7)

    DB.session.commit()

    referrer, data, targets = case
    r = client.post(f"/{form.hashid}", data=data, headers={"Referer": referrer})
    assert r.status_code == 302
    received = {call[1]["to"] for call in msend.call_args_list}
    targets.add(emailalways.address)
    assert received == targets
