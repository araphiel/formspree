import json
import stripe

from formspree import settings
from formspree.app_globals import DB
from formspree.users.models import User, Email, Plan

from .helpers import (
    parse_confirmation_link_sent,
    create_user_and_form,
    create_and_activate_form,
)


def test_register_page(client, msend):
    r = client.get("/register")
    assert 200 == r.status_code


def test_login_page(client, msend):
    r = client.get("/login")
    assert 200 == r.status_code


def test_forgot_password_page(client, msend):
    r = client.get("/login/reset")
    assert 200 == r.status_code


def test_user_auth(client, msend):
    # register
    r = client.post(
        "/register", data={"email": "alice@springs.com", "password": "canada"}
    )
    assert r.status_code == 302
    assert r.location.endswith("/dashboard")
    assert 1 == User.query.count()

    # email confirmation
    user = User.query.filter_by(email="alice@springs.com").first()
    assert Email.query.get(["alice@springs.com", user.id]).verified is False

    assert msend.called
    link, qs = parse_confirmation_link_sent(msend.call_args[1]["text"])
    r = client.get(link, query_string=qs, follow_redirects=True)
    assert "Almost There" in r.data.decode("utf-8")

    # logout
    r = client.get("/logout")
    assert r.status_code == 302
    assert 1 == User.query.count()

    # login
    r = client.post("/login", data={"email": "alice@springs.com", "password": "canada"})
    assert r.status_code == 302
    assert r.location.endswith("/dashboard")
    assert 1 == User.query.count()


def test_forgot_password(client, msend):
    # register
    r = client.post(
        "/register", data={"email": "fragile@yes.com", "password": "roundabout"}
    )
    assert 1 == User.query.count()
    initial_password = User.query.all()[0].password

    # logout
    client.get("/logout")

    # forget password
    r = client.post("/login/reset", data={"email": "fragile@yes.com"})
    assert r.status_code == 200

    # click on the email link
    link, qs = parse_confirmation_link_sent(msend.call_args[1]["text"])
    r = client.get(link, query_string=qs, follow_redirects=True)
    assert r.status_code == 200

    # send new passwords (not matching)
    r = client.post(link, data={"password1": "verdes", "password2": "roxas"})
    assert r.status_code == 302
    assert r.location == link
    assert User.query.all()[0].password == initial_password

    # again, now matching
    r = client.post(link, data={"password1": "amarelas", "password2": "amarelas"})
    assert r.status_code == 302
    assert r.location.endswith("/dashboard")
    assert User.query.all()[0].password != initial_password


def test_user_upgrade_and_downgrade(client, msend, mocker):
    # check correct usage of stripe test keys during test
    assert "_test_" in settings.STRIPE_PUBLISHABLE_KEY
    assert "_test_" in settings.STRIPE_SECRET_KEY
    assert stripe.api_key in settings.STRIPE_TEST_SECRET_KEY

    # get card token from stripe
    token = stripe.Token.create(
        card={
            "number": "4242424242424242",
            "exp_month": "11",
            "exp_year": "2026",
            "cvc": "123",
        }
    )["id"]

    # create user and buy a plan at the same time
    r = client.post(
        "/api-int/buy",
        headers={"Content-type": "application/json", "Referer": settings.SERVICE_URL},
        data=json.dumps(
            {
                "token": token,
                "plan": Plan.platinum_yearly,
                "email": "maria@example.com",
                "password": "12345678",
            }
        ),
    )

    user = User.query.filter_by(email="maria@example.com").first()
    assert user.plan == Plan.platinum_yearly

    # downgrade back to the free plan
    r = client.post(
        "/api-int/cancel",
        headers={"Content-type": "application/json", "Referer": settings.SERVICE_URL},
    )
    assert r.status_code == 200

    user = User.query.filter_by(email="maria@example.com").first()
    assert user.plan == Plan.platinum_yearly

    customer = stripe.Customer.retrieve(user.stripe_id)
    assert customer.subscriptions.data[0].cancel_at_period_end == True

    # simulate stripe webhook reporting that the plan has been canceled just now
    m_senddowngraded = mocker.patch("formspree.users.views.send_downgrade_email.delay")
    customer.subscriptions.data[0].delete()
    # this will send webhooks automatically only for
    # endpoints registered on the stripe dashboard

    client.post(
        "/webhooks/stripe",
        data=json.dumps(
            {
                "type": "customer.subscription.deleted",
                "data": {"object": {"customer": user.stripe_id}},
            }
        ),
        headers={"Content-type": "application/json"},
    )

    user = User.query.filter_by(email="maria@example.com").first()
    assert user.plan == Plan.free
    assert m_senddowngraded.called

    # delete the stripe customer
    customer.delete()


def test_user_card_management(client, msend):
    # check correct usage of stripe test keys during test
    assert "_test_" in settings.STRIPE_PUBLISHABLE_KEY
    assert "_test_" in settings.STRIPE_SECRET_KEY
    assert stripe.api_key in settings.STRIPE_TEST_SECRET_KEY

    # register user
    r = client.post("/register", data={"email": "maria@example.com", "password": "uva"})
    assert r.status_code == 302

    user = User.query.filter_by(email="maria@example.com").first()
    assert user.plan == Plan.free

    # subscribe with card through stripe
    token = stripe.Token.create(
        card={
            "number": "5555555555554444",
            "exp_month": "11",
            "exp_year": "2026",
            "cvc": "123",
        }
    )["id"]
    r = client.post(
        "/api-int/buy",
        headers={"Content-type": "application/json", "Referer": settings.SERVICE_URL},
        data=json.dumps({"token": token, "plan": Plan.platinum}),
    )

    user = User.query.filter_by(email="maria@example.com").first()
    assert user.plan == Plan.platinum

    # add another card
    token = stripe.Token.create(
        card={
            "number": "4012888888881881",
            "exp_month": "11",
            "exp_year": "2021",
            "cvc": "345",
        }
    )["id"]
    r = client.post(
        "/api-int/account/cards",
        headers={"Content-type": "application/json", "Referer": settings.SERVICE_URL},
        data=json.dumps({"token": token}),
    )

    assert r.status_code == 201  # 201 Created means a card was added
    customer = stripe.Customer.retrieve(user.stripe_id)
    cards = customer.sources.list(object="card").data
    assert len(cards) == 2

    # add a duplicate card
    token = stripe.Token.create(
        card={
            "number": "5555555555554444",
            "exp_month": "11",
            "exp_year": "2026",
            "cvc": "123",
        }
    )["id"]
    r = client.post(
        "/api-int/account/cards",
        headers={"Content-type": "application/json", "Referer": settings.SERVICE_URL},
        data=json.dumps({"token": token}),
    )

    assert r.status_code == 200  # 200 Ok means the card already existed,
    # but that's not a problem

    # delete a card
    r = client.delete(
        "/api-int/account/cards/%s" % cards[1].id,
        headers={"Accept": "application/json", "Referer": settings.SERVICE_URL},
    )
    assert r.status_code == 200
    cards = customer.sources.list(object="card").data
    assert len(cards) == 1

    # delete the customer
    customer.delete()


def test_email_and_linked_forms_managements(client, msend):
    user, dashboard_form = create_user_and_form(client)

    # create a legacy form with this same email address
    create_and_activate_form(client, email=user.email, host="www.example.com")

    # try to delete email address
    r = client.delete(
        "/api-int/account/emails/" + user.email,
        headers={"Accept": "application/json", "Referer": settings.SERVICE_URL},
    )
    assert r.status_code == 403  # fails because there's a form tied to it

    # add a new email address
    email = Email(address="foo@example.com", owner_id=user.id, verified=True)
    DB.session.add(email)
    DB.session.commit()

    # move this form to there
    r = client.patch(
        "/api-int/forms/" + dashboard_form.hashid,
        headers={"Content-Type": "application/json", "Referer": settings.SERVICE_URL},
        data=json.dumps({"email": "foo@example.com"}),
    )
    assert r.status_code == 200

    # try to delete again
    r = client.delete(
        "/api-int/account/emails/" + user.email,
        headers={"Accept": "application/json", "Referer": settings.SERVICE_URL},
    )
    # should succeed now (even though the legacy form is
    # still tied to the previous email address)
    assert r.status_code == 200

def test_user_resubscribe(client, msend):
    # register the user and assign them a stripe id without a source
    # simulates a downgraded user without a payment source on file
    # register user
    r = client.post("/register", data={"email": "jolly@roger.com", "password": "pirate"})
    assert r.status_code == 302

    user = User.query.filter_by(email="jolly@roger.com").first()
    customer = stripe.Customer.create(email=user.email)
    user.stripe_id = customer['id']
    DB.session.add(user)
    DB.session.commit()

    # subscribe with card through stripe
    token = stripe.Token.create(
        card={
            "number": "5555555555554444",
            "exp_month": "11",
            "exp_year": "2026",
            "cvc": "123",
        }
    )["id"]
    r = client.post(
        "/api-int/buy",
        headers={"Content-type": "application/json", "Referer": settings.SERVICE_URL},
        data=json.dumps({"token": token, "plan": Plan.platinum}),
    )

    user = User.query.filter_by(email="jolly@roger.com").first()
    assert user.plan == Plan.platinum

    customer.delete()
