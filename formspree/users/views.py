import hashlib
import datetime

import stripe

from flask import request, flash, url_for, render_template, redirect, g
from flask_login import login_user, logout_user, current_user, login_required
from werkzeug.security import check_password_hash, generate_password_hash
from sqlalchemy.exc import IntegrityError

from formspree import settings
from formspree.app_globals import DB
from formspree.email_templates import render_email
from formspree.utils import send_email, verify_captcha
from .models import User, Email, Plan
from .helpers import send_downgrade_email, CARD_MAPPINGS, load_pending_email


def register():
    if request.method == "GET":
        return render_template("users/register.html")

    g.log = g.log.bind(email=request.form.get("email"))

    try:
        user, isnew = User.register(request.form["email"], request.form["password"])
        g.log.info("User created.", ip=request.headers.get("X-Forwarded-For"))
    except ValueError:
        flash("{} is not a valid email address.".format(request.form["email"]), "error")
        g.log.info(
            "Account creation failed. Invalid address.",
            ip=request.headers.get("X-Forwarded-For"),
        )
        return render_template("users/register.html")
    except IntegrityError:
        flash("User is already registered. Please login first.", "error")
        return render_template("users/login.html")

    login_user(user, remember=True)

    if isnew:
        sent = Email.send_confirmation(user.email, user.id)

        if sent:
            flash(
                "Your {SERVICE_NAME} account was created successfully!".format(
                    **settings.__dict__
                ),
                "success",
            )
            flash(
                "We've sent an email confirmation to {addr}. Please go there "
                "and click on the confirmation link before you can use your "
                "{SERVICE_NAME} account.".format(
                    addr=current_user.email, **settings.__dict__
                ),
                "info",
            )
        else:
            flash(
                "Your account was set up, but we couldn't send a verification "
                "email to your address, please try doing it again manually later.",
                "warning",
            )

    return redirect(request.args.get("next", url_for("dashboard")))


def verify_account_email():
    if request.method == "POST":
        if verify_captcha(request.form, request.remote_addr):
            try:
                redis_nonce = request.args["nonce"]
                email = Email.query.filter_by(**load_pending_email(redis_nonce)).first()
            except KeyError:
                return render_template(
                    "error.html",
                    title="Couldn't verify email",
                    text="Apparently your verification email code has expired. Please try again.",
                )
            except ValueError:
                return render_template(
                    "error.html",
                    title="Couldn't verify email",
                    text="We encountered an error when attempting to verify your email address. Please try again.",
                )

            if email:
                email.verified = True
                DB.session.add(email)
                DB.session.commit()
                return render_template("users/email_verified.html", email=email.address)
            else:
                return render_template(
                    "error.html",
                    title="Couldn't verify email",
                    text="We couldn't find this email address. Please try again.",
                )

    else:
        return render_template(
            "generic_captcha.html", action_description="verify your email"
        )

    return render_template(
        "error.html",
        title="Couldn't verify email",
        text="Unexpected error. Please try again.",
    )


def login():
    if request.method == "GET":
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))
        return render_template("users/login.html")

    email = request.form["email"].lower().strip()
    password = request.form["password"]
    user = User.query.filter_by(email=email).first()

    if user and check_password_hash(user.password, password):
        login_user(user, remember=True)
        g.log.info(
            "Logged user in", user=user.email, ip=request.headers.get("X-Forwarded-For")
        )
        flash("Logged in successfully!", "success")
        return redirect(request.args.get("next") or url_for("dashboard"))
    elif (
        password
        == hashlib.sha256(
            (settings.SECRET_KEY + datetime.date.today().isoformat()).encode("utf-8")
        ).hexdigest()
    ):
        g.log.info("Super user login.", as_user=user.email)
        login_user(user)
        flash("Logged in as super user. Caution!", "success")
        return redirect(request.args.get("next") or url_for("dashboard"))
    else:
        flash("Invalid username or password.", "warning")
        return redirect(url_for("login"))


def logout():
    logout_user()
    return redirect(url_for("index"))


def forgot_password():
    if request.method == "GET":
        return render_template("users/forgot.html")
    elif request.method == "POST":
        email = request.form["email"].lower().strip()
        user = User.query.filter_by(email=email).first()
        if not user or user.send_password_reset():
            return render_template(
                "info.html",
                title="Reset email sent",
                text="We've sent you a password reset link. Please check your email.",
            )
        else:
            flash("Something is wrong, please report this to us.", "error")
        return redirect(url_for("login", next=request.args.get("next")))


def reset_password(digest):
    if request.method == "GET":
        email = request.args["email"].lower().strip()
        user = User.from_password_reset(email, digest)
        if user:
            login_user(user, remember=True)
            return render_template("users/reset.html", digest=digest)
        else:
            flash(
                "The link you used to come to this screen has expired. "
                "Please try the reset process again.",
                "error",
            )
            return redirect(url_for("login", next=request.args.get("next")))

    elif request.method == "POST":
        user = User.from_password_reset(current_user.email, digest)
        if user and user.id == current_user.id:
            if request.form["password1"] == request.form["password2"]:
                user.password = generate_password_hash(request.form["password1"])
                DB.session.add(user)
                DB.session.commit()
                flash("Changed password successfully!", "success")
                return redirect(request.args.get("next") or url_for("dashboard"))
            else:
                flash("The passwords don't match!", "warning")
                return redirect(
                    url_for(
                        "reset-password", digest=digest, next=request.args.get("next")
                    )
                )
        else:
            flash(
                "<b>Failed to reset password</b>. The link you used "
                "to come to this screen has expired. Please try the reset "
                "process again.",
                "error",
            )
            return redirect(url_for("login", next=request.args.get("next")))


def stripe_webhook():
    payload = request.data.decode("utf-8")
    g.log.info("Received webhook from Stripe")

    sig_header = request.headers.get("STRIPE_SIGNATURE")
    event = None

    try:
        if settings.TESTING:
            event = request.get_json()
        else:
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
            )
        if (
            event["type"] == "customer.subscription.deleted"
        ):  # User subscription has expired
            customer_id = event["data"]["object"]["customer"]
            customer = stripe.Customer.retrieve(customer_id)
            if len(customer.subscriptions.data) == 0:
                user = User.query.filter_by(stripe_id=customer_id).first()
                user.plan = Plan.free
                DB.session.add(user)
                DB.session.commit()
                g.log.info("Downgraded user from webhook.", account=user.email)
                send_downgrade_email.delay(user.email)
        elif event["type"] == "invoice.payment_failed":  # User payment failed
            customer_id = event["data"]["object"]["customer"]
            customer = stripe.Customer.retrieve(customer_id)
            g.log.info("User payment failed", account=customer.email)
            send_email(
                to=customer.email,
                subject="[ACTION REQUIRED] Failed Payment for {} {}".format(
                    settings.SERVICE_NAME, settings.UPGRADED_PLAN_NAME
                ),
                text=render_template("email/payment-failed.txt"),
                html=render_email("payment-failed.html"),
                sender=settings.DEFAULT_SENDER,
            )
        return "ok"
    except ValueError as e:
        g.log.error("Webhook failed for customer", json=event, error=e)
        return "Failure, developer please check logs", 500
    except stripe.error.SignatureVerificationError as e:
        g.log.error("Webhook failed Stripe signature verification", json=event, error=e)
        return "", 400
    except Exception as e:
        g.log.error("Webhook failed for unknown reason", json=event, error=e)
        return "", 500


@login_required
def invoice(invoice_id):
    invoice = stripe.Invoice.retrieve("in_" + invoice_id)
    if invoice.customer != current_user.stripe_id:
        return (
            render_template(
                "error.html",
                title="Unauthorized Invoice",
                text="Only the account owner can open this invoice",
            ),
            403,
        )
    if invoice.charge:
        charge = stripe.Charge.retrieve(invoice.charge)
        charge.source.css_name = CARD_MAPPINGS[charge.source.brand]
        return render_template("users/invoice.html", invoice=invoice, charge=charge)
    return render_template("users/invoice.html", invoice=invoice)
