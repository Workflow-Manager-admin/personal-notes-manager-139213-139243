# Pytest Test Plan for FastAPI Notes Backend

## Fixtures
- Temporary test database (SQLite in-memory or temp file)
- FastAPI TestClient
- User registration & JWT helper
- Setup/teardown for clean state per test

## Auth Tests
- Register new user (success, username/email taken, invalid, short pw, etc)
- Login (success, wrong user, wrong password, use email or username)
- Get profile (/auth/me) (success, unauthorized)

## Notes CRUD Tests
- No notes initially
- Create note (success, bad data), unauthorized
- List notes (empty, one, many, search)
- Get note (correct owner, not existing, not owner)
- Update note (success, not owner, 404)
- Delete note (success, not owner, 404)
- Notes only visible to correct user

## Error Cases
- 404s (note not found)
- 401s (missing/bad token)
- 409s (duplicate user/email)

## Helper Functions
- User registration, login JWT setup
- Auth headers helper
