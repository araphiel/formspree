import os
import json

from urllib.parse import urlparse

trueish = ["True", "true", "1", "yes"]

# load a bunch of environment
DEBUG = os.getenv("DEBUG") in trueish
SQLALCHEMY_ECHO = os.getenv("SQLALCHEMY_ECHO") in trueish
TESTING = os.getenv("TESTING") in trueish
LOG_LEVEL = os.getenv("LOG_LEVEL") or "debug"
PREFERRED_URL_SCHEME = os.getenv("PREFERRED_URL_SCHEME", "https")

SQLALCHEMY_DATABASE_URI = os.getenv("SQLALCHEMY_DATABASE_URI") or os.getenv(
    "DATABASE_URL"
)
SQLALCHEMY_TRACK_MODIFICATIONS = False

SECRET_KEY = os.getenv("SECRET_KEY") or ""
HASHIDS_SALT = os.getenv("HASHIDS_SALT") or ""
NONCE_SECRET = (os.getenv("NONCE_SECRET") or "").encode("utf-8")
PUBLIC_USERID_SALT = os.getenv("PUBLIC_USERID_SALT", "")
SPAM_SECRET = os.getenv("SPAM_SECRET") or ""

GRANDFATHER_MONTHLY_LIMIT = 1000
OVERLIMIT_NOTIFICATION_QUANTITY = 25
MONTHLY_SUBMISSIONS_LIMIT = int(os.getenv("MONTHLY_SUBMISSIONS_LIMIT") or 100)
ARCHIVED_SUBMISSIONS_LIMIT = int(os.getenv("ARCHIVED_SUBMISSIONS_LIMIT") or 1000)
LINKED_EMAIL_ADDRESSES_LIMIT = int(os.getenv("LINKED_EMAIL_ADDRESSES_LIMIT") or 3)
FORM_LIMIT_DECREASE_ACTIVATION_SEQUENCE = int(
    os.getenv("FORM_LIMIT_DECREASE_ACTIVATION_SEQUENCE") or 0
)
FORM_AJAX_DISABLE_ACTIVATION_SEQUENCE = int(
    os.getenv("FORM_AJAX_DISABLE_ACTIVATION_SEQUENCE") or 0
)
PROMO_DELAY = int(os.getenv("PROMO_DELAY", "10000"))
FAILED_WEBHOOKS_ALLOWED = 6
CURRENT_SALE = os.getenv("CURRENT_SALE", None)

EXPENSIVELY_WIPE_SUBMISSIONS_FREQUENCY = float(
    os.getenv("EXPENSIVELY_WIPE_SUBMISSIONS_FREQUENCY") or 0.2
)
REDIS_URL = (
    os.getenv("REDISTOGO_URL")
    or os.getenv("REDISCLOUD_URL")
    or os.getenv("REDIS_URL")
    or "redis://localhost:6379"
)

SERVICE_NAME = os.getenv("SERVICE_NAME") or "Forms"
UPGRADED_PLAN_NAME = os.getenv("UPGRADED_PLAN_NAME") or "Gold"
SERVICE_URL = (
    "https://" + os.environ["HEROKU_APP_NAME"] + ".herokuapp.com"
    if "HEROKU_APP_NAME" in os.environ
    else os.getenv("SERVICE_URL") or "http://example.com"
)
SERVER_NAME = urlparse(SERVICE_URL).netloc

CDN_URL = (
    "https://" + os.getenv("CDN_DOMAIN")
    if "CDN_DOMAIN" in os.environ
    else os.getenv("SERVICE_URL")
)
CDN_DEBUG = os.getenv("CDN_DEBUG", "True") in trueish
CDN_TIMESTAMP = os.getenv("CDN_TIMESTAMP", "False") in trueish
TEST_URL = os.getenv("TEST_URL", "http://test.example.com")
CONTACT_EMAIL = os.getenv("CONTACT_EMAIL") or "team@example.com"
NEWSLETTER_EMAIL = os.getenv("NEWSLETTER_EMAIL") or "signup@example.com"
DEFAULT_SENDER = os.getenv("DEFAULT_SENDER") or "Forms Team <submissions@example.com>"
ACCOUNT_SENDER = os.getenv("ACCOUNT_SENDER") or DEFAULT_SENDER
API_ROOT = os.getenv("API_ROOT") or "//example.com"

SENDGRID_USERNAME = os.getenv("SENDGRID_USERNAME")
SENDGRID_PASSWORD = os.getenv("SENDGRID_PASSWORD")

STRIPE_TEST_PUBLISHABLE_KEY = os.getenv("STRIPE_TEST_PUBLISHABLE_KEY")
STRIPE_TEST_SECRET_KEY = os.getenv("STRIPE_TEST_SECRET_KEY")
STRIPE_PUBLISHABLE_KEY = (
    os.getenv("STRIPE_PUBLISHABLE_KEY") or STRIPE_TEST_PUBLISHABLE_KEY
)
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY") or STRIPE_TEST_SECRET_KEY
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

AMPLITUDE_KEY = os.getenv("AMPLITUDE_KEY", "123456")
GA_KEY = os.getenv("GA_KEY") or "123456"
OLARK_KEY = os.getenv("OLARK_KEY", "123456")

RECAPTCHA_SECRET = os.getenv("RECAPTCHA_SECRET")
RECAPTCHA_KEY = os.getenv("RECAPTCHA_KEY")

RATE_LIMIT = os.getenv("RATE_LIMIT", "120 per hour")
REDIS_RATE_LIMIT = os.getenv("REDIS_URL")  # heroku-redis

CONTACT_FORM_HASHID = os.getenv("CONTACT_FORM_HASHID", CONTACT_EMAIL)

CELERY_BROKER_URL = os.getenv("REDIS_URL")

PLUGINS_MAX_FAILURES = int(os.getenv("PLUGINS_MAX_FAILURES", "10"))

GOOGLE_CLIENT_CONFIG = json.loads(os.getenv("GOOGLE_CLIENT_CONFIG", "{}"))
TRELLO_API_KEY = os.getenv("TRELLO_API_KEY")
TRELLO_OAUTH_SECRET = os.getenv("TRELLO_OAUTH_SECRET")
SLACK_CLIENT_ID = os.getenv("SLACK_CLIENT_ID")
SLACK_CLIENT_SECRET = os.getenv("SLACK_CLIENT_SECRET")
MAILCHIMP_CLIENT_ID = os.getenv("MAILCHIMP_CLIENT_ID")
MAILCHIMP_CLIENT_SECRET = os.getenv("MAILCHIMP_CLIENT_SECRET")
