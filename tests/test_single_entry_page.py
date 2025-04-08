import os, sys
from datetime import datetime
from starlette.testclient import TestClient
from fasthtml.common import database


# In order to import the app from the main module, we need to add the parent directory to the system path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from main import app

DUMMY_PAGE = 1000000  # This is a dummy page number for testing purposes

db = database("data/quran.db")
revisions = db.t.revisions
initial_revisions_count = len(revisions())

current_date = datetime.now().strftime("%Y-%m-%d")

client = TestClient(app)


# This route is responsible for handling navigation to the single entry page
def test_entry_route():
    response = client.post(
        "/revision/entry",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "type": "single",
            "page": "56",
        },
    )
    assert response.status_code == 200


def test_decimal_value():
    response = client.post(
        "/revision/entry",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "type": "single",
            "page": "56.20",
        },
    )
    assert response.status_code == 200


def test_create_page():
    response = client.post(
        "/revision/add",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "id": "",
            "user_id": "1",
            "page": DUMMY_PAGE,
            "revision_date": current_date,
            "rating": 1,
        },
    )
    assert response.status_code == 200
    assert (initial_revisions_count + 1) == len(
        revisions()
    )  # Check if the page was added


def test_update_page():
    page_data = revisions(where=f"page = {DUMMY_PAGE}")[0]
    page_data["rating"] = -1  # Update the rating

    response = client.post(
        "/revision/edit",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data=page_data,
    )
    assert response.status_code == 200
    assert revisions[page_data["id"]]["rating"] == -1  # Check if the rating was updated
    assert (initial_revisions_count + 1) == len(
        revisions()
    )  # Check if the page is still present


def test_delete_page():
    id = revisions(where=f"page = {DUMMY_PAGE}")[0]["id"]

    response = client.delete(f"/revision/delete/{id}")
    assert response.status_code == 200
    assert initial_revisions_count == len(revisions())  # Check if the page was deleted
