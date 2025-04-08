import os, sys, pytest, re
from datetime import datetime, timedelta
from starlette.testclient import TestClient

# In order to import the app from the main module, we need to add the parent directory to the system path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from main import app


client = TestClient(app)
current_date = datetime.now().strftime("%Y-%m-%d")


# Test cases for the UI
def test_title():
    t = client.get("/revision/add?page=56").text
    assert "<title>Quran SRS</title>" in t


def test_heading():
    t = client.get("/revision/add?page=56").text
    assert "56 - S3 Aal-e-Imran Page 5" in t


def test_page_input():
    t = client.get("/revision/add?page=56").text
    assert re.search(r'<input.*?name="page".*?value="56"', t)


def test_date_input():
    t = client.get("/revision/add?page=56").text
    assert re.search(
        r'<input.*?name="revision_date".*?value="{}"'.format(current_date), t
    )


def test_default_radio_selection():
    t = client.get("/revision/add?page=56").text
    assert re.search(r'value="1".*?checked', t)


# Test cases for different page values
def test_integer_value():
    t = client.get("/revision/add?page=56").status_code
    assert t == 200


def test_decimal_value():
    t = client.get("/revision/add?page=56.20").status_code
    assert t == 200


def test_string_value():
    with pytest.raises(ValueError):
        client.get("/revision/add?page=abc")


def test_string_with_number_value():
    with pytest.raises(ValueError):
        client.get("/revision/add?page=105a")


def test_empty_value():
    with pytest.raises(ValueError):
        client.get("/revision/add?page=")


def test_missing_page():
    assert client.get("/revision/add").is_client_error


def test_page_out_of_range():
    url = client.get("/revision/add?page=605").url.__str__()
    assert url.endswith("/")


# def test_create_page():
#     # Simulate a POST request to create a new page
#     response = client.post(
#         "/revision/add",
#         headers={"Content-Type": "application/x-www-form-urlencoded"},
#         data={
#             "id": "",
#             "user_id": "1",
#             "page": "56",
#             "revision_date": current_date,
#             "rating": 1,
#         },
#     )
#     assert "57 - S3 Aal-e-Imran" in response.text


# def test_different_date_to_flow_to_next_page():
#     next_day = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
#     response = client.post(
#         "/revision/add",
#         headers={"Content-Type": "application/x-www-form-urlencoded"},
#         data={
#             "id": "",
#             "user_id": "1",
#             "page": "56",
#             "revision_date": next_day,
#             "rating": 1,
#         },
#     )
#     assert re.search(
#         r'<input.*?name="revision_date".*?value="{}"'.format(next_day), response.text
#     )
