from playwright.sync_api import Page, expect
from datetime import datetime, timedelta

next_day = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")


def test_single_entry_navigation(page: Page) -> None:
    page.goto("http://localhost:5001/")
    page.get_by_role("textbox", name="page").click()
    page.get_by_role("textbox", name="page").type("56", delay=150)
    page.get_by_role("button", name="Single Entry").click()
    expect(page).to_have_url("http://localhost:5001/revision/add?page=56")


def test_default_radio_selection(page: Page) -> None:
    page.goto("http://localhost:5001/revision/add?page=56")
    expect(page.get_by_role("radio", name="✅ Good")).to_be_checked()


def test_form_submission(page: Page) -> None:
    page.goto("http://localhost:5001/revision/add?page=56")
    page.get_by_role("textbox", name="Revision Date").fill(next_day)
    page.get_by_role("radio", name="😄 Ok").check()
    page.get_by_role("button", name="Save").click()


def test_save_button_navigation(page: Page) -> None:
    page.goto("http://localhost:5001/revision/add?page=56")
    page.get_by_role("button", name="Save").click()
    expect(page).to_have_url("http://localhost:5001/revision/add?page=57")


def test_cancel_button_navigation(page: Page) -> None:
    page.goto("http://localhost:5001/revision/add?page=56")
    page.get_by_role("button", name="Cancel").click()
    expect(page).to_have_url("http://localhost:5001/")


def test_different_date_to_flow_to_next_page(page: Page) -> None:
    page.goto("http://localhost:5001/revision/add?page=56")
    page.get_by_role("textbox", name="Revision Date").fill(next_day)
    page.get_by_role("button", name="Save").click()
    expect(page.get_by_role("textbox", name="Revision Date")).to_have_value(
        next_day, timeout=1000
    )
