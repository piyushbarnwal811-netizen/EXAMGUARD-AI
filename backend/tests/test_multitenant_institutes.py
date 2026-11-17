import pytest
from fastapi.testclient import TestClient


def test_master_admin_login(client: TestClient):
    """Verifies that the Super Admin can log in with new email credentials and receives super_admin claims."""
    # Test 1: login with username field
    res = client.post("/api/auth/admin-login", json={"username": "piyushbarnwal811@gmail.com", "password": "piyush@123"})
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["role"] == "admin"
    assert data["is_super_admin"] is True
    assert data["institute_name"] in (None, "Master Administration")
    assert "access_token" in data

    token = data["access_token"]
    profile_res = client.get("/api/admin/current-profile", headers={"Authorization": f"Bearer {token}"})
    assert profile_res.status_code == 200
    p = profile_res.json()
    assert p["is_super_admin"] is True
    assert p["username"] == "piyushbarnwal811@gmail.com"

    # Test 2: login with email field instead of username
    res_email = client.post("/api/auth/admin-login", json={"email": "piyushbarnwal811@gmail.com", "password": "piyush@123"})
    assert res_email.status_code == 200
    assert res_email.json()["is_super_admin"] is True


def test_seed_institute_login(client: TestClient):
    """Verifies that the default seeded coaching (Target Topper Classes) can log in with their ID & password."""
    res = client.post("/api/auth/admin-login", json={"username": "targettopper", "password": "topper123"})
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["role"] == "coaching_admin"
    assert data["is_super_admin"] is False
    assert data["institute_name"] == "Target Topper Classes"
    assert "access_token" in data

    token = data["access_token"]
    profile_res = client.get("/api/admin/current-profile", headers={"Authorization": f"Bearer {token}"})
    assert profile_res.status_code == 200
    p = profile_res.json()
    assert p["is_super_admin"] is False
    assert p["institute_name"] == "Target Topper Classes"


def test_institute_login_invalid_password(client: TestClient):
    """Verifies that entering the wrong password for an institute account is rejected."""
    res = client.post("/api/auth/admin-login", json={"username": "targettopper", "password": "wrongpassword"})
    assert res.status_code == 401


def test_rbac_institute_cannot_access_super_admin_endpoints(client: TestClient):
    """Verifies that a coaching admin cannot access super admin endpoints like /admin/institutes."""
    # Login as Target Topper
    res = client.post("/api/auth/admin-login", json={"username": "targettopper", "password": "topper123"})
    token = res.json()["access_token"]

    # Try listing institutes
    list_res = client.get("/api/admin/institutes", headers={"Authorization": f"Bearer {token}"})
    assert list_res.status_code == 403

    # Try creating institute
    create_res = client.post("/api/admin/institutes", json={"name": "Hacked", "username": "hack", "password": "123"}, headers={"Authorization": f"Bearer {token}"})
    assert create_res.status_code == 403


def test_super_admin_institute_crud_lifecycle(client: TestClient):
    """
    Complete lifecycle test:
    1. Super admin lists coachings.
    2. Super admin creates new coaching 'Apex Academy' with ID 'apex101' and password 'apexPass!'.
    3. Apex Academy logs in successfully with their ID & password.
    4. Super admin resets password for Apex Academy to 'newApexPass999'.
    5. Old password is rejected; new password works.
    6. Super admin toggles active status to Inactive.
    7. Inactive coaching is blocked from logging in.
    8. Super admin re-activates and coaching can log in again.
    9. Super admin deletes coaching.
    """
    # 1. Super admin login
    res = client.post("/api/auth/admin-login", json={"username": "piyushbarnwal811@gmail.com", "password": "piyush@123"})
    super_token = res.json()["access_token"]
    headers = {"Authorization": f"Bearer {super_token}"}

    # List institutes
    res_list = client.get("/api/admin/institutes", headers=headers)
    assert res_list.status_code == 200
    institutes = res_list.json()
    assert any(inst["username"] == "targettopper" for inst in institutes)

    # 2. Create Apex Academy
    create_payload = {
        "name": "Apex Academy",
        "username": "apex101",
        "password": "apexPass!",
        "contact_person": "Ramesh Kumar",
        "phone": "9876543210",
        "email": "ramesh@apex.com",
    }
    create_res = client.post("/api/admin/institutes", json=create_payload, headers=headers)
    assert create_res.status_code == 201, create_res.text
    new_inst = create_res.json()
    assert new_inst["name"] == "Apex Academy"
    assert new_inst["username"] == "apex101"
    inst_id = new_inst["id"]

    # 3. Apex Academy logs in
    login_res = client.post("/api/auth/admin-login", json={"username": "apex101", "password": "apexPass!"})
    assert login_res.status_code == 200
    assert login_res.json()["institute_name"] == "Apex Academy"

    # 4. Super admin resets password
    reset_res = client.post(
        f"/api/admin/institutes/{inst_id}/reset-password",
        json={"new_password": "newApexPass999"},
        headers=headers,
    )
    assert reset_res.status_code == 200

    # 5. Old password rejected, new password accepted
    old_res = client.post("/api/auth/admin-login", json={"username": "apex101", "password": "apexPass!"})
    assert old_res.status_code == 401

    new_res = client.post("/api/auth/admin-login", json={"username": "apex101", "password": "newApexPass999"})
    assert new_res.status_code == 200

    # 6. Toggle to Inactive
    toggle_res = client.patch(f"/api/admin/institutes/{inst_id}/toggle", headers=headers)
    assert toggle_res.status_code == 200
    assert toggle_res.json()["is_active"] is False

    # 7. Inactive coaching blocked
    inactive_login = client.post("/api/auth/admin-login", json={"username": "apex101", "password": "newApexPass999"})
    assert inactive_login.status_code == 403
    assert "suspended" in inactive_login.text.lower() or "inactive" in inactive_login.text.lower()

    # 8. Re-activate
    toggle_res2 = client.patch(f"/api/admin/institutes/{inst_id}/toggle", headers=headers)
    assert toggle_res2.status_code == 200
    assert toggle_res2.json()["is_active"] is True

    reactivated_login = client.post("/api/auth/admin-login", json={"username": "apex101", "password": "newApexPass999"})
    assert reactivated_login.status_code == 200

    # 9. Delete
    delete_res = client.delete(f"/api/admin/institutes/{inst_id}", headers=headers)
    assert delete_res.status_code == 200

    deleted_login = client.post("/api/auth/admin-login", json={"username": "apex101", "password": "newApexPass999"})
    assert deleted_login.status_code == 401


def test_submissions_isolation_between_institutes(client: TestClient):
    """
    Verifies that a coaching admin only sees their own coaching's candidate submissions,
    while the master super admin sees all.
    """
    # Create two candidates: one for Target Topper Classes, one for Brilliant College
    c1 = client.post(
        "/api/auth/coaching-candidate-onboard",
        json={
            "name": "Topper Student",
            "roll_no": "TOP-101",
            "coaching_name": "Target Topper Classes",
            "exam_id": "test-exam-1",
        },
    )
    assert c1.status_code == 200

    c2 = client.post(
        "/api/auth/coaching-candidate-onboard",
        json={
            "name": "Brilliant Student",
            "roll_no": "BRIL-202",
            "coaching_name": "Brilliant College",
            "exam_id": "test-exam-2",
        },
    )
    assert c2.status_code == 200

    # Login as Target Topper admin
    topper_admin = client.post("/api/auth/admin-login", json={"username": "targettopper", "password": "topper123"})
    topper_token = topper_admin.json()["access_token"]

    # Target Topper admin fetches submissions
    topper_subs = client.get(
        "/api/exam/admin/coaching-submissions",
        headers={"Authorization": f"Bearer {topper_token}"},
    )
    assert topper_subs.status_code == 200
    data = topper_subs.json()
    assert all(item["coaching_name"].lower() == "target topper classes" for item in data)
    assert any(item["name"] == "Topper Student" for item in data)
    assert not any(item["name"] == "Brilliant Student" for item in data)

    # Master admin fetches submissions
    super_admin = client.post("/api/auth/admin-login", json={"username": "piyushbarnwal811@gmail.com", "password": "piyush@123"})
    super_token = super_admin.json()["access_token"]

    all_subs = client.get(
        "/api/exam/admin/coaching-submissions",
        headers={"Authorization": f"Bearer {super_token}"},
    )
    assert all_subs.status_code == 200
    all_data = all_subs.json()
    names = [item["name"] for item in all_data]
    assert "Topper Student" in names
    assert "Brilliant Student" in names
