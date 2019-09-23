import datetime

import stripe
from flask import request, jsonify, g
from flask_login import current_user, login_required, login_user
from sqlalchemy.exc import IntegrityError

from formspree.app_globals import DB
from formspree.utils import prevent_xsrf, requires_feature
from formspree import settings
from .models import Email, User
from .helpers import CARD_MAPPINGS, send_downgrade_reason_email, get_current_sale


@prevent_xsrf
def buy():
    data = request.get_json()

    isnew = False
    if "email" in data:
        try:
            user, isnew = User.register(data["email"], data["password"])
            g.log.info("User created.", ip=request.headers.get("X-Forwarded-For"))
        except ValueError:
            return jsonify({"ok": False, "error": "Invalid email address."}), 400
        except IntegrityError:
            return (
                jsonify(
                    {
                        "ok": False,
                        "error": "User already registered. Please login first.",
                    }
                ),
                401,
            )

        login_user(user, remember=True)

        if isnew:
            Email.send_confirmation(user.email, user.id)

    # from now on we have current_user for sure
    g.log = g.log.bind(account=current_user.email)

    token = data.get("token")
    plan = data["plan"]
    coupon = get_current_sale(plan)

    g.log.info("Upgrading account.", plan=plan)

    sub = None
    try:
        if current_user.stripe_id:
            g.log.info("User already has a Stripe account. Will attempt to retrieve subscription.")
            customer = stripe.Customer.retrieve(current_user.stripe_id)
            sub = (
                customer.subscriptions.data[0] if customer.subscriptions.data else None
            )
        else:
            g.log.info("Will create a new subscription.")
            # the customer is created without a source because the stripe source token can only be used once
            # instead it will fall through to the else block because it does not have a sub
            # this block will set the default (and only) source to be the token that was just passed in
            customer = stripe.Customer.create(
                email=current_user.email,
                coupon=coupon,
                metadata={"formspree_id": current_user.id},
            )
            current_user.stripe_id = customer.id

        if sub:
            sub.plan = plan
            sub.cancel_at_period_end = False
            sub.save()
        else:
            '''
            Check if the submitted billing source is already on the customer's account
            If so, add it and delete the old one
            If not, add this billing source
            Set it as the default payment method
            '''
            stripe_token = stripe.Token.retrieve(token)
            current_cards = stripe.Customer.retrieve(current_user.stripe_id).sources.list(object='card')
            existing_matching_card = None
            for card in current_cards.auto_paging_iter():
                if stripe_token['card']['fingerprint'] == card['fingerprint']:
                    existing_matching_card = card
                    break
            new_source = customer.sources.create(source=token)['id']
            customer.default_source = new_source
            customer.save()
            if existing_matching_card:
                customer.sources.retrieve(existing_matching_card['id']).delete()
            customer.subscriptions.create(plan=plan)
    except stripe.error.CardError as e:
        g.log.warning("Couldn't charge card.", reason=e.json_body, status=e.http_status)
        return jsonify({"ok": False, "error": "Couldn't charge card."}), 403

    current_user.plan = plan
    DB.session.add(current_user)
    DB.session.commit()
    g.log.info("Subscription created.")

    return jsonify({"ok": True})


@prevent_xsrf
@login_required
def cancel():
    customer = stripe.Customer.retrieve(current_user.stripe_id)
    sub = customer.subscriptions.data[0] if customer.subscriptions.data else None

    if not sub:
        return (
            jsonify(
                {
                    "ok": False,
                    "error": "You can't do this. You are not subscribed to any plan.",
                }
            ),
            403,
        )

    reason = (request.get_json(silent=True) or {}).get("why")
    if reason:
        send_downgrade_reason_email.delay(current_user.email, reason)

    sub.cancel_at_period_end = True
    sub.save()

    g.log.info("Subscription canceled from dashboard.", account=current_user.email)

    at = datetime.datetime.fromtimestamp(sub.current_period_end).strftime(
        "%A, %B %d, %Y"
    )
    return jsonify({"ok": True, "at": at})


@prevent_xsrf
@login_required
def resubscribe():
    customer = stripe.Customer.retrieve(current_user.stripe_id)
    sub = customer.subscriptions.data[0] if customer.subscriptions.data else None

    if not sub:
        return (
            jsonify(
                {
                    "ok": False,
                    "error": "You can't do this. You are not subscribed to any plan.",
                }
            ),
            403,
        )

    try:
        sub.cancel_at_period_end = False
        sub.save()
    except stripe.error.CardError as e:
        g.log.warning("Couldn't charge card.", reason=e.json_body, status=e.http_status)
        return jsonify({"ok": False, "error": "Couldn't charge card."}), 403

    g.log.info("Resubscribed user.", account=current_user.email)
    at = datetime.datetime.fromtimestamp(sub.current_period_end).strftime(
        "%A, %B %d, %Y"
    )
    return jsonify({"ok": True, "at": at})


@prevent_xsrf
@login_required
def get_account():
    sub = None
    cards = {}
    invoices = []

    if current_user.stripe_id:
        try:
            customer = stripe.Customer.retrieve(current_user.stripe_id)

            sub = (
                customer.subscriptions.data[0] if customer.subscriptions.data else None
            )
            invoices = stripe.Invoice.list(customer=customer, limit=12)

            cards = customer.sources.list(object="card").data
            for card in cards:
                if customer.default_source == card.id:
                    card.default = True
                card.css_name = CARD_MAPPINGS[card.brand]

        except stripe.error.StripeError:
            return (
                jsonify(
                    {
                        "ok": False,
                        "error": "Failed to get your subscription details from Stripe.",
                    }
                ),
                503,
            )

    pending_emails = []
    verified_emails = []
    for e in current_user.emails.order_by(Email.registered_on.desc()):
        if e.verified:
            verified_emails.append(e.address)
        else:
            pending_emails.append(e.address)

    return jsonify(
        {
            "ok": True,
            "user": current_user.serialize(),
            "emails": {"verified": verified_emails, "pending": pending_emails},
            "cards": cards,
            "invoices": [
                {
                    "id": inv.id,
                    "date": datetime.datetime.fromtimestamp(inv.date).strftime(
                        "%A, %B %d, %Y"
                    ),
                    "attempted": inv.attempted,
                    "total": inv.total,
                    "paid": inv.paid,
                }
                for inv in invoices
            ],
            "sub": {
                "cancel_at_period_end": sub.cancel_at_period_end,
                "current_period_end": datetime.datetime.fromtimestamp(
                    sub.current_period_end
                ).strftime("%A, %B %d, %Y"),
            }
            if sub
            else None,
        }
    )


@prevent_xsrf
@login_required
@requires_feature("dashboard")
def update_account():
    patch = request.get_json()
    for attr in ["invoice_address"]:
        if attr in patch:
            setattr(current_user, attr, patch[attr])

    DB.session.add(current_user)
    DB.session.commit()
    return jsonify({"ok": True})


@prevent_xsrf
@login_required
@requires_feature("dashboard")
def add_email():
    address = request.get_json()["address"].lower().strip()
    g.log = g.log.bind(address=address, account=current_user.email)

    emails = [email.address for email in current_user.emails]
    if address in emails:
        return (
            jsonify(
                {
                    "ok": True,
                    "message": "{} already added to account.".format(address),
                    "noop": True,
                }
            ),
            200,
        )

    if (
        not current_user.has_feature("unlimited_addresses")
        and current_user.emails.count() >= settings.LINKED_EMAIL_ADDRESSES_LIMIT
    ):
        g.log.info("reached limit of linked addresses.")
        return (
            jsonify(
                {
                    "ok": False,
                    "error": (
                        "You've reached the limit of email addresses for this "
                        "account, please upgrade your account or delete one of "
                        "your addresses before adding a new one."
                    ),
                    "noop": True,
                }
            ),
            403,
        )

    try:
        g.log.info("Adding new email address to account.")
        sent = Email.send_confirmation(address, current_user.id)
        if sent:
            newEmail = Email(address=address, owner_id=current_user.id, verified=False)
            DB.session.add(newEmail)
            DB.session.commit()
            return (
                jsonify(
                    {
                        "ok": True,
                        "message": (
                            "We've sent a message with a " "verification link to {}."
                        ).format(address),
                        "noop": False,
                    }
                ),
                202,
            )
        else:
            return (
                jsonify(
                    {
                        "ok": False,
                        "error": "We couldn't sent you the verification email at {}. "
                        "Please try again later.".format(address),
                    }
                ),
                500,
            )

    except ValueError:
        return (
            jsonify(
                {
                    "ok": False,
                    "error": "{} is not a valid email address.".format(address),
                }
            ),
            400,
        )


@prevent_xsrf
@login_required
@requires_feature("dashboard")
def delete_email(address):
    from formspree.forms.models import Form, RoutingRule

    g.log = g.log.bind(address=address, account=current_user.email)

    nforms = current_user.forms.filter_by(email=address, hash=None).count()
    nrules = (
        current_user.forms.join(Form.routing_rules)
        .filter(RoutingRule.email == address)
        .count()
    )
    if nforms or nrules:
        return (
            jsonify(
                {
                    "ok": False,
                    "error": (
                        "{} is still tied to {} form{} and {} rule{}, "
                        "so it cannot be deleted."
                    ).format(
                        address,
                        nforms,
                        "" if nforms == 1 else "s",
                        nrules,
                        "" if nrules == 1 else "s",
                    ),
                }
            ),
            403,
        )

    email = Email.query.get([address, current_user.id])
    DB.session.delete(email)
    DB.session.commit()
    return jsonify({"ok": True})


@prevent_xsrf
@login_required
@requires_feature("dashboard")
def add_card():
    token = request.get_json()["token"]

    g.log = g.log.bind(account=current_user.email)

    try:
        if current_user.stripe_id:
            customer = stripe.Customer.retrieve(current_user.stripe_id)
        else:
            customer = stripe.Customer.create(
                email=current_user.email, metadata={"formspree_id": current_user.id}
            )
            current_user.stripe_id = customer.id

        # make sure this card doesn't already exist
        new_fingerprint = stripe.Token.retrieve(token).card.fingerprint
        if new_fingerprint in (
            card.fingerprint for card in customer.sources.list(object="card").data
        ):
            return jsonify({"ok": True}), 200
        else:
            customer.sources.create(source=token)
            g.log.info("Added card to Stripe account.")
            return jsonify({"ok": True}), 201

    except stripe.error.CardError as e:
        g.log.warning(
            "Couldn't add card to Stripe account.",
            reason=e.json_body,
            status=e.http_status,
        )
        return (
            jsonify(
                {
                    "ok": False,
                    "error": "Sorry, there was an error in adding your card. If this persists, please contact us.",
                }
            ),
            400,
        )
    except stripe.error.APIConnectionError:
        g.log.warning(
            "Couldn't add card to Stripe account. Failed to "
            "communicate with Stripe API."
        )
        return (
            jsonify(
                {
                    "ok": False,
                    "error": "We're unable to establish a connection with our payment "
                    "processor. For your security, we haven't added this "
                    "card to your account. Please try again later.",
                }
            ),
            503,
        )
    except stripe.error.StripeError:
        g.log.warning("Couldn't add card to Stripe account. Unknown error.")
        return (
            jsonify(
                {
                    "ok": False,
                    "error": "Sorry, an unknown error occured. Please try again "
                    "later. If this problem persists, please contact us.",
                }
            ),
            503,
        )


@prevent_xsrf
@login_required
@requires_feature("dashboard")
def change_default_card(cardid):
    customer = stripe.Customer.retrieve(current_user.stripe_id)
    customer.default_source = cardid
    customer.save()
    return jsonify({"ok": True})


@prevent_xsrf
@login_required
@requires_feature("dashboard")
def delete_card(cardid):
    customer = stripe.Customer.retrieve(current_user.stripe_id)
    customer.sources.retrieve(cardid).delete()
    g.log.info("Deleted card from account.", account=current_user.email)
    return jsonify({"ok": True})
