import sys
import hashlib
import datetime

import click
from flask_migrate import Migrate

from formspree import app, settings
from formspree.app_globals import redis_store, DB
from formspree.forms.helpers import REDIS_COUNTER_KEY, HASHIDS_CODEC
from formspree.forms.models import Form

# add flask-migrate commands
migrate = Migrate(app, DB)


@app.cli.command()
@click.option("-i", "--id", default=None, help="form id")
@click.option("-H", "--host", default=None, help="referer hostname")
@click.option("-e", "--email", default=None, help="form email")
def monthly_counters(email=None, host=None, id=None, month=datetime.date.today().month):
    if id:
        query = [Form.query.get(id)]
    elif email and host:
        query = Form.query.filter_by(email=email, host=host)
    elif email and not host:
        query = Form.query.filter_by(email=email)
    elif host and not email:
        query = Form.query.filter_by(host=host)
    else:
        print("supply each --email or --form or both (or --id).")
        return 1

    for form in query:
        nsubmissions = (
            redis_store.get(REDIS_COUNTER_KEY(form_id=form.id, month=month)) or 0
        )
        print("%s submissions for %s" % (nsubmissions, form))


@app.cli.command()
@click.argument("hashid")
def hashid_to_id(hashid):
    print(HASHIDS_CODEC.decode(hashid)[0])


@app.cli.command()
def super_user_password():
    print(
        hashlib.sha256(
            (settings.SECRET_KEY + datetime.date.today().isoformat()).encode("utf-8")
        ).hexdigest()
    )


@app.cli.command(context_settings={"ignore_unknown_options": True})
@click.argument("args", nargs=-1)
def test(args):
    import pytest

    argv = list(args)

    for arg in argv:
        if not arg.startswith("-"):
            break
    else:
        argv.insert(0, "tests/")

    errno = pytest.main(argv)
    sys.exit(errno)
