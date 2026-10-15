

from uuid import uuid4

import pytest

from fastapi.testclient import TestClient

from sqlalchemy import create_engine

from sqlalchemy.orm import sessionmaker



from main import app

from app.database import Base, DATABASE_URL, get_db





# --------------------------------------------------

# TEST DATABASE SETUP

# --------------------------------------------------



TEST_DATABASE_URL = (

    DATABASE_URL.rsplit("/", 1)[0] + "/job_tracker_test"

)



test_engine = create_engine(TEST_DATABASE_URL)



TestingSessionLocal = sessionmaker(

    autocommit=False,

    autoflush=False,

    bind=test_engine,

)





def override_get_db():

    db = TestingSessionLocal()

    try:

        yield db

    finally:

        db.close()





app.dependency_overrides[get_db] = override_get_db



client = TestClient(app)





@pytest.fixture(autouse=True)

def reset_test_database():

    Base.metadata.drop_all(bind=test_engine)

    Base.metadata.create_all(bind=test_engine)





# --------------------------------------------------

# HELPER FUNCTIONS

# --------------------------------------------------



def create_user_and_get_headers():

    email = f"pytest.{uuid4().hex}@example.com"

    password = "TestPass123!"



    response = client.post(

        "/register",

        json={

            "name": "Test User",

            "email": email,

            "password": password,

        },

    )

    assert response.status_code == 201



    response = client.post(

        "/auth/login",

        json={"email": email, "password": password},

    )

    assert response.status_code == 200



    token = response.json()["access_token"]



    return {"Authorization": f"Bearer {token}"}





def create_application(

    headers,

    company="ABC Technologies",

    title="Python Developer",

    location=None,

    source=None,

    status_value="APPLIED",

    salary_min=None,

    salary_max=None,

):

    data = {

        "company_name": company,

        "job_title": title,

        "status": status_value,

    }



    if location is not None:

        data["location"] = location



    if source is not None:

        data["source"] = source



    if salary_min is not None:

        data["salary_min"] = salary_min



    if salary_max is not None:

        data["salary_max"] = salary_max



    return client.post(

        "/applications",

        headers=headers,

        json=data,

    )





# --------------------------------------------------

# HOME AND AUTHENTICATION TESTS

# --------------------------------------------------



def test_home():

    response = client.get("/")

    assert response.status_code == 200

    assert "message" in response.json()





def test_register_user():

    email = f"pytest.register.{uuid4().hex}@example.com"



    response = client.post(

        "/register",

        json={

            "name": "Test User",

            "email": email,

            "password": "TestPass123!",

        },

    )



    assert response.status_code == 201

    assert response.json()["name"] == "Test User"

    assert response.json()["email"] == email

    assert "password" not in response.json()





def test_duplicate_registration():

    email = f"pytest.duplicate.{uuid4().hex}@example.com"



    user_data = {

        "name": "Test User",

        "email": email,

        "password": "TestPass123!",

    }



    assert client.post("/register", json=user_data).status_code == 201

    assert client.post("/register", json=user_data).status_code == 409





def test_register_user_with_invalid_email():

    response = client.post(

        "/register",

        json={

            "name": "Test User",

            "email": "not-an-email",

            "password": "TestPass123!",

        },

    )



    assert response.status_code == 422





def test_register_user_with_short_password():

    response = client.post(

        "/register",

        json={

            "name": "Test User",

            "email": f"pytest.short.{uuid4().hex}@example.com",

            "password": "abc",

        },

    )



    assert response.status_code == 422





def test_register_user_with_short_name():

    response = client.post(

        "/register",

        json={

            "name": "A",

            "email": f"pytest.name.{uuid4().hex}@example.com",

            "password": "TestPass123!",

        },

    )



    assert response.status_code == 422





def test_login_user():

    headers = create_user_and_get_headers()



    # The helper has already registered and logged in the user.

    assert "Authorization" in headers

    assert headers["Authorization"].startswith("Bearer ")





def test_login_wrong_password():

    email = f"pytest.wrongpass.{uuid4().hex}@example.com"



    client.post(

        "/register",

        json={

            "name": "Test User",

            "email": email,

            "password": "TestPass123!",

        },

    )



    response = client.post(

        "/auth/login",

        json={

            "email": email,

            "password": "WrongPass123!",

        },

    )



    assert response.status_code == 401





def test_login_unregistered_user():

    response = client.post(

        "/auth/login",

        json={

            "email": "nobody@example.com",

            "password": "TestPass123!",

        },

    )



    assert response.status_code == 401





def test_applications_require_login():

    response = client.get("/applications")

    assert response.status_code == 401





def test_applications_reject_invalid_token():

    response = client.get(

        "/applications",

        headers={"Authorization": "Bearer invalid-token"},

    )



    assert response.status_code == 401





# --------------------------------------------------

# CREATE AND READ APPLICATION TESTS

# --------------------------------------------------



def test_create_application():

    headers = create_user_and_get_headers()



    response = create_application(headers)



    assert response.status_code == 201

    assert response.json()["company_name"] == "ABC Technologies"

    assert response.json()["job_title"] == "Python Developer"

    assert response.json()["status"] == "APPLIED"





def test_applications_with_login():

    headers = create_user_and_get_headers()



    response = client.get("/applications", headers=headers)



    assert response.status_code == 200

    assert isinstance(response.json()["data"], list)





def test_get_application_by_id():

    headers = create_user_and_get_headers()



    create_response = create_application(headers)

    assert create_response.status_code == 201



    application_id = create_response.json()["id"]



    response = client.get(

        f"/applications/{application_id}",

        headers=headers,

    )



    assert response.status_code == 200

    assert response.json()["id"] == application_id

    assert response.json()["company_name"] == "ABC Technologies"





def test_get_nonexistent_application():

    headers = create_user_and_get_headers()



    response = client.get(

        "/applications/999999",

        headers=headers,

    )



    assert response.status_code == 404





def test_create_application_with_invalid_status():

    headers = create_user_and_get_headers()



    response = client.post(

        "/applications",

        headers=headers,

        json={

            "company_name": "ABC Technologies",

            "job_title": "Python Developer",

            "status": "PENDING",

        },

    )



    assert response.status_code == 422





# --------------------------------------------------

# USER DATA ISOLATION TESTS

# --------------------------------------------------



def test_users_only_see_their_own_applications():

    headers_a = create_user_and_get_headers()

    headers_b = create_user_and_get_headers()



    response = create_application(

        headers_a,

        company="Private Company A",

    )

    assert response.status_code == 201



    response = client.get("/applications", headers=headers_b)



    assert response.status_code == 200

    assert all(

        item["company_name"] != "Private Company A"

        for item in response.json()["data"]

    )





def test_users_cannot_read_each_others_applications():

    headers_a = create_user_and_get_headers()

    headers_b = create_user_and_get_headers()



    create_response = create_application(

        headers_a,

        company="Owner Private Company",

    )

    application_id = create_response.json()["id"]



    response = client.get(

        f"/applications/{application_id}",

        headers=headers_b,

    )



    assert response.status_code == 404





def test_users_cannot_modify_each_others_applications():

    headers_a = create_user_and_get_headers()

    headers_b = create_user_and_get_headers()



    create_response = create_application(

        headers_a,

        company="Owner Private Company",

    )

    application_id = create_response.json()["id"]



    patch_response = client.patch(

        f"/applications/{application_id}/status",

        params={"new_status": "INTERVIEW"},

        headers=headers_b,

    )

    assert patch_response.status_code == 404



    put_response = client.put(

        f"/applications/{application_id}",

        headers=headers_b,

        json={

            "company_name": "Changed Company",

            "job_title": "Manager",

            "status": "APPLIED",

        },

    )

    assert put_response.status_code == 404



    delete_response = client.delete(

        f"/applications/{application_id}",

        headers=headers_b,

    )

    assert delete_response.status_code == 404





# --------------------------------------------------

# SEARCH AND FILTER TESTS

# --------------------------------------------------



def test_applications_search_by_company_name():

    headers = create_user_and_get_headers()



    create_application(headers, company="Google")

    create_application(headers, company="Microsoft")



    response = client.get(

        "/applications",

        headers=headers,

        params={"search": "Google"},

    )



    assert response.status_code == 200

    assert len(response.json()["data"]) == 1

    assert response.json()["data"][0]["company_name"] == "Google"





def test_applications_search_is_case_insensitive():

    headers = create_user_and_get_headers()

    create_application(headers, company="Google")



    response = client.get(

        "/applications",

        headers=headers,

        params={"search": "google"},

    )



    assert response.status_code == 200

    assert len(response.json()["data"]) == 1





def test_applications_search_by_job_title():

    headers = create_user_and_get_headers()



    create_application(

        headers,

        company="ABC Technologies",

        title="Python Developer",

    )

    create_application(

        headers,

        company="XYZ Solutions",

        title="Data Analyst",

    )



    response = client.get(

        "/applications",

        headers=headers,

        params={"search": "Python"},

    )



    assert response.status_code == 200

    assert len(response.json()["data"]) == 1

    assert response.json()["data"][0]["job_title"] == "Python Developer"





def test_applications_filter_by_status():

    headers = create_user_and_get_headers()



    create_application(

        headers,

        company="Company A",

        status_value="APPLIED",

    )

    create_application(

        headers,

        company="Company B",

        status_value="INTERVIEW",

    )



    response = client.get(

        "/applications",

        headers=headers,

        params={"status_filter": "INTERVIEW"},

    )



    assert response.status_code == 200

    assert len(response.json()["data"]) == 1

    assert response.json()["data"][0]["company_name"] == "Company B"





def test_applications_filter_by_location():

    headers = create_user_and_get_headers()



    create_application(headers, location="Hyderabad")

    create_application(

        headers,

        company="XYZ Solutions",

        location="Bangalore",

    )



    response = client.get(

        "/applications",

        headers=headers,

        params={"location": "Hyderabad"},

    )



    assert response.status_code == 200

    assert len(response.json()["data"]) == 1

    assert response.json()["data"][0]["location"] == "Hyderabad"





def test_applications_filter_by_location_case_insensitive():

    headers = create_user_and_get_headers()

    create_application(headers, location="Hyderabad")



    response = client.get(

        "/applications",

        headers=headers,

        params={"location": "hyderabad"},

    )



    assert response.status_code == 200

    assert len(response.json()["data"]) == 1





def test_applications_filter_by_location_partial_match():

    headers = create_user_and_get_headers()

    create_application(headers, location="Hyderabad, Telangana")



    response = client.get(

        "/applications",

        headers=headers,

        params={"location": "Hyderabad"},

    )



    assert response.status_code == 200

    assert len(response.json()["data"]) == 1





def test_applications_filter_by_status_and_location():

    headers = create_user_and_get_headers()



    create_application(

        headers,

        company="Company A",

        location="Hyderabad",

        status_value="APPLIED",

    )

    create_application(

        headers,

        company="Company B",

        location="Hyderabad",

        status_value="INTERVIEW",

    )

    create_application(

        headers,

        company="Company C",

        location="Bangalore",

        status_value="INTERVIEW",

    )



    response = client.get(

        "/applications",

        headers=headers,

        params={

            "status_filter": "INTERVIEW",

            "location": "Hyderabad",

        },

    )



    assert response.status_code == 200

    assert len(response.json()["data"]) == 1

    assert response.json()["data"][0]["company_name"] == "Company B"





# --------------------------------------------------

# SORTING AND PAGINATION TESTS

# --------------------------------------------------



def test_applications_sort_by_company_ascending():

    headers = create_user_and_get_headers()



    create_application(headers, company="Zebra Ltd")

    create_application(headers, company="Alpha Ltd")

    create_application(headers, company="Microsoft")



    response = client.get(

        "/applications",

        headers=headers,

        params={

            "sort_by": "company_name",

            "sort_order": "asc",

        },

    )



    assert response.status_code == 200



    companies = [

        item["company_name"] for item in response.json()["data"]

    ]



    assert companies == ["Alpha Ltd", "Microsoft", "Zebra Ltd"]





def test_applications_sort_by_company_descending():

    headers = create_user_and_get_headers()



    create_application(headers, company="Alpha Ltd")

    create_application(headers, company="Zebra Ltd")

    create_application(headers, company="Microsoft")



    response = client.get(

        "/applications",

        headers=headers,

        params={

            "sort_by": "company_name",

            "sort_order": "desc",

        },

    )



    assert response.status_code == 200



    companies = [

        item["company_name"] for item in response.json()["data"]

    ]



    assert companies == ["Zebra Ltd", "Microsoft", "Alpha Ltd"]





def test_applications_pagination():

    headers = create_user_and_get_headers()



    for company in ["Company A", "Company B", "Company C"]:

        create_application(headers, company=company)



    response = client.get(

        "/applications",

        headers=headers,

        params={"skip": 0, "limit": 2},

    )



    assert response.status_code == 200

    assert len(response.json()["data"]) == 2





def test_applications_pagination_second_page():

    headers = create_user_and_get_headers()



    for company in ["Company A", "Company B", "Company C"]:

        create_application(headers, company=company)



    first_page = client.get(

        "/applications",

        headers=headers,

        params={

            "skip": 0,

            "limit": 2,

            "sort_by": "company_name",

            "sort_order": "asc",

        },

    )



    second_page = client.get(

        "/applications",

        headers=headers,

        params={

            "skip": 2,

            "limit": 2,

            "sort_by": "company_name",

            "sort_order": "asc",

        },

    )



    assert len(first_page.json()["data"]) == 2

    assert len(second_page.json()["data"]) == 1



    first_ids = {item["id"] for item in first_page.json()["data"]}

    second_ids = {item["id"] for item in second_page.json()["data"]}



    assert first_ids.isdisjoint(second_ids)





def test_applications_reject_invalid_pagination():

    headers = create_user_and_get_headers()



    response = client.get(

        "/applications",

        headers=headers,

        params={"limit": 0},

    )



    assert response.status_code == 422





def test_applications_reject_invalid_sort_field():

    headers = create_user_and_get_headers()



    response = client.get(

        "/applications",

        headers=headers,

        params={"sort_by": "invalid_field"},

    )



    assert response.status_code == 422





# --------------------------------------------------

# SALARY VALIDATION TESTS

# --------------------------------------------------



def test_create_application_with_negative_salary():

    headers = create_user_and_get_headers()



    response = create_application(

        headers,

        salary_min=-5000,

        salary_max=900000,

    )



    assert response.status_code == 422





def test_create_application_when_min_salary_exceeds_max_salary():

    headers = create_user_and_get_headers()



    response = create_application(

        headers,

        salary_min=800000,

        salary_max=500000,

    )



    assert response.status_code == 422





def test_create_application_with_valid_salary_range():

    headers = create_user_and_get_headers()



    response = create_application(

        headers,

        salary_min=500000,

        salary_max=900000,

    )



    assert response.status_code == 201

    assert response.json()["salary_min"] == 500000

    assert response.json()["salary_max"] == 900000





# --------------------------------------------------

# UPDATE AND DELETE TESTS

# --------------------------------------------------



def test_update_application_status():

    headers = create_user_and_get_headers()



    create_response = create_application(

        headers,

        status_value="APPLIED",

    )

    application_id = create_response.json()["id"]



    response = client.patch(

        f"/applications/{application_id}/status",

        headers=headers,

        params={"new_status": "INTERVIEW"},

    )



    assert response.status_code == 200

    assert response.json()["status"] == "INTERVIEW"





def test_update_application_rejects_invalid_status():

    headers = create_user_and_get_headers()



    create_response = create_application(headers)

    application_id = create_response.json()["id"]



    response = client.patch(

        f"/applications/{application_id}/status",

        headers=headers,

        params={"new_status": "PENDING"},

    )



    assert response.status_code == 422





def test_edit_application():

    headers = create_user_and_get_headers()



    create_response = create_application(headers)

    application_id = create_response.json()["id"]



    response = client.put(

        f"/applications/{application_id}",

        headers=headers,

        json={

            "company_name": "XYZ Technologies",

            "job_title": "Backend Developer",

            "location": "Hyderabad",

            "status": "INTERVIEW",

        },

    )



    assert response.status_code == 200

    assert response.json()["company_name"] == "XYZ Technologies"

    assert response.json()["job_title"] == "Backend Developer"

    assert response.json()["location"] == "Hyderabad"

    assert response.json()["status"] == "INTERVIEW"





def test_edit_nonexistent_application():

    headers = create_user_and_get_headers()



    response = client.put(

        "/applications/999999",

        headers=headers,

        json={

            "company_name": "XYZ Technologies",

            "job_title": "Backend Developer",

            "status": "APPLIED",

        },

    )



    assert response.status_code == 404





def test_delete_application():

    headers = create_user_and_get_headers()



    create_response = create_application(headers)

    application_id = create_response.json()["id"]



    delete_response = client.delete(

        f"/applications/{application_id}",

        headers=headers,

    )



    assert delete_response.status_code == 200



    get_response = client.get(

        f"/applications/{application_id}",

        headers=headers,

    )



    assert get_response.status_code == 404





def test_delete_nonexistent_application():

    headers = create_user_and_get_headers()



    response = client.delete(

        "/applications/999999",

        headers=headers,

    )



    assert response.status_code == 404



def test_dashboard_counts_applications():

    headers = create_user_and_get_headers()



    create_application(headers, status_value="APPLIED")

    create_application(

        headers,

        company="Company B",

        status_value="INTERVIEW",

    )

    create_application(

        headers,

        company="Company C",

        status_value="APPLIED",

    )



    response = client.get("/dashboard", headers=headers)



    assert response.status_code == 200

    assert response.json()["total_applications"] == 3

    assert response.json()["status_counts"]["APPLIED"] == 2

    assert response.json()["status_counts"]["INTERVIEW"] == 1





def test_dashboard_only_counts_current_users_applications():

    headers_a = create_user_and_get_headers()

    headers_b = create_user_and_get_headers()



    create_application(headers_a, company="Company A")

    create_application(headers_a, company="Company B")

    create_application(headers_b, company="Company C")



    response = client.get("/dashboard", headers=headers_b)



    assert response.status_code == 200

    assert response.json()["total_applications"] == 1
