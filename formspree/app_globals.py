import stripe
from flask_sqlalchemy import SQLAlchemy
from flask_cdn import CDN
from flask_redis import Redis
from celery import Celery
from itsdangerous import URLSafeSerializer

from . import settings

DB = SQLAlchemy()
redis_store = Redis()
stripe.api_key = settings.STRIPE_SECRET_KEY
stripe.api_version = "2018-09-24"
cdn = CDN()
celery = Celery(__name__, broker=settings.CELERY_BROKER_URL)
spam_serializer = URLSafeSerializer(settings.SPAM_SECRET)
