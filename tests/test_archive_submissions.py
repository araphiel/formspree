from formspree import settings
from formspree.app_globals import DB
from formspree.forms.models import Form, Submission

from .helpers import create_and_activate_form


def test_automatically_created_forms(
    client, host="somewhere.com", email="alice@example.com"
):

    form = create_and_activate_form(
        client, host="somewhere.com", email="alice@example.com"
    )

    # add four filler submissions
    DB.session.add(Submission(form.id))
    DB.session.add(Submission(form.id))
    DB.session.add(Submission(form.id))
    DB.session.commit()

    # submit again
    client.post(
        "/alice@example.com",
        headers={"referer": "http://somewhere.com"},
        data={
            "_replyto": "joh@ann.es",
            "_next": "http://google.com",
            "name": "johannes",
            "message": "yahoo!",
        },
    )

    form = Form.query.first()
    assert form.submissions.count() == 4

    # check archived values
    submissions = form.submissions.all()

    assert 4 == len(submissions)
    assert "message" in submissions[0].data
    assert "_next" not in submissions[0].data

    # check if submissions over the limit are correctly deleted
    assert settings.ARCHIVED_SUBMISSIONS_LIMIT == 4

    client.post(
        "/alice@example.com",
        headers={"referer": "http://somewhere.com"},
        data={"which-submission-is-this": "the fifth!"},
    )

    form = Form.query.first()
    assert 4 == form.submissions.count()
    newest = form.submissions.first()  # first should be the newest
    assert newest.data["which-submission-is-this"] == "the fifth!"

    client.post(
        "/alice@example.com",
        headers={"referer": "http://somewhere.com"},
        data={"which-submission-is-this": "the sixth!"},
    )
    client.post(
        "/alice@example.com",
        headers={"referer": "http://somewhere.com"},
        data={"which-submission-is-this": "the seventh!"},
    )

    form = Form.query.first()
    assert 4 == form.submissions.count()
    submissions = form.submissions.all()
    assert submissions[0].data["which-submission-is-this"] == "the seventh!"
    assert submissions[3].data["message"] == "yahoo!"

    #
    # try another form (to ensure that a form is not deleting wrong submissions)
    client.post(
        "/sokratis@example.com",
        headers={"referer": "http://here.com"},
        data={"name": "send me the confirmation!"},
    )
    secondform = Form.get_with(host="here.com", email="sokratis@example.com")
    assert secondform is not None

    # this form wasn't confirmed, so it still has no submissions
    assert secondform.submissions.count() == 0

    # confirm
    secondform.confirmed = True
    DB.session.add(form)
    DB.session.commit()

    # submit more times and test
    client.post(
        "/sokratis@example.com",
        headers={"referer": "http://here.com"},
        data={"name": "leibniz"},
    )

    secondform = Form.query.filter_by(
        host="here.com", email="sokratis@example.com"
    ).first()
    assert 1 == secondform.submissions.count()
    assert secondform.submissions.first().data["name"] == "leibniz"

    client.post(
        "/sokratis@example.com",
        headers={"referer": "http://here.com"},
        data={"name": "schelling"},
    )

    secondform = Form.query.filter_by(
        host="here.com", email="sokratis@example.com"
    ).first()
    assert 2 == secondform.submissions.count()
    newest, last = secondform.submissions.all()
    assert newest.data["name"] == "schelling"
    assert last.data["name"] == "leibniz"

    client.post(
        "/sokratis@example.com",
        headers={"referer": "http://here.com"},
        data={"name": "husserl"},
    )
    client.post(
        "/sokratis@example.com",
        headers={"referer": "http://here.com"},
        data={"name": "barban"},
    )
    client.post(
        "/sokratis@example.com",
        headers={"referer": "http://here.com"},
        data={"name": "gliffet"},
    )

    secondform = Form.query.filter_by(
        host="here.com", email="sokratis@example.com"
    ).first()
    assert 4 == secondform.submissions.count()
    last = secondform.submissions.order_by(Submission.id.desc()).first()
    assert last.data["name"] == "gliffet"

    # now check the previous form again
    form = Form.query.first()
    submissions = form.submissions.all()
    assert submissions[0].data["which-submission-is-this"] == "the seventh!"
    assert submissions[3].data["message"] == "yahoo!"


def test_grandfather_limit_and_decrease(client, msend):
    settings.GRANDFATHER_MONTHLY_LIMIT = 2
    settings.MONTHLY_SUBMISSIONS_LIMIT = 1
    settings.FORM_LIMIT_DECREASE_ACTIVATION_SEQUENCE = 1
    # the form limit should be 2 for the first form and 1 for the second

    # submit the forms
    client.post(
        "/grandfathered@example.com",
        headers={"referer": "http://somewhere.com"},
        data={"name": "john"},
    )
    form_grandfathered = Form.get_with(
        host="somewhere.com", email="grandfathered@example.com"
    )

    client.post(
        "/new@example.com",
        headers={"referer": "http://somewhere.com"},
        data={"name": "john"},
    )
    form_new = Form.get_with(host="somewhere.com", email="new@example.com")

    # confirm formS
    form_grandfathered.confirmed = True
    DB.session.add(form_grandfathered)
    form_new.confirmed = True
    DB.session.add(form_new)
    DB.session.commit()

    # submit each form 3 times
    msend.reset_mock()
    for i in range(3):
        client.post(
            "/grandfathered@example.com",
            headers={"referer": "http://somewhere.com"},
            data={"_replyto": "johann@gmail.com", "name": "johann", "value": "v%s" % i},
        )

    assert len(msend.call_args_list) == 4
    assert "grandfathered@example.com" == msend.call_args_list[-4][1]["to"]
    assert "90%" in msend.call_args_list[-4][1]["text"]
    assert "grandfathered@example.com" == msend.call_args_list[-3][1]["to"]
    assert "v0" in msend.call_args_list[-3][1]["text"]
    assert "grandfathered@example.com" == msend.call_args_list[-2][1]["to"]
    assert "v1" in msend.call_args_list[-2][1]["text"]
    assert "grandfathered@example.com" == msend.call_args_list[-1][1]["to"]
    assert "limit" in msend.call_args_list[-1][1]["text"]

    msend.reset_mock()
    for i in range(3):
        client.post(
            "/new@example.com",
            headers={"referer": "http://somewhere.com"},
            data={"_replyto": "johann@gmail.com", "name": "johann", "value": "v%s" % i},
        )

    assert len(msend.call_args_list) == 3
    assert "new@example.com" == msend.call_args_list[-3][1]["to"]
    assert "v0" in msend.call_args_list[-3][1]["text"]
    assert "new@example.com" == msend.call_args_list[-2][1]["to"]
    assert "limit" in msend.call_args_list[-2][1]["text"]
    assert "new@example.com" == msend.call_args_list[-1][1]["to"]
    assert "limit" in msend.call_args_list[-1][1]["text"]
