import os
import time
import logging
from unittest.mock import patch, DEFAULT
from multiprocessing import Process

import pytest
from werkzeug.serving import run_simple
from pyppeteer import launch

from formspree import settings
from formspree.create_app import create_app
from formspree.app_globals import DB, redis_store, celery
from urllib.parse import urlparse


@pytest.fixture
def msend():
    with patch("formspree.utils.send_email") as msend:

        def side_effect(*args, **kwargs):
            msend(*args, **kwargs)
            return DEFAULT

        with patch("formspree.users.models.send_email", side_effect=side_effect), patch(
            "formspree.users.views.send_email", side_effect=side_effect
        ), patch("formspree.users.helpers.send_email", side_effect=side_effect), patch(
            "formspree.forms.models.send_email", side_effect=side_effect
        ), patch(
            "formspree.forms.views.send_email", side_effect=side_effect
        ):
            yield msend


@pytest.fixture
def setup_settings():
    if os.getenv("HEROKU_CI") == "true":
        settings.SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")
    else:
        settings.SQLALCHEMY_DATABASE_URI = os.getenv("TEST_DATABASE_URL")

    settings.MONTHLY_SUBMISSIONS_LIMIT = 2
    settings.OVERLIMIT_NOTIFICATION_QUANTITY = 2
    settings.ARCHIVED_SUBMISSIONS_LIMIT = 4
    settings.FORM_LIMIT_DECREASE_ACTIVATION_SEQUENCE = 0
    settings.EXPENSIVELY_WIPE_SUBMISSIONS_FREQUENCY = 1
    settings.PRESERVE_CONTEXT_ON_EXCEPTION = False
    settings.STRIPE_PUBLISHABLE_KEY = settings.STRIPE_TEST_PUBLISHABLE_KEY
    settings.STRIPE_SECRET_KEY = settings.STRIPE_TEST_SECRET_KEY
    settings.PRESERVE_CONTEXT_ON_EXCEPTION = False
    settings.SERVICE_URL = "http://localhost:5000"
    settings.SERVER_NAME = urlparse(settings.SERVICE_URL).netloc
    settings.TESTING = True


@pytest.fixture()
def client(setup_settings):
    app = create_app()
    # debug: print all SQL statements
    # logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)
    celery.conf.task_always_eager = True

    with app.app_context():
        DB.create_all()

        with app.test_request_context():
            yield app.test_client()

        DB.session.remove()
        DB.drop_all()

    redis_store.flushdb()


@pytest.fixture()
@pytest.mark.asyncio
async def page(setup_settings, msend):
    logging.getLogger().addHandler(logging.StreamHandler())

    # backend_app and test_app are basically the same thing
    # but we must create two so they don't reuse each others'
    # database connections, which causes OperationalError
    test_app = create_app()
    backend_app = create_app()
    celery.conf.task_always_eager = True

    # we rely test_app it to setup the database
    with test_app.app_context():
        DB.create_all()

    # we pass backend_app to the sub process that will respond to our frontend
    host, port = settings.SERVICE_URL.split("://")[1].split(":")
    p = Process(target=run_simple, args=(host, int(port), backend_app))
    p.start()

    # launch the browser
    opts = {"headless": True}
    if os.getenv("GOOGLE_CHROME_BIN"):
        opts["executablePath"] = os.getenv("GOOGLE_CHROME_SHIM")

    browser = await launch(opts)
    page = await browser.newPage()

    # at the same time we use the test_app to execute queries inside the tests
    with test_app.app_context():
        yield page

    # terminate browser and backend app
    p.terminate()
    await browser.close()

    time.sleep(0.1)
    if p.is_alive():
        p.kill()

    # we also rely on test_app to purge the database
    with test_app.app_context():
        DB.session.remove()
        DB.drop_all()
    redis_store.flushdb()
