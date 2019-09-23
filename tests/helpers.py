import re
import random
import string

from formspree.app_globals import DB
from formspree.users.models import User, Plan
from formspree.forms.models import Form

PASSWORD = "xxxxxxxx"


def parse_confirmation_link_sent(email_text):
    matchlink = re.search(r"Link: ([^?]+)\?(\S+)", email_text)
    if not matchlink:
        raise ValueError("No link found in email body:", email_text)

    link = matchlink.group(1)
    qs = matchlink.group(2)

    return link, qs


def create_user_and_form(client, login=True):
    # create user and form
    username = "".join([random.choice(string.ascii_lowercase) for i in range(10)])
    email = username + "@example.com"
    user, _ = User.register(email, PASSWORD)
    user.plan = Plan.gold
    user.emails[0].verified = True
    form = Form(username + "@example.com", name="example", owner=user, confirmed=True)
    DB.session.add(user)
    DB.session.add(form)
    DB.session.commit()

    if login:
        client.post("/login", data={"email": email, "password": PASSWORD})

    return user, form


def create_and_activate_form(client, email, host):
    # create user and form
    form = Form(email, host=host, confirmed=True)
    DB.session.add(form)
    DB.session.commit()
    return form
