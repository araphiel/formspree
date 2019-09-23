import json
from functools import partial

from formspree import settings
from formspree.app_globals import DB
from formspree.forms.models import Form
from formspree.users.models import User, Email, Plan

from .helpers import create_user_and_form

http_headers = {"Referer": "testwebsite.com"}


def test_index_page(client):
    r = client.get("/")
    assert 200 == r.status_code


def test_thanks_page(client):
    r = client.get("/thanks")
    assert r.status_code == 200

    # test XSS
    r = client.get("/thanks?next=javascript:alert(document.domain)")
    assert r.status_code == 400

    r = client.get("/thanks?next=https%3A%2F%2Fformspree.io")
    assert r.status_code == 200


def test_submit_form(client, msend):
    client.post(
        "/alice@testwebsite.com",
        headers=http_headers,
        data={"name": "alice", "_subject": "my-nice-subject"},
    )
    assert 1 == Form.query.count()
    f = Form.query.first()
    f.confirmed = True

    client.post(
        "/alice@testwebsite.com",
        headers=http_headers,
        data={"name": "alice", "_subject": "my-nice-subject", "_format": "plain"},
    )
    assert "my-nice-subject" in msend.call_args[1]["subject"]
    assert "_subject" not in msend.call_args[1]["text"]
    assert "_format" not in msend.call_args[1]["text"]
    assert "plain" not in msend.call_args[1]["text"]


def test_fail_form_without_header(client, msend):
    msend.reset_mock()
    no_referer = http_headers.copy()
    del no_referer["Referer"]
    r = client.post("/bob@testwebsite.com", headers=no_referer, data={"name": "bob"})
    assert 200 != r.status_code
    assert not msend.called
    assert 0 == Form.query.count()


def test_fail_form_spoof_formspree(client, msend):
    msend.reset_mock()
    r = client.post(
        "/alice@testwebsite.com",
        headers={"Referer": settings.SERVICE_URL},
        data={"name": "alice", "_subject": "my-nice-subject"},
    )
    assert "Unable to submit form" in r.data.decode("utf-8")
    assert 200 != r.status_code
    assert not msend.called
    assert 0 == Form.query.count()


def test_fail_but_appears_to_have_succeeded_with_gotcha(client, msend):
    # manually confirm
    r = client.post(
        "/carlitos@testwebsite.com",
        headers={"Referer": "http://carlitos.net/"},
        data={"name": "carlitos"},
    )
    f = Form.query.first()
    f.confirm_sent = True
    f.confirmed = True
    DB.session.add(f)
    DB.session.commit()

    msend.reset_mock()

    r = client.post(
        "/carlitos@testwebsite.com",
        headers={"Referer": "http://carlitos.net/"},
        data={"name": "Real Stock", "_gotcha": "The best offers."},
    )
    assert not msend.called
    assert 302 == r.status_code
    assert 0 == Form.query.first().counter


def test_fail_with_invalid_reply_to(client, msend):
    # manually confirm
    r = client.post(
        "/carlitos@testwebsite.com",
        headers={"Referer": "http://carlitos.net/"},
        data={"name": "carlitos"},
    )
    f = Form.query.first()
    f.confirm_sent = True
    f.confirmed = True
    DB.session.add(f)
    DB.session.commit()

    # fail with an invalid '_replyto'
    msend.reset_mock()

    r = client.post(
        "/carlitos@testwebsite.com",
        headers={"Referer": "http://carlitos.net/"},
        data={"name": "Real Stock", "_replyto": "The best offers."},
    )
    assert not msend.called
    assert 400 == r.status_code
    assert 0 == Form.query.first().counter

    # fail with an invalid 'email'
    r = client.post(
        "/carlitos@testwebsite.com",
        headers={"Referer": "http://carlitos.net/"},
        data={"name": "Real Stock", "email": "The best offers."},
    )
    assert not msend.called
    assert 400 == r.status_code
    assert 0 == Form.query.first().counter


def test_fail_ajax_form(client, msend):
    msend.reset_mock()

    ajax_headers = http_headers.copy()
    ajax_headers["X_REQUESTED_WITH"] = "xmlhttprequest"
    r = client.post("/bob@example.com", headers=ajax_headers, data={"name": "bob"})
    assert not msend.called
    assert 200 != r.status_code


def test_activation_workflow(client, msend):
    r = client.post("/bob@testwebsite.com", headers=http_headers, data={"name": "bob"})
    f = Form.query.first()
    assert f.email == "bob@testwebsite.com"
    assert f.host == "testwebsite.com"
    assert f.confirm_sent == True
    assert f.counter == 0  # the counter shows zero submissions
    assert f.owner_id == None
    assert f.get_monthly_counter() == 0  # monthly submissions also 0

    # form has another submission, number of forms in the table should increase?
    r = client.post("/bob@testwebsite.com", headers=http_headers, data={"name": "bob"})
    number_of_forms = Form.query.count()
    assert number_of_forms == 1  # still only one form

    # assert form data is still the same
    f = Form.query.first()
    assert f.email == "bob@testwebsite.com"
    assert f.host == "testwebsite.com"
    assert f.confirm_sent == True
    assert f.counter == 0  # still zero submissions
    assert f.owner_id == None

    # test clicking of activation link
    r = client.get("/confirm/%s" % (f.hash,))

    f = Form.query.first()
    assert f.confirmed == True
    assert f.counter == 1  # counter has increased
    assert f.get_monthly_counter() == 1  # monthly submissions also

    # a third submission should now increase the counter
    r = client.post("/bob@testwebsite.com", headers=http_headers, data={"name": "bob"})
    number_of_forms = Form.query.count()
    assert number_of_forms == 1  # still only one form

    f = Form.query.first()
    assert f.email == "bob@testwebsite.com"
    assert f.host == "testwebsite.com"
    assert f.confirm_sent == True
    assert f.owner_id == None
    assert f.counter == 2  # counter has increased
    assert f.get_monthly_counter() == 2  # monthly submissions also


def test_monthly_limits(client, msend):
    # monthly limit is set to 2 during tests
    assert settings.MONTHLY_SUBMISSIONS_LIMIT == 2

    # manually verify luke@example.com
    r = client.post(
        "/luke@testwebsite.com", headers=http_headers, data={"name": "luke"}
    )
    f = Form.query.first()
    f.confirm_sent = True
    f.confirmed = True
    DB.session.add(f)
    DB.session.commit()

    # first submission
    r = client.post(
        "/luke@testwebsite.com", headers=http_headers, data={"name": "peter"}
    )
    assert r.status_code == 302
    assert "peter" in msend.call_args[1]["text"]

    # second submission
    r = client.post("/luke@testwebsite.com", headers=http_headers, data={"name": "ana"})
    assert r.status_code == 302
    assert "ana" in msend.call_args[1]["text"]

    # third submission, now we're over the limit
    r = client.post(
        "/luke@testwebsite.com", headers=http_headers, data={"name": "maria"}
    )
    assert r.status_code == 302  # the response to the user is the same
    # being the form over the limits or not

    # the mocked sendgrid should never receive this last form
    assert "maria" not in msend.call_args[1]["text"]
    assert "past the limit" in msend.call_args[1]["text"]

    # all the other variables are ok:
    assert 1 == Form.query.count()
    f = Form.query.first()
    assert f.counter == 3
    assert f.get_monthly_counter() == 3  # the counters mark 4

    # the user pays and becomes gold
    r = client.post(
        "/register", data={"email": "luke@testwebsite.com", "password": "banana"}
    )
    user = User.query.filter_by(email="luke@testwebsite.com").first()
    user.plan = Plan.gold
    user.emails[0].verified = True
    DB.session.add(user)
    DB.session.commit()

    # the user should receive form posts again
    r = client.post(
        "/luke@testwebsite.com", headers=http_headers, data={"name": "noah"}
    )
    assert r.status_code == 302
    assert "noah" in msend.call_args[1]["text"]


def test_overlimit_notifications(client, msend):
    # monthly limit is set to 2 during tests
    assert settings.MONTHLY_SUBMISSIONS_LIMIT == 2

    # we'll send two overlimit notifications and no more
    assert settings.OVERLIMIT_NOTIFICATION_QUANTITY == 2

    # manually verify luke@example.com
    r = client.post(
        "/luke@testwebsite.com", headers=http_headers, data={"name": "luke"}
    )
    f = Form.query.first()
    f.confirm_sent = True
    f.confirmed = True
    DB.session.add(f)
    DB.session.commit()

    # submit the form multiple times
    msend.reset_mock()
    for i in range(0, 20):
        r = client.post(
            "/luke@testwebsite.com", headers=http_headers, data={"name": "matthew"}
        )

    # but we'll only send 5 emails (1 warning, 2 normal, 2 overlimit)
    assert len(msend.call_args_list) == 5
    assert "90%" in msend.call_args_list[-5][1]["text"]
    assert "matthew" in msend.call_args_list[-4][1]["text"]
    assert "matthew" in msend.call_args_list[-3][1]["text"]
    assert "limit" in msend.call_args_list[-2][1]["text"]
    assert "limit" in msend.call_args_list[-1][1]["text"]


def test_first_submission_is_stored(client, msend):
    r = client.post(
        "/what@firstsubmissed.com",
        headers=http_headers,
        data={"missed": "this was important"},
    )
    f = Form.query.first()
    assert f.email == "what@firstsubmissed.com"
    assert f.confirm_sent == True
    assert f.counter == 0  # the counter shows zero submissions
    assert f.get_monthly_counter() == 0  # monthly submissions also 0

    # got a confirmation email
    assert "one step away" in msend.call_args[1]["text"]

    # clicking of activation link
    client.get("/confirm/%s" % (f.hash,))

    f = Form.query.first()
    assert f.confirmed == True
    assert f.counter == 1  # counter has increased
    assert f.get_monthly_counter() == 1  # monthly submissions also

    # got the first (missed) submission
    assert "this was important" in msend.call_args[1]["text"]


def test_recaptcha_is_rendered(client, msend):
    def revert(testing, seq):
        settings.TESTING = testing
        settings.FORM_AJAX_DISABLE_ACTIVATION_SEQUENCE = seq

    revert = partial(
        revert,
        testing=settings.TESTING,
        seq=settings.FORM_AJAX_DISABLE_ACTIVATION_SEQUENCE,
    )
    settings.TESTING = False

    try:
        # create the form
        f = Form("example@example.com", confirmed=True, host="example.com")
        DB.session.add(f)
        DB.session.commit()

        # normal submission
        r = client.post(
            "/example@example.com",
            headers={"Referer": "example.com"},
            data={"hello": "world"},
        )
        assert r.status_code == 401  # recaptcha
        assert b"google.com/recaptcha" in r.data
        assert not msend.called

        # ajax submission
        r = client.post(
            "/example@example.com",
            headers={"Referer": "example.com", "Content-Type": "application/json"},
            data=json.dumps({"hello": "world"}),
        )
        assert r.status_code == 403  # should get a json error
        assert "error" in json.loads(r.data.decode("utf-8"))
        assert not msend.called

        # a form that is before ajax disable sequence shouldn't show recaptcha
        # when the submission is ajax
        settings.FORM_AJAX_DISABLE_ACTIVATION_SEQUENCE = 1

        # normal submission
        r = client.post(
            "/example@example.com",
            headers={"Referer": "example.com"},
            data={"hello": "world"},
        )
        assert r.status_code == 401  # recaptcha
        assert b"google.com/recaptcha" in r.data
        assert not msend.called

        # ajax submission
        r = client.post(
            "/example@example.com",
            headers={"Referer": "example.com", "Content-Type": "application/json"},
            data=json.dumps({"hello": "world"}),
        )
        assert r.status_code == 200
        assert b"google.com/recaptcha" not in r.data
        assert msend.called

    finally:
        revert()


def test_recaptcha_is_not_rendered_when_disabled(client, msend):
    def revert(testing):
        settings.TESTING = testing

    revert = partial(revert, testing=settings.TESTING)
    settings.TESTING = False

    try:
        # a gold form
        _, form = create_user_and_form(client)

        # normal submission
        r = client.post(
            "/" + form.hashid,
            headers={"Referer": "example.com"},
            data={"hello": "world"},
        )
        assert r.status_code == 401 # recaptcha
        assert b"google.com/recaptcha" in r.data
        assert not msend.called

        # ajax submission
        r = client.post(
            "/" + form.hashid,
            headers={"Referer": "example.com", "Content-Type": "application/json"},
            data=json.dumps({"hello": "world"}),
        )
        assert r.status_code == 403  # should get a json error
        assert "error" in json.loads(r.data.decode("utf-8"))
        assert not msend.called

        # disable recaptcha
        form.captcha_disabled = True
        DB.session.add(form)
        DB.session.commit()

        # normal submission
        r = client.post(
            "/" + form.hashid,
            headers={"Referer": "example.com"},
            data={"hello": "world"},
        )
        assert b"google.com/recaptcha" not in r.data
        assert r.status_code == 302 # no recaptcha
        assert "thanks" in r.headers["Location"]
        assert msend.called

        # ajax submission
        msend.reset_mock()
        r = client.post(
            "/" + form.hashid,
            headers={"Referer": "example.com", "Content-Type": "application/json"},
            data=json.dumps({"hello": "world"}),
        )
        assert r.status_code == 200
        assert b"google.com/recaptcha" not in r.data
        assert msend.called

    finally:
        revert()
