import traceback
import uuid

from flask import request, render_template, g, redirect, url_for
from jinja2 import TemplateNotFound
from flask_login import login_required

from .helpers import PUBLIC_PARAMS


@login_required
def serve_dashboard(hashid=None, s=None):
    return render_template("static_pages/dashboard.html", params=PUBLIC_PARAMS)


def serve_plans():
    g.plans = True
    return render_template("static_pages/dashboard.html", params=PUBLIC_PARAMS)


def default(template="index"):
    template = template if template.endswith(".html") else template + ".html"
    try:
        return render_template(
            "static_pages/" + template, is_redirect=request.args.get("redirected")
        )
    except TemplateNotFound:
        return render_template("static_pages/404.html"), 404


def exception_handler(e):
    trace_id = uuid.uuid4()
    g.log.error(traceback.format_exc(), trace_id=trace_id)
    return (
        render_template("static_pages/500.html", trace_id=trace_id),
        (e.code if hasattr(e, "code") else 500),
    )


def error_400(e):
    return render_template("static_pages/400.html"), 400


def error_404(e):
    return render_template("static_pages/404.html"), 404


def error_405(e):
    return render_template("static_pages/405.html"), 405


def favicon():
    return redirect(url_for("static", filename="img/favicon.ico"))
