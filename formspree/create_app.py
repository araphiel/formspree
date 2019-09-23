import json
import os
import re
import structlog

from flask import Flask, g, request, url_for, redirect, jsonify
from flask_login import LoginManager
from flask_limiter import Limiter
from flask_limiter.util import get_ipaddr

from . import routes, settings
from .utils import request_wants_json
from .app_globals import DB, redis_store, cdn, celery
from .users.models import User
from .static_pages.views import exception_handler, error_400, error_404, error_405


def configure_login(app):
    login_manager = LoginManager()
    login_manager.init_app(app)

    @login_manager.unauthorized_handler
    def unauthorized():
        if request_wants_json() or request.path.startswith("/api-int/"):
            return jsonify({"error": "User not logged."}), 401
        return redirect(url_for("login"))

    @login_manager.user_loader
    def load_user(id):
        return User.query.get(int(id))


def configure_ssl_redirect(app):
    @app.before_request
    def get_redirect():
        if (
            not request.is_secure
            and not request.headers.get("X-Forwarded-Proto", "http") == "https"
            and request.method == "GET"
            and request.url.startswith("http://")
        ):
            url = request.url.replace("http://", "https://", 1)
            r = redirect(url, code=301)
            return r


def configure_logger(app):
    def processor(_, method, event):
        # we're on heroku, so we can count that heroku will
        # timestamp the logs.
        levelcolor = {"debug": 32, "info": 34, "warning": 33, "error": 31}.get(
            method, 37
        )

        msg = event.pop("event")

        rest = []
        for k, v in event.items():
            if type(v) is bytes:
                v = v.encode("utf-8", "ignore")
            rest.append("\x1b[{}m{}\x1b[0m={}".format(levelcolor, k.upper(), v))
        rest = " ".join(rest)

        try:
            current_request = request.headers is not None
        except RuntimeError:
            # no request exists if called outside flask's request context
            current_request = False

        return "\x1b[{clr}m{met}\x1b[0m [\x1b[35m{rid}\x1b[0m] {msg} {rest}".format(
            clr=levelcolor,
            met=method.upper(),
            rid=request.headers.get("X-Request-Id", "~")[-7:]
            if current_request
            else "~",
            msg=msg,
            rest=rest,
        )

    structlog.configure(
        processors=[structlog.processors.ExceptionPrettyPrinter(), processor]
    )

    logger = structlog.get_logger()

    @app.before_request
    def get_request_id():
        g.log = logger.new()


def create_app():
    app = Flask(__name__)
    app.config.from_object(settings)

    DB.init_app(app)
    redis_store.init_app(app)
    routes.configure_routes(app)
    configure_login(app)
    configure_logger(app)

    app.register_error_handler(400, error_400)
    app.register_error_handler(404, error_404)
    app.register_error_handler(405, error_405)
    app.register_error_handler(Exception, exception_handler)

    app.jinja_env.filters["json"] = json.dumps

    def epoch_to_date(s):
        import datetime

        return datetime.datetime.fromtimestamp(s).strftime("%B %-d, %Y")

    def epoch_to_ts(s):
        import datetime

        return datetime.datetime.fromtimestamp(s).strftime("%m-%-d-%Y %H:%M")

    app.jinja_env.filters["epoch_to_date"] = epoch_to_date
    app.jinja_env.filters["epoch_to_ts"] = epoch_to_ts
    app.config["CDN_DOMAIN"] = os.getenv(
        "CDN_DOMAIN", re.sub("https?://", "", settings.SERVICE_URL)
    )
    app.config["CDN_HTTPS"] = True
    cdn.init_app(app)

    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            if app.config["TESTING"]:
                # When testing, celery tasks are called eagerly, from the same thread
                # so don't push an app context, the request's app context is already there
                return self.run(*args, **kwargs)
            else:
                with app.app_context():
                    g.log = structlog.get_logger().new()
                    return self.run(*args, **kwargs)

    celery.Task = ContextTask

    if not app.debug and not app.testing:
        configure_ssl_redirect(app)

    Limiter(
        app,
        key_func=get_ipaddr,
        global_limits=[settings.RATE_LIMIT],
        storage_uri=settings.REDIS_RATE_LIMIT,
    )

    return app
