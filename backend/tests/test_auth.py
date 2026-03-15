"""Tests for authentication endpoints."""

import pytest


@pytest.mark.asyncio
async def test_register_first_user_becomes_admin(client):
    resp = await client.post(
        "/api/v1/auth/register",
        json={"username": "alice", "email": "alice@test.local", "password": "password123"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["username"] == "alice"
    assert data["is_admin"] is True  # first user is always admin


@pytest.mark.asyncio
async def test_register_second_user_not_admin(client):
    await client.post(
        "/api/v1/auth/register",
        json={"username": "first", "email": "first@test.local", "password": "password123"},
    )
    resp = await client.post(
        "/api/v1/auth/register",
        json={"username": "second", "email": "second@test.local", "password": "password123"},
    )
    assert resp.status_code == 201
    assert resp.json()["is_admin"] is False


@pytest.mark.asyncio
async def test_register_duplicate_username(client):
    await client.post(
        "/api/v1/auth/register",
        json={"username": "dup", "email": "dup@test.local", "password": "password123"},
    )
    resp = await client.post(
        "/api/v1/auth/register",
        json={"username": "dup", "email": "dup2@test.local", "password": "password123"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_login_success(client):
    await client.post(
        "/api/v1/auth/register",
        json={"username": "loginuser", "email": "login@test.local", "password": "pw123"},
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "loginuser", "password": "pw123"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    await client.post(
        "/api/v1/auth/register",
        json={"username": "wrongpw", "email": "wrongpw@test.local", "password": "correctpass"},
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "wrongpw", "password": "wrongpass"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_me(client, auth_headers):
    resp = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["username"] == "admin"


@pytest.mark.asyncio
async def test_get_me_unauthenticated(client):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_oidc_config_disabled(client):
    resp = await client.get("/api/v1/auth/oidc/config")
    assert resp.status_code == 200
    assert resp.json()["enabled"] is False
