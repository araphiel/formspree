import time
import asyncio
import pytest

import pyppeteer
from pyppeteer import launch
from pyppeteer.errors import *

from formspree import settings
from formspree.users.models import User, Plan

pyppeteer.DEBUG = True


def debug_page(page):
    page.on("console", lambda msg: print(msg.text))

    @page.on("request")
    async def on_request(r):
        print("req: {} {}".format(r.method, r.url))

    @page.on("requestfailed")
    async def on_requestfailed(r):
        print("failed: {} {}".format(r.method, r.url))

    @page.on("response")
    async def on_response(w):
        if w.url.startswith(settings.SERVICE_URL):
            print("resp: {} {}".format(w.url, w.status))
            if not w.ok:
                try:
                    print(await w.text())
                except:
                    print(w.headers)


@pytest.mark.filterwarnings("ignore::DeprecationWarning")
@pytest.mark.asyncio
async def test_plans(page):
    await page.goto(settings.SERVICE_URL + "/plans", {"waitUntil": "networkidle2"})
    await page.waitForSelector(".product-button", {"timeout": 10000})

    buttons = await page.JJ(".product-button")
    assert 3 == len(buttons)

    assert await (await buttons[0].getProperty("disabled")).jsonValue()
    assert not await (await buttons[1].getProperty("disabled")).jsonValue()
    assert not await (await buttons[2].getProperty("disabled")).jsonValue()


@pytest.mark.filterwarnings("ignore::DeprecationWarning")
@pytest.mark.asyncio
async def test_buy_gold_unregistered(page, msend):
    debug_page(page)

    await page.goto(settings.SERVICE_URL + "/plans", {"waitUntil": "networkidle2"})
    await page.waitForSelector(".product-button", {"timeout": 10000})

    buttons = await page.JJ(".product-button")
    await buttons[1].click()
    await page.waitForSelector(".modal-overlay.open", {"timeout": 500})

    title = await page.J(".modal .title h4")
    assert "Account Details" in await (await title.getProperty("innerText")).jsonValue()
    form = await page.J(".modal form")
    inputs = await form.JJ("input")
    assert 3 == len(inputs)
    button = await form.J("button")

    [email, pass1, pass2] = inputs

    # should fail with no password confirmation
    await email.type("example@example.com")
    await pass1.type("password")
    await button.click()
    assert "Account Details" in await page.evaluate(
        "document.querySelector('.modal .title h4').innerText", force_expr=True
    )

    # should fail with wrong password
    await pass2.type("passw")
    await button.click()
    assert "Account Details" in await page.evaluate(
        "document.querySelector('.modal .title h4').innerText"
    )

    # should succeed with correct password
    await pass2.type("ord")  # just continue typing
    await button.click()
    assert "Billing Address" in await page.evaluate(
        "document.querySelector('.modal .title h4').innerText"
    )

    # now the address form
    title = await page.J(".modal .title h4")
    assert "Billing Address" in await (await title.getProperty("innerText")).jsonValue()
    form = await page.J(".modal form")
    inputs = await form.JJ("input")
    assert 4 == len(inputs)

    name, address, zipcode, country = inputs

    await name.type("Bob Julian")
    await address.type("Rua das Palmeiras, 532")
    await zipcode.type("12345")
    await page.keyboard.press("Enter")  # just pressing enter should work too
    assert "Gold" in await page.evaluate(
        "document.querySelector('.modal .title h4').innerText"
    )

    # yearly is preselected
    form = await page.J(".modal form")
    yearly = await form.J('input[value="' + Plan.gold_yearly + '"]')
    assert await (await yearly.getProperty("checked")).jsonValue()

    # select monthly
    monthly = await form.J('input[value="' + Plan.gold + '"]')
    await monthly.click()
    await monthly.click()  # click it twice, just to make sure

    # type in card
    card = {"number": "4242424242424242", "month": "04", "year": "29", "cvc": "123"}

    cardfield = await form.J(".StripeElement--empty")
    await cardfield.click()
    time.sleep(0.2)

    await page.keyboard.type(card["number"], {"delay": 30})
    await page.keyboard.type(card["month"], {"delay": 30})
    await page.keyboard.type(card["year"], {"delay": 30})
    await page.keyboard.type(card["cvc"], {"delay": 30})
    await page.keyboard.press("Enter")

    button = await form.J("button")
    assert "loading" in await (await button.getProperty("className")).jsonValue()

    await page.waitForNavigation({"timeout": 10000})
    assert "/forms" == await page.evaluate("location.pathname", force_expr=True)

    # user was created
    user = User.query.filter_by(email="example@example.com").first()
    assert user is not None
    assert user.plan == Plan.gold


@pytest.mark.filterwarnings("ignore::DeprecationWarning")
@pytest.mark.asyncio
async def test_buy_platinum_registered(page, msend):
    debug_page(page)

    User.register("example@example.com", "password")
    await page.goto(settings.SERVICE_URL + "/login")

    inputs = await page.JJ("input")
    await inputs[0].type("example@example.com")
    await inputs[1].type("password")
    await page.keyboard.press("Enter")
    await page.waitForNavigation({"timeout": 7000, "waitUntil": "networkidle2"})

    # navigate to account dashboard and then to plans
    await page.waitForSelector("#account-menu-item a")
    await (await page.J("#account-menu-item a")).click()
    await page.waitForNavigation({"timeout": 1000, "waitUntil": "networkidle2"})
    upgrade_now = await page.J('[href="/plans"]')
    assert (
        "upgrade now"
        == (await (await upgrade_now.getProperty("innerText")).jsonValue()).lower()
    )
    await upgrade_now.click()
    await page.waitForNavigation({"timeout": 1000, "waitUntil": "networkidle2"})

    buttons = await page.JJ(".product-button")
    await buttons[2].click()
    await page.waitForSelector(".modal-overlay.open", {"timeout": 500})

    # goes directly to the address form
    title = await page.J(".modal .title h4")
    assert "Billing Address" in await (await title.getProperty("innerText")).jsonValue()
    form = await page.J(".modal form")
    inputs = await form.JJ("input")
    assert 4 == len(inputs)

    name, address, zipcode, country = inputs

    await name.type("Bob Julian")
    await address.type("Rua das Palmeiras, 532")
    await zipcode.type("12345")
    await page.keyboard.press("Enter")  # just pressing enter should work too
    assert "Platinum" in await page.evaluate(
        "document.querySelector('.modal .title h4').innerText"
    )

    # yearly is preselected
    form = await page.J(".modal form")
    yearly = await form.J('input[value="' + Plan.platinum_yearly + '"]')
    assert await (await yearly.getProperty("checked")).jsonValue()

    # type in card
    card = {"number": "4242424242424242", "month": "04", "year": "29", "cvc": "123"}

    cardfield = await form.J(".StripeElement--empty")
    await cardfield.click()
    time.sleep(0.2)

    await page.keyboard.type(card["number"], {"delay": 30})
    await page.keyboard.type(card["month"], {"delay": 30})
    await page.keyboard.type(card["year"], {"delay": 30})
    await page.keyboard.type(card["cvc"], {"delay": 30})
    await page.keyboard.press("Enter")

    # in this case there isn't a navigation, the plans page just updates in-place
    time.sleep(8)
    assert 1 == User.query.filter_by(email="example@example.com").count()
    user = User.query.filter_by(email="example@example.com").first()
    assert user.plan == Plan.platinum_yearly
