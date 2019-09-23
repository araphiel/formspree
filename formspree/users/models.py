import hmac
import hashlib
from datetime import datetime

from flask import url_for, render_template, g
from flask_login import current_user
from werkzeug.security import check_password_hash, generate_password_hash
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from formspree import settings
from formspree.app_globals import DB
from formspree.email_templates import render_email
from formspree.utils import send_email, is_valid_email
from .helpers import store_pending_email


class Product(object):
    free = "free"
    gold = "gold"
    platinum = "platinum"


class Plan(DB.Enum):
    free = "v1_free"
    gold = "v1_gold"
    gold_yearly = "v1_gold_yearly"
    platinum = "v1_platinum"
    platinum_yearly = "v1_platinum_yearly"

    feature_defs = {
        "base": {
            "name": "Easy Setup",
            "description": (
                "No PHP, JS, or registration needed. Just name your form fields, "
                "point the action to us, and submit the form once to activate. "
                "It takes only a few minutes to get your form up and running."
            ),
        },
        "replyto": {
            "name": "Flexible Email Settings",
            "description": (
                "Control the reply-to, subject and cc attributes of your emails "
                "via special hidden input fields. Configure emails to match your "
                "workflow."
            ),
        },
        "recaptcha": {
            "name": "Spam Protection",
            "description": (
                "All forms come with a reCAPTCHA that uses machine learning "
                "techniques to fight spam. For non-English forms, choose from 93 "
                "languages for the reCAPTCHA page."
            ),
        },
        "thankyou": {
            "name": "Custom Thank You Page",
            "description": (
                'By default, a user is shown a Formspree "Thank You" page after '
                "submission. You can provide an alternative URL per form to use instead."
            ),
        },
        "archive": {
            "name": "Submissions Archive",
            "description": (
                "If you ever missed a submission email, you can just login and read "
                "your last 1000 submissions, all listed and timestamped with full "
                "data. Also, the submissions can be exported to CSV or JSON!"
            ),
        },
        "ajax": {
            "name": "Ajax Forms",
            "description": (
                "Use AJAX to submit forms — this even works cross-origin. Create a "
                "new form in your account dashboard and set the Accept header on "
                "your form to application/json."
            ),
        },
        "disable_recaptcha": {
            "name": "Disable Recaptcha",
            "description": (
                "Don't want your users to complete a reCAPTCHA? With Gold "
                "Registration, each form now comes with the option to disable the "
                "reCAPTCHA or leave it enabled, so you can maintain complete control."
            ),
        },
        "dashboard": {
            "name": "Private Emails",
            "description": (
                "Use a random string instead of your email address in the action "
                "attribute of your form. Your email address will remain unknown to "
                "spam-bots and human visitors."
            ),
        },
        "unlimited": {
            "name": "Unlimited Form Submissions",
            "description": (
                "Formspree is free for 50 submissions per form per month. Getting "
                "more than 50 submissions each month? No problem, there is an "
                "upgrade path to unlimited submissions."
            ),
        },
        "plugins": {
            "name": "Third-party Plugins",
            "description": (
                "Get your form submissions automatically replicated to "
                "third-party applications through our plugins for Google "
                "Sheets, Mailchimp and Webhooks."
            ),
        },
        "whitelabel": {
            "name": "White-label Forms",
            "description": (
                "Replace the Formspree branding with your own, and send submissions "
                "using a custom from name and email template that’s familiar to "
                "your clients."
            ),
        },
        "unlimited_addresses": {
            "name": "Unlimited Client Emails",
            "description": (
                "Pre-verify your clients’ email addresses on your account so you "
                "can set up and manage all their forms in one place."
            ),
        },
        "custom_emails": {
            "name": "Custom Email Templates",
            "description": (
                "Customize the content and style of your submission emails by "
                "changing the logo and font, or replace the email markup with your own."
            ),
        },
        "api_access": {
            "name": "API Access",
            "description": (
                "Fetch all your submissions programmatically from a JSON HTTP "
                "endpoint without having to login or share your password."
            ),
        },
        "submission_routing": {
            "name": "Routing rules",
            "description": (
                "Route submissions to different emails based on field values."
            ),
        },
    }

    plan_defs = {
        "v1_free": {
            "product": Product.free,
            "price": 0,
            "features": ["base", "replyto", "recaptcha"],
        },
        "gold": {  # the old gold still shines.
            "product": Product.gold,
            "price": 9.99,
            "features": [
                # Free
                "base",
                "replyto",
                "recaptcha",
                # Gold legacy
                "unlimited_addresses",
                # Gold
                "thankyou",
                "archive",
                "ajax",
                "disable_recaptcha",
                "dashboard",
                "unlimited",
                "plugins",
            ],
        },
        "v1_gold": {
            "product": Product.gold,
            "price": 12,
            "features": [
                # Free
                "base",
                "replyto",
                "recaptcha",
                # Gold
                "thankyou",
                "archive",
                "ajax",
                "disable_recaptcha",
                "dashboard",
                "unlimited",
                "plugins",
                "api_access",
            ],
        },
        "v1_gold_yearly": {
            "product": Product.gold,
            "price": 120,
            "features": [
                # Free
                "base",
                "replyto",
                "recaptcha",
                # Gold
                "thankyou",
                "archive",
                "ajax",
                "disable_recaptcha",
                "dashboard",
                "unlimited",
                "plugins",
                "api_access",
            ],
        },
        "v1_platinum": {
            "product": Product.platinum,
            "price": 48,
            "features": [
                # Free
                "base",
                "replyto",
                "recaptcha",
                # Gold
                "thankyou",
                "archive",
                "ajax",
                "disable_recaptcha",
                "dashboard",
                "unlimited",
                "plugins",
                "api_access",
                # Platinum
                "whitelabel",
                "unlimited_addresses",
                "custom_emails",
                "submission_routing",
            ],
        },
        "v1_platinum_yearly": {
            "product": Product.platinum,
            "price": 480,
            "features": [
                # Free
                "base",
                "replyto",
                "recaptcha",
                # Gold
                "thankyou",
                "archive",
                "ajax",
                "disable_recaptcha",
                "dashboard",
                "unlimited",
                "plugins",
                "api_access",
                # Platinum
                "whitelabel",
                "unlimited_addresses",
                "custom_emails",
                "submission_routing",
            ],
        },
    }

    @classmethod
    def has_feature(cls, plan, feature_id):
        return feature_id in cls.plan_defs[plan]["features"]


def _merge_plan_details(plan):
    """ conveneince method for building plan lists"""
    plan_def = Plan.plan_defs[plan].copy()
    plan_def["stripe_plan"] = plan
    plan_def["features"] = [Plan.feature_defs[f] for f in plan_def["features"]]
    return plan_def


Product.product_defs = [
    {
        "id": Product.free,
        "name": "Free",
        "description": "No Registration",
        "monthly": _merge_plan_details(Plan.free),
        "yearly": None,
    },
    {
        "id": Product.gold,
        "name": "Gold",
        "description": "For Professionals",
        "monthly": _merge_plan_details(Plan.gold),
        "yearly": _merge_plan_details(Plan.gold_yearly),
    },
    {
        "id": Product.platinum,
        "name": "Platinum",
        "description": "For Agencies",
        "monthly": _merge_plan_details(Plan.platinum),
        "yearly": _merge_plan_details(Plan.platinum_yearly),
    },
]


class User(DB.Model):
    __tablename__ = "users"

    id = DB.Column(DB.Integer, primary_key=True)
    email = DB.Column(DB.Text, unique=True, index=True)
    password = DB.Column(DB.String(100))
    plan = DB.Column(DB.Enum(*Plan.plan_defs.keys(), name="plans"), nullable=False)
    stripe_id = DB.Column(DB.String(50))
    registered_on = DB.Column(DB.DateTime)
    invoice_address = DB.Column(DB.Text)

    emails = DB.relationship("Email", backref="owner", lazy="dynamic")

    @property
    def verified_addresses(self):
        return [email.address for email in self.emails if email.verified]

    @property
    def forms(self):
        from formspree.forms.models import Form

        by_email = (
            DB.session.query(Form)
            .join(Email, Email.address == func.normalize_email(Form.email))
            .join(User, User.id == Email.owner_id)
            .filter(User.id == self.id)
        )
        by_creation = (
            DB.session.query(Form)
            .join(User, User.id == Form.owner_id)
            .filter(User.id == self.id)
        )
        return by_creation.union(by_email)

    def __init__(self, email, password):
        email = email.lower().strip()
        if not is_valid_email(email):
            raise ValueError("Cannot create User. %s is not a valid email." % email)

        self.email = email
        self.password = generate_password_hash(password)
        self.plan = Plan.free
        self.registered_on = datetime.utcnow()

    def __repr__(self):
        return "<User %s, email=%s, plan=%s>" % (self.id, self.email, self.plan)

    def serialize(self):
        return {
            "id": self.public_id,
            "email": self.email,
            "product": Plan.plan_defs[self.plan]["product"],
            "plan": self.plan,
            "registered_on": self.registered_on.strftime("%I:%M %p UTC - %d %B %Y"),
            "features": {f: True for f in self.features},
            "invoice_address": self.invoice_address,
        }

    @property
    def is_authenticated(self):
        return True

    @property
    def is_active(self):
        return True

    @property
    def is_anonymous(self):
        return False

    @property
    def features(self):
        return Plan.plan_defs[self.plan]["features"]

    @property
    def public_id(self):
        """ 
        public_id is a one-way hash of the id. It's used to provide a stable
        id for analytics tools that won't change even if the user email changes.
        However, it can't be used to look up the user. Email or other field is
        necessary for this.
        """
        h = hashlib.blake2b(digest_size=10, salt=settings.PUBLIC_USERID_SALT.encode())
        h.update(self.id.to_bytes(length=16, byteorder="big"))
        return h.hexdigest()

    def has_feature(self, feature_id):
        return Plan.has_feature(self.plan, feature_id)

    def get_id(self):
        return self.id

    def reset_password_digest(self):
        return hmac.new(
            settings.NONCE_SECRET,
            "id={0}&password={1}".format(self.id, self.password).encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def send_password_reset(self):
        g.log.info("Sending password reset.", account=self.email)

        digest = self.reset_password_digest()
        link = url_for(
            "reset-password", digest=digest, email=self.email, _external=True
        )
        res = send_email(
            to=self.email,
            subject="Reset your %s password!" % settings.SERVICE_NAME,
            text=render_template(
                "email/reset-password.txt", addr=self.email, link=link
            ),
            html=render_email("reset-password.html", add=self.email, link=link),
            sender=settings.ACCOUNT_SENDER,
        )
        if not res[0]:
            g.log.info("Failed to send email.", reason=res[1], code=res[2])
            return False
        else:
            return True

    @classmethod
    def register(cls, email, password):
        try:
            user = cls(email, password)
            DB.session.add(user)
            DB.session.commit()

            newEmail = Email(address=user.email, owner_id=user.id, verified=False)
            DB.session.add(newEmail)
            DB.session.commit()
            return user, True
        except ValueError as e:
            DB.session.rollback()
            raise e
        except IntegrityError as ie:
            DB.session.rollback()
            registered = cls.query.filter_by(email=email).first()
            if registered and check_password_hash(registered.password, password):
                return registered, False
            raise ie

    @classmethod
    def from_password_reset(cls, email, digest):
        user = User.query.filter_by(email=email).first()
        if not user:
            return None

        what_should_be = user.reset_password_digest()
        if digest == what_should_be:
            return user
        else:
            return None


class Email(DB.Model):
    __tablename__ = "emails"

    """
    emails added here are already confirmed and can be trusted.
    """

    address = DB.Column(DB.Text, primary_key=True)
    owner_id = DB.Column(
        DB.Integer,
        DB.ForeignKey("users.id"),
        nullable=False,
        index=True,
        primary_key=True,
    )
    verified = DB.Column(DB.Boolean, default=DB.false)
    registered_on = DB.Column(DB.DateTime, default=DB.func.now())

    def __repr__(self):
        verified = "[✓]" if self.verified else "[ ]"
        return "<Email {} owner={} {}>".format(self.address, self.owner_id, verified)

    @staticmethod
    def send_confirmation(addr, user_id):
        g.log = g.log.new(address=addr, user_id=user_id)
        g.log.info("Sending email confirmation for new address on account.")

        addr = addr.lower().strip()
        if not is_valid_email(addr):
            g.log.info("Failed. Invalid address.")
            raise ValueError(
                "Cannot send confirmation. " "{} is not a valid email.".format(addr)
            )

        link = url_for(
            "verify-account-email",
            nonce=store_pending_email(addr, user_id),
            _external=True,
        )
        res = send_email(
            to=addr,
            subject="Action Required: Verify email linked to %s"
            % settings.SERVICE_NAME,
            text=render_template(
                "email/verify-email-in-account.txt",
                owner_email=current_user.email,
                email=addr,
                link=link,
            ),
            html=render_email(
                "verify-email-in-account.html",
                owner_email=current_user.email,
                email=addr,
                link=link,
            ),
            sender=settings.ACCOUNT_SENDER,
        )
        if not res[0]:
            g.log.info("Failed to send email.", reason=res[1], code=res[2])
            return False
        else:
            return True
