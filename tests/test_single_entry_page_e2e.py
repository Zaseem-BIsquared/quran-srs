import os, sys
from playwright.sync_api import Page, expect
from fasthtml.common import *

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

db = database("data/quran.db")
revisions = db.t.revisions


def test_url(page: Page) -> None:
    page.goto("http://localhost:5001/")
    page.get_by_role("textbox", name="page").click()
    page.get_by_role("textbox", name="page").type("56", delay=150)
    page.get_by_role("button", name="Single Entry").click()
    expect(page).to_have_url("http://localhost:5001/revision/add?page=56")


def test_default_radio_selection(page: Page) -> None:
    page.goto("http://localhost:5001/revision/add?page=56")
    expect(page.get_by_role("radio", name="✅ Good")).to_be_checked()


def test_form_submission(page: Page) -> None:
    date = "2025-04-08"
    page.goto("http://localhost:5001/revision/add?page=56")
    page.get_by_role("textbox", name="Revision Date").fill(date)
    page.get_by_role("radio", name="😄 Ok").check()
    page.get_by_role("button", name="Save").click()
    expect(page.get_by_role("heading", name="- S3 Aal-e-Imran")).to_contain_text(
        "57 - S3 Aal-e-Imran"
    )
    # Check if the revision was added to the database
    last_revision = revisions()[-1]
    assert last_revision["page"] == 56
    assert last_revision["revision_date"] == date
    assert last_revision["rating"] == 0


def test_cancel_button(page: Page) -> None:
    page.goto("http://localhost:5001/revision/add?page=56")
    page.get_by_role("button", name="Cancel").click()
    expect(page).to_have_url("http://localhost:5001/")


def test_different_date_to_flow_to_next_page(page: Page) -> None:
    page.goto("http://localhost:5001/revision/add?page=56")
    page.get_by_role("textbox", name="Revision Date").fill("2025-04-08")
    page.get_by_role("button", name="Save").click()
    expect(page.get_by_role("textbox", name="Revision Date")).to_have_value(
        "2025-04-08", timeout=1000
    )
