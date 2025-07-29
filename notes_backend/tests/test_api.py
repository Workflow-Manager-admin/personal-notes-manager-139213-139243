def test_health_check(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json()["message"] == "Healthy"

# -------- AUTH TESTS --------
def test_register_and_login(client, user_data):
    # Register new user
    r = client.post("/auth/register", json=user_data)
    assert r.status_code == 200
    resp = r.json()
    assert resp["username"] == user_data["username"]
    assert resp["email"] == user_data["email"]
    assert "id" in resp

    # Duplicate username/email
    r2 = client.post("/auth/register", json=user_data)
    assert r2.status_code == 409

    # Login with correct credentials
    r3 = client.post("/auth/login", data={
        "username": user_data["username"], "password": user_data["password"]
    })
    assert r3.status_code == 200
    assert "access_token" in r3.json()

    # Login with incorrect password
    r4 = client.post("/auth/login", data={
        "username": user_data["username"], "password": "wrongpw"
    })
    assert r4.status_code == 401

    # Login with nonexistent user
    r5 = client.post("/auth/login", data={
        "username": "somebody", "password": "pw"
    })
    assert r5.status_code == 401

def test_profile_requires_auth(client, user_data):
    # No token
    r = client.get("/auth/me")
    assert r.status_code == 401

    # Valid token
    reg = client.post("/auth/register", json=user_data)
    assert reg.status_code in [200,409]
    login = client.post("/auth/login", data={
        "username": user_data["username"], "password": user_data["password"]
    })
    token = login.json()["access_token"]
    r2 = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r2.status_code == 200
    assert r2.json()["username"] == user_data["username"]

# ------- NOTES CRUD --------
def test_notes_crud(client, auth_header):
    # Empty notes list
    r = client.get("/notes/", headers=auth_header)
    assert r.status_code == 200
    assert r.json() == []

    # Create a note (valid)
    note_data = {"title": "First", "content": "Hello note"}
    r2 = client.post("/notes/", json=note_data, headers=auth_header)
    assert r2.status_code == 201
    note = r2.json()
    assert note["title"] == "First"
    assert note["content"] == "Hello note"
    note_id = note["id"]

    # List notes (should include the new one)
    notes = client.get("/notes/", headers=auth_header).json()
    assert len(notes) == 1
    assert notes[0]["title"] == "First"

    # Get note by ID (success)
    r3 = client.get(f"/notes/{note_id}", headers=auth_header)
    assert r3.status_code == 200
    assert r3.json()["id"] == note_id

    # Update note (partial)
    update = {"content": "Updated!", "title": "Renamed"}
    r4 = client.put(f"/notes/{note_id}", json=update, headers=auth_header)
    assert r4.status_code == 200
    assert r4.json()["content"] == "Updated!"
    assert r4.json()["title"] == "Renamed"

    # Delete note
    r5 = client.delete(f"/notes/{note_id}", headers=auth_header)
    assert r5.status_code == 204

    # Ensure note gone
    r6 = client.get(f"/notes/{note_id}", headers=auth_header)
    assert r6.status_code == 404

def test_notes_auth_required(client):
    # All notes endpoints must require auth
    r = client.get("/notes/")
    assert r.status_code == 401
    r2 = client.post("/notes/", json={"title": "x"})
    assert r2.status_code == 401
    r3 = client.get("/notes/123")
    assert r3.status_code == 401

def test_notes_multi_user(client, auth_header, second_auth_header):
    # User 1 adds note
    note_data = {"title": "U1 note", "content": "Owned"}
    r = client.post("/notes/", json=note_data, headers=auth_header)
    note_id = r.json()["id"]

    # User 2 cannot see or delete
    notes2 = client.get("/notes/", headers=second_auth_header).json()
    assert all(n["id"] != note_id for n in notes2)

    r2 = client.get(f"/notes/{note_id}", headers=second_auth_header)
    assert r2.status_code == 404

    r3 = client.put(f"/notes/{note_id}", json={"title": "hax"}, headers=second_auth_header)
    assert r3.status_code == 404

    r4 = client.delete(f"/notes/{note_id}", headers=second_auth_header)
    assert r4.status_code == 404

def test_notes_search(client, auth_header):
    # Insert several notes
    for i in range(3):
        client.post("/notes/", json={"title": f"todo-{i}", "content": "mytask"}, headers=auth_header)
    client.post("/notes/", json={"title": "Meeting", "content": "work"}, headers=auth_header)
    # Search by title
    r = client.get("/notes/?q=todo", headers=auth_header)
    assert r.status_code == 200
    found = [note["title"] for note in r.json()]
    assert all("todo" in t for t in found)
    # Search by content
    r2 = client.get("/notes/?q=work", headers=auth_header)
    assert len(r2.json()) == 1
    assert r2.json()[0]["title"] == "Meeting"

def test_create_note_invalid(client, auth_header):
    # Missing title
    r = client.post("/notes/", json={"content": "x"}, headers=auth_header)
    assert r.status_code == 422
    # Title too long
    r2 = client.post("/notes/", json={"title": "x"*200}, headers=auth_header)
    assert r2.status_code == 422

def test_update_note_not_found(client, auth_header):
    r = client.put("/notes/999", json={"title": "nope"}, headers=auth_header)
    assert r.status_code == 404

def test_delete_note_not_found(client, auth_header):
    r = client.delete("/notes/999", headers=auth_header)
    assert r.status_code == 404

def test_duplicate_registration(client, user_data):
    # Register first time should succeed
    r = client.post("/auth/register", json=user_data)
    assert r.status_code == 200 or r.status_code == 409
    # Register duplicate should fail
    r2 = client.post("/auth/register", json=user_data)
    assert r2.status_code == 409
