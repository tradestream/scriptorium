"""Tests for library management endpoints."""

import pytest


@pytest.mark.asyncio
async def test_list_libraries_empty(client, auth_headers):
    resp = await client.get("/api/v1/libraries", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_create_library(client, auth_headers, tmp_path):
    lib_path = str(tmp_path / "books")
    resp = await client.post(
        "/api/v1/libraries",
        json={"name": "My Books", "path": lib_path},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "My Books"
    assert data["path"] == lib_path
    assert "id" in data


@pytest.mark.asyncio
async def test_create_library_requires_admin(client):
    # Register a non-admin user
    await client.post(
        "/api/v1/auth/register",
        json={"username": "firstforlibtest", "email": "first_lib@test.local", "password": "testpass123"},
    )
    await client.post(
        "/api/v1/auth/register",
        json={"username": "nonadmin", "email": "nonadmin_lib@test.local", "password": "testpass123"},
    )
    login = await client.post(
        "/api/v1/auth/login",
        json={"username": "nonadmin", "password": "testpass123"},
    )
    token = login.json()["access_token"]

    resp = await client.post(
        "/api/v1/libraries",
        json={"name": "Forbidden", "path": "/tmp/forbidden"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_get_library(client, auth_headers, tmp_path):
    create_resp = await client.post(
        "/api/v1/libraries",
        json={"name": "GetTest", "path": str(tmp_path)},
        headers=auth_headers,
    )
    lib_id = create_resp.json()["id"]

    resp = await client.get(f"/api/v1/libraries/{lib_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == lib_id


@pytest.mark.asyncio
async def test_delete_library(client, auth_headers, tmp_path):
    create_resp = await client.post(
        "/api/v1/libraries",
        json={"name": "ToDelete", "path": str(tmp_path)},
        headers=auth_headers,
    )
    lib_id = create_resp.json()["id"]

    resp = await client.delete(f"/api/v1/libraries/{lib_id}", headers=auth_headers)
    assert resp.status_code == 204

    resp = await client.get(f"/api/v1/libraries/{lib_id}", headers=auth_headers)
    assert resp.status_code == 404
