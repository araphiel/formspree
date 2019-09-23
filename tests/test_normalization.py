from functools import partial

import pytest

from formspree import settings
from formspree.app_globals import DB
from formspree.forms.models import Form, Submission
from formspree.users.models import User, Email

from .helpers import create_user_and_form

hosts = [
    "example.com/contact",
    "example.com/contact/",
    "www.example.com/contact",
    "www.example.com/contact/",
    "example.com/contact.html",
    "example.com/contact/index.html",
    "www.example.com/contact.html",
    "www.example.com/contact/index.html",
]

email = "example@example.com"


def _revert(arc, sub):
    settings.ARCHIVED_SUBMISSIONS_LIMIT = arc
    settings.MONTHLY_SUBMISSIONS_LIMIT = sub


revert = partial(
    _revert, settings.ARCHIVED_SUBMISSIONS_LIMIT, settings.MONTHLY_SUBMISSIONS_LIMIT
)


def prepare():
    settings.ARCHIVED_SUBMISSIONS_LIMIT = 100
    settings.MONTHLY_SUBMISSIONS_LIMIT = 100


@pytest.mark.parametrize("host", hosts)
def test_backwards_single(client, msend, host):
    """
    Here we have a single form with one of the 8 host formats,
    then try to submit using all the 8.
    Everything must succeed.
    """

    prepare()
    try:
        f = Form(email=email, confirmed=True, host=host)
        DB.session.add(f)
        DB.session.commit()

        for referrer in hosts:
            r = client.post(
                "/" + email,
                headers={"Referer": "http://" + referrer},
                data={"name": "example"},
            )

            assert 1 == Form.query.count()
            assert r.status_code == 302
            assert "next" in r.location

        assert len(hosts) == Form.query.first().submissions.count()

    finally:
        revert()


@pytest.mark.parametrize("confirmed_host", hosts)
def test_backwards_multiple(client, msend, confirmed_host):
    """
    Same as previous, but now instead of having a single form, we have all,
    but each time only one of the them is confirmed.
    """

    prepare()
    try:
        for host in hosts:
            f = Form(email=email, confirmed=(host == confirmed_host), host=host)
            DB.session.add(f)
            DB.session.commit()

        for referer in hosts:
            r = client.post(
                "/" + email,
                headers={"Referer": "http://" + referer},
                data={"name": "example"},
            )

            assert r.status_code == 302
            assert "next" in r.location

        assert (
            len(hosts)
            == Form.query.filter_by(host=confirmed_host).first().submissions.count()
        )

    finally:
        revert()


@pytest.mark.parametrize("unconfirmed_host", hosts)
def test_backwards_multiple_confirmed(client, msend, unconfirmed_host):
    """
    Same as previous, but now instead of having a single form confirmed, we
    have all but one confirmed. Submissions should go through the form which they
    specify directly, and fallback to the first in the priority when that is not
    confirmed.
    """

    prepare()
    try:
        for host in hosts:
            f = Form(email=email, confirmed=(host != unconfirmed_host), host=host)
            DB.session.add(f)
            DB.session.commit()

        for referer in hosts:
            r = client.post(
                "/" + email,
                headers={"Referer": "http://" + referer},
                data={"name": "example"},
            )

            assert r.status_code == 302
            assert "next" in r.location

        first = None
        for host in hosts:
            form = Form.query.filter_by(host=host).first()

            if host == unconfirmed_host:
                assert form.submissions.count() == 0
            else:
                if not first:
                    first = form
                    continue

                assert form.submissions.count() == 1
        assert first.submissions.count() == 2

    finally:
        revert()


def test_backwards_none_confirmed(client, msend):
    """
    This time no form is confirmed.
    """

    prepare()
    try:
        for host in hosts:
            f = Form(email=email, confirmed=False, host=host)
            DB.session.add(f)
            DB.session.commit()

        for referer in hosts:
            r = client.post(
                "/" + email,
                headers={"Referer": "http://" + referer},
                data={"name": "example"},
            )

            assert r.status_code == 200
            assert b"confirm" in r.get_data()
            assert Form.get_with(email=email, host=referer).host == hosts[0]

        assert Form.query.count() == len(hosts)
        assert Form.query.filter_by(confirmed=True).count() == 0
        assert Submission.query.count() == 0

    finally:
        revert()


@pytest.mark.parametrize("referrers", [hosts, reversed(hosts)])
def test_new_multiple(client, msend, referrers):
    """
    Here we test the flow of a new form being created, first with one host,
    then with the others.
    Only one form should be created, in the non-www/non-slash form.
    The order shouldn't matter.
    """

    prepare()
    try:
        for referrer in referrers:
            client.post(
                "/" + email,
                headers={"Referer": "http://" + referrer},
                data={"name": "example"},
            )

            assert 1 == Form.query.count()
            assert 1 == msend.call_count

        form = Form.query.first()
        assert form.host == hosts[0]
        form.confirmed = True
        DB.session.add(form)
        DB.session.commit()

        for i, referrer in enumerate(referrers):
            r = client.post(
                "/" + email,
                headers={"Referer": "http://" + referrer},
                data={"name": "example"},
            )

            assert 1 == Form.query.count()
            assert r.status_code == 302
            assert "next" in r.location

            # 1 for email confirmation, 1 to account for 0-based loop indexing
            assert 1 + 1 + i == msend.call_count

            # the first submission is not stored
            assert 1 + i == Form.query.first().submissions.count()

    finally:
        revert()


def test_a_confusing_case(client, msend):
    """
    Final boss.
    """

    prepare()
    try:
        _, uf = create_user_and_form(client)
        DB.session.add(Form(email=uf.email, confirmed=False, host="example.com"))
        DB.session.add(Form(email=uf.email, confirmed=True, host="example.com/contact"))
        DB.session.add(Form(email=uf.email, confirmed=True, host="www.example.com/"))
        DB.session.commit()

        assert Form.query.count() == 4

        form = Form.get_with(email=uf.email, host="example.com/")
        assert form
        assert form.confirmed
        assert form.host == "www.example.com/"

        form2 = Form.get_with(email=uf.email, host="www.example.com")
        assert form2
        assert form2.confirmed
        assert form.host == "www.example.com/"

        contact = form.get_with(email=uf.email, host="www.example.com/contact/")
        assert contact
        assert contact.host == "example.com/contact"

        assert form.id != contact.id
        assert form.id == form2.id

        r = client.post(
            "/" + uf.email,
            headers={"Referer": "http://example.com/"},
            data={"name": "example"},
        )
        assert r.status_code == 302
        assert "next" in r.location

        r = client.post(
            "/" + uf.email,
            headers={"Referer": "www.example.com"},
            data={"name": "example"},
        )
        assert r.status_code == 302
        assert "next" in r.location

        assert msend.call_count == 2
        assert Form.query.count() == 4
        form3 = Form.get_with(email=uf.email, host="example.com")
        assert 2 == form.submissions.count()
        assert form3.id == form2.id == form.id

    finally:
        revert()


def test_email_normalization(client, msend):
    match = [
        "myemail@example.com",
        "myemail+formspree@example.com",
        "myemail+otherstuff@example.com",
        "myemail+@example.com",
    ]
    dontmatch = ["myemaill@example.com", "myemai@example.com", "myemail@other.com"]

    # create forms
    for email in match + dontmatch:
        client.post(
            "/" + email, data={"foo": "bar"}, headers={"Referer": "example.com"}
        )

    for form in Form.query:
        form.confirmed = True
        DB.session.add(form)
    DB.session.commit()

    # register user
    client.post(
        "/register", data={"email": "myemail@example.com", "password": "banana"}
    )
    email = Email.query.first()
    email.verified = True
    DB.session.add(email)
    DB.session.commit()

    # user should have access to the forms that match his email ignoring the +... suffix
    user = User.query.filter_by(email="myemail@example.com").first()
    allforms = user.forms.all()

    for email in match:
        form = Form.query.filter_by(email=email).first()
        assert form in allforms
    for email in dontmatch:
        form = Form.query.filter_by(email=email).first()
        assert form not in allforms
