import re
import uuid

from flask import render_template

from formspree import settings
from formspree.app_globals import redis_store, celery
from formspree.email_templates import render_email
from formspree.utils import send_email


CARD_MAPPINGS = {
    "Visa": "cc-visa",
    "American Express": "cc-amex",
    "MasterCard": "cc-mastercard",
    "Discover": "cc-discover",
    "JCB": "cc-jcb",
    "Diners Club": "cc-diners-club",
    "Unknown": "credit-card",
}


REDIS_EMAIL_KEY = "email_{nonce}".format


def store_pending_email(email, userid):
    nonce = uuid.uuid4()
    key = REDIS_EMAIL_KEY(nonce=nonce)
    redis_store.set(key, email + ",{}".format(userid))
    redis_store.expire(key, 300000)
    return nonce


def load_pending_email(nonce):
    key = REDIS_EMAIL_KEY(nonce=nonce)
    value = redis_store.get(key)
    if value is None:
        raise KeyError("no temp email stored.")
    redis_store.delete(key)
    values = value.decode("utf-8").split(",")
    if len(values) != 2:
        raise ValueError("temp email value is invalid: " + value)
    else:
        return {"address": values[0], "owner_id": int(values[1])}


def get_current_sale(plan):
    if not settings.CURRENT_SALE:
        return None
    (pattern, coupon) = settings.CURRENT_SALE.split()
    return coupon if re.match(pattern, plan) else None


@celery.task()
def send_downgrade_email(customer_email):
    send_email(
        to=customer_email,
        subject="Successfully downgraded from {} {}".format(
            settings.SERVICE_NAME, settings.UPGRADED_PLAN_NAME
        ),
        text=render_template("email/downgraded.txt"),
        html=render_email("downgraded.html"),
        sender=settings.DEFAULT_SENDER,
    )


@celery.task()
def send_downgrade_reason_email(customer_email, reason):
    send_email(
        to=settings.CONTACT_EMAIL,
        reply_to=customer_email,
        subject="A customer has downgraded from {}".format(settings.UPGRADED_PLAN_NAME),
        text=render_template("email/downgraded_reason.txt", reason=reason),
        sender=settings.DEFAULT_SENDER,
    )
