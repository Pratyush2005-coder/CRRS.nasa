"""Comprehensive tests for Farm Profile Management CRUD API with authorization."""

import uuid
from typing import Any, Dict
from fastapi.testclient import TestClient


def get_sample_farm_payload() -> Dict[str, Any]:
    """Return a valid farm creation payload."""
    return {
        "name": "Ludhiana Research Station",
        "farmer_name": "Dr. Harpreet Singh",
        "latitude": 30.9010,
        "longitude": 75.8573,
        "elevation_m": 244.0,
        "region": "Punjab",
        "country": "India",
        "total_area_hectares": 25.5,
        "soil_type": "sandy_loam",
        "soil_ph": 7.2,
        "organic_matter_pct": 1.8,
        "primary_irrigation": "canal",
        "current_crop": "Wheat",
        "current_crop_planting_date": "2023-11-10",
        "previous_crops": [
            {
                "crop_name": "Rice (Basmati)",
                "harvest_year": 2023,
                "season": "Kharif",
                "yield_tonnes_per_hectare": 4.2,
            },
            {
                "crop_name": "Mustard",
                "harvest_year": 2022,
                "season": "Rabi",
                "yield_tonnes_per_hectare": 1.9,
            },
        ],
    }


# --- Unauthenticated access tests ---

def test_create_farm_unauthenticated_returns_401(client: TestClient):
    """POST /api/farms without auth returns 401."""
    payload = get_sample_farm_payload()
    response = client.post("/api/farms", json=payload)
    assert response.status_code == 401
    assert "not authenticated" in response.json()["detail"].lower()


def test_list_farms_unauthenticated_returns_401(client: TestClient):
    """GET /api/farms without auth returns 401."""
    response = client.get("/api/farms")
    assert response.status_code == 401


def test_get_farm_unauthenticated_returns_401(client: TestClient):
    """GET /api/farms/{id} without auth returns 401."""
    random_id = str(uuid.uuid4())
    response = client.get(f"/api/farms/{random_id}")
    assert response.status_code == 401


def test_update_farm_unauthenticated_returns_401(client: TestClient):
    """PUT/PATCH /api/farms/{id} without auth returns 401."""
    random_id = str(uuid.uuid4())
    response = client.put(f"/api/farms/{random_id}", json=get_sample_farm_payload())
    assert response.status_code == 401
    response = client.patch(f"/api/farms/{random_id}", json={"name": "New"})
    assert response.status_code == 401


def test_delete_farm_unauthenticated_returns_401(client: TestClient):
    """DELETE /api/farms/{id} without auth returns 401."""
    random_id = str(uuid.uuid4())
    response = client.delete(f"/api/farms/{random_id}")
    assert response.status_code == 401


# --- Authenticated user tests ---

def test_create_farm_success(auth_client: TestClient):
    """POST /api/farms with valid data and auth should return 201 and created farm with UUID."""
    payload = get_sample_farm_payload()
    response = auth_client.post("/api/farms", json=payload)
    assert response.status_code == 201

    data = response.json()
    assert "id" in data
    # Verify valid UUID string
    uuid_obj = uuid.UUID(data["id"])
    assert str(uuid_obj) == data["id"]

    assert data["name"] == payload["name"]
    assert data["farmer_name"] == payload["farmer_name"]
    assert data["latitude"] == payload["latitude"]
    assert data["longitude"] == payload["longitude"]
    assert data["soil_type"] == payload["soil_type"]
    assert data["primary_irrigation"] == payload["primary_irrigation"]
    assert len(data["previous_crops"]) == 2
    assert data["previous_crops"][0]["crop_name"] == "Rice (Basmati)"
    assert "created_at" in data
    assert "updated_at" in data
    # Farm should be owned by the authenticated user
    assert data.get("owner_id") == "test-user-123"


def test_create_farm_invalid_latitude_returns_422(auth_client: TestClient):
    """Latitude > 90 must fail validation."""
    payload = get_sample_farm_payload()
    payload["latitude"] = 95.0
    response = auth_client.post("/api/farms", json=payload)
    assert response.status_code == 422
    assert "latitude" in str(response.json()).lower()


def test_create_farm_invalid_longitude_returns_422(auth_client: TestClient):
    """Longitude < -180 must fail validation."""
    payload = get_sample_farm_payload()
    payload["longitude"] = -195.0
    response = auth_client.post("/api/farms", json=payload)
    assert response.status_code == 422
    assert "longitude" in str(response.json()).lower()


def test_create_farm_invalid_area_returns_422(auth_client: TestClient):
    """Area <= 0 must fail validation."""
    payload = get_sample_farm_payload()
    payload["total_area_hectares"] = -5.0
    response = auth_client.post("/api/farms", json=payload)
    assert response.status_code == 422


def test_create_farm_invalid_soil_type_returns_422(auth_client: TestClient):
    """Unrecognized soil_type enum must return 422."""
    payload = get_sample_farm_payload()
    payload["soil_type"] = "martian_dust"
    response = auth_client.post("/api/farms", json=payload)
    assert response.status_code == 422


def test_create_farm_missing_required_fields_returns_422(auth_client: TestClient):
    """Missing required name or coordinates returns 422."""
    response = auth_client.post("/api/farms", json={"soil_type": "clay"})
    assert response.status_code == 422


def test_get_farm_by_id_success(auth_client: TestClient, test_user):
    """GET /api/farms/{farm_id} should return existing farm owned by user."""
    created = auth_client.post("/api/farms", json=get_sample_farm_payload()).json()
    farm_id = created["id"]

    response = auth_client.get(f"/api/farms/{farm_id}")
    assert response.status_code == 200
    fetched = response.json()
    assert fetched["id"] == farm_id
    assert fetched["name"] == created["name"]
    assert fetched["owner_id"] == test_user.id


def test_get_farm_by_id_not_found(auth_client: TestClient):
    """GET /api/farms/{non_existent_id} should return 404."""
    random_id = str(uuid.uuid4())
    response = auth_client.get(f"/api/farms/{random_id}")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_get_farm_cross_user_returns_404(auth_client: TestClient, admin_client: TestClient):
    """User A cannot access User B's farm (admin creates farm, user tries to access)."""
    # Admin creates a farm
    created = admin_client.post("/api/farms", json=get_sample_farm_payload()).json()
    farm_id = created["id"]

    # User A tries to access Admin's farm
    response = auth_client.get(f"/api/farms/{farm_id}")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_list_farms_empty_and_populated(auth_client: TestClient):
    """GET /api/farms should list only user's farm profiles with count."""
    # Initially empty
    empty_resp = auth_client.get("/api/farms")
    assert empty_resp.status_code == 200
    assert empty_resp.json()["total"] == 0
    assert empty_resp.json()["items"] == []

    # Insert two farms
    p1 = get_sample_farm_payload()
    p1["name"] = "Farm Alpha"
    auth_client.post("/api/farms", json=p1)

    p2 = get_sample_farm_payload()
    p2["name"] = "Farm Beta"
    auth_client.post("/api/farms", json=p2)

    list_resp = auth_client.get("/api/farms")
    assert list_resp.status_code == 200
    data = list_resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2
    for item in data["items"]:
        assert item["owner_id"] == "test-user-123"


def test_list_farms_pagination(auth_client: TestClient):
    """Pagination query params (skip, limit) should be respected."""
    for i in range(5):
        p = get_sample_farm_payload()
        p["name"] = f"Plot {i+1}"
        auth_client.post("/api/farms", json=p)

    resp = auth_client.get("/api/farms", params={"skip": 2, "limit": 2})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 5
    assert len(data["items"]) == 2
    assert data["skip"] == 2
    assert data["limit"] == 2


def test_list_farms_search_filter(auth_client: TestClient):
    """Searching should match name, farmer_name, region, or country."""
    p1 = get_sample_farm_payload()
    p1["name"] = "Golden Wheat Estate"
    p1["region"] = "Sonipat"
    p1["soil_type"] = "clay"
    auth_client.post("/api/farms", json=p1)

    p2 = get_sample_farm_payload()
    p2["name"] = "Silver Valley"
    p2["region"] = "Bathinda"
    p2["soil_type"] = "sandy"
    auth_client.post("/api/farms", json=p2)

    # Search by region
    search_resp = auth_client.get("/api/farms", params={"search": "Sonipat"})
    assert search_resp.status_code == 200
    items = search_resp.json()["items"]
    assert len(items) == 1
    assert items[0]["name"] == "Golden Wheat Estate"

    # Filter by soil type
    soil_resp = auth_client.get("/api/farms", params={"soil_type": "sandy"})
    assert soil_resp.status_code == 200
    soil_items = soil_resp.json()["items"]
    assert len(soil_items) == 1
    assert soil_items[0]["name"] == "Silver Valley"


def test_put_farm_success(auth_client: TestClient):
    """PUT /api/farms/{id} should fully update farm attributes."""
    created = auth_client.post("/api/farms", json=get_sample_farm_payload()).json()
    farm_id = created["id"]

    updated_payload = get_sample_farm_payload()
    updated_payload["name"] = "Updated Station Name"
    updated_payload["total_area_hectares"] = 48.0
    updated_payload["soil_type"] = "clay"

    put_resp = auth_client.put(f"/api/farms/{farm_id}", json=updated_payload)
    assert put_resp.status_code == 200
    data = put_resp.json()
    assert data["id"] == farm_id
    assert data["name"] == "Updated Station Name"
    assert data["total_area_hectares"] == 48.0
    assert data["soil_type"] == "clay"
    assert data["owner_id"] == "test-user-123"


def test_put_farm_not_found(auth_client: TestClient):
    """PUT /api/farms/{non_existent_id} should return 404."""
    random_id = str(uuid.uuid4())
    resp = auth_client.put(f"/api/farms/{random_id}", json=get_sample_farm_payload())
    assert resp.status_code == 404


def test_put_farm_cross_user_returns_404(auth_client: TestClient, admin_client: TestClient):
    """User A cannot update User B's farm."""
    created = admin_client.post("/api/farms", json=get_sample_farm_payload()).json()
    farm_id = created["id"]

    updated_payload = get_sample_farm_payload()
    updated_payload["name"] = "Hacked Name"
    resp = auth_client.put(f"/api/farms/{farm_id}", json=updated_payload)
    assert resp.status_code == 404


def test_patch_farm_partial_update(auth_client: TestClient):
    """PATCH /api/farms/{id} should update only provided fields."""
    created = auth_client.post("/api/farms", json=get_sample_farm_payload()).json()
    farm_id = created["id"]

    patch_payload = {
        "name": "Partially Modified Farm",
        "soil_ph": 8.0,
    }
    patch_resp = auth_client.patch(f"/api/farms/{farm_id}", json=patch_payload)
    assert patch_resp.status_code == 200
    data = patch_resp.json()
    assert data["name"] == "Partially Modified Farm"
    assert data["soil_ph"] == 8.0
    # Unmodified fields should remain untouched
    assert data["latitude"] == created["latitude"]
    assert data["total_area_hectares"] == created["total_area_hectares"]
    assert data["soil_type"] == created["soil_type"]
    assert data["owner_id"] == "test-user-123"


def test_patch_farm_not_found(auth_client: TestClient):
    """PATCH /api/farms/{non_existent_id} should return 404."""
    random_id = str(uuid.uuid4())
    resp = auth_client.patch(f"/api/farms/{random_id}", json={"name": "New Name"})
    assert resp.status_code == 404


def test_patch_farm_cross_user_returns_404(auth_client: TestClient, admin_client: TestClient):
    """User A cannot patch User B's farm."""
    created = admin_client.post("/api/farms", json=get_sample_farm_payload()).json()
    farm_id = created["id"]

    resp = auth_client.patch(f"/api/farms/{farm_id}", json={"name": "Hacked Name"})
    assert resp.status_code == 404


def test_delete_farm_success(auth_client: TestClient):
    """DELETE /api/farms/{id} should return 204 and remove the resource."""
    created = auth_client.post("/api/farms", json=get_sample_farm_payload()).json()
    farm_id = created["id"]

    del_resp = auth_client.delete(f"/api/farms/{farm_id}")
    assert del_resp.status_code == 204

    # Subsequent GET should return 404
    get_resp = auth_client.get(f"/api/farms/{farm_id}")
    assert get_resp.status_code == 404


def test_delete_farm_not_found(auth_client: TestClient):
    """DELETE /api/farms/{non_existent_id} should return 404."""
    random_id = str(uuid.uuid4())
    resp = auth_client.delete(f"/api/farms/{random_id}")
    assert resp.status_code == 404


def test_delete_farm_cross_user_returns_404(auth_client: TestClient, admin_client: TestClient):
    """User A cannot delete User B's farm."""
    created = admin_client.post("/api/farms", json=get_sample_farm_payload()).json()
    farm_id = created["id"]

    resp = auth_client.delete(f"/api/farms/{farm_id}")
    assert resp.status_code == 404


def test_user_cannot_set_owner_id_in_payload(auth_client: TestClient):
    """User cannot manipulate ownership through request payload."""
    payload = get_sample_farm_payload()
    payload["owner_id"] = "some-other-user-id"  # This field shouldn't be in FarmCreate schema
    # The FarmCreate schema doesn't have owner_id, so this will be ignored or cause validation error
    response = auth_client.post("/api/farms", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["owner_id"] == "test-user-123"  # Should be set to authenticated user


# --- Admin tests ---

def test_admin_can_access_all_farms(admin_client: TestClient, auth_client: TestClient):
    """Admin can list and access all farms including other users' farms."""
    # User creates a farm
    created = auth_client.post("/api/farms", json=get_sample_farm_payload()).json()
    farm_id = created["id"]

    # Admin can list all farms
    list_resp = admin_client.get("/api/farms")
    assert list_resp.status_code == 200
    data = list_resp.json()
    assert data["total"] >= 1
    # Find the user's farm in admin's list
    user_farm = next((f for f in data["items"] if f["id"] == farm_id), None)
    assert user_farm is not None

    # Admin can get the user's farm
    get_resp = admin_client.get(f"/api/farms/{farm_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == farm_id

    # Admin can update the user's farm
    put_resp = admin_client.put(f"/api/farms/{farm_id}", json=get_sample_farm_payload())
    assert put_resp.status_code == 200

    # Admin can delete the user's farm
    del_resp = admin_client.delete(f"/api/farms/{farm_id}")
    assert del_resp.status_code == 204


def test_admin_can_access_legacy_farms(admin_client: TestClient):
    """Admin can access legacy farms with NULL owner_id."""
    # Create a legacy farm directly in DB (simulating pre-migration data)
    from app.models.farm import Farm
    from app.core.database import get_db
    from app.main import app
    from sqlalchemy.orm import Session
    from tests.conftest import TestingSessionLocal

    # Insert a farm with NULL owner_id directly in the test database
    db = TestingSessionLocal()
    try:
        legacy_farm = Farm(
            id="legacy-farm-001",
            name="Legacy Farm Alpha",
            latitude=30.0,
            longitude=75.0,
            total_area_hectares=10.0,
            soil_type="loam",
            primary_irrigation="rainfed",
            owner_id=None,  # Legacy farm - no owner
        )
        db.add(legacy_farm)
        db.commit()
        db.refresh(legacy_farm)
        legacy_farm_id = legacy_farm.id
    finally:
        db.close()

    # Admin can list all farms including legacy
    list_resp = admin_client.get("/api/farms")
    assert list_resp.status_code == 200
    data = list_resp.json()
    legacy_in_list = next((f for f in data["items"] if f["id"] == legacy_farm_id), None)
    assert legacy_in_list is not None
    assert legacy_in_list["owner_id"] is None

    # Admin can get the legacy farm
    get_resp = admin_client.get(f"/api/farms/{legacy_farm_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == legacy_farm_id
    assert get_resp.json()["owner_id"] is None

    # Admin can update the legacy farm
    put_resp = admin_client.put(f"/api/farms/{legacy_farm_id}", json={
        "name": "Updated Legacy Farm",
        "latitude": 30.0,
        "longitude": 75.0,
        "total_area_hectares": 10.0,
        "soil_type": "loam",
        "primary_irrigation": "rainfed",
    })
    assert put_resp.status_code == 200
    assert put_resp.json()["name"] == "Updated Legacy Farm"

    # Admin can delete the legacy farm
    del_resp = admin_client.delete(f"/api/farms/{legacy_farm_id}")
    assert del_resp.status_code == 204


def test_user_cannot_access_legacy_farm_get(auth_client: TestClient):
    """Normal user receives 404 when GETting a legacy farm (NULL owner_id)."""
    from app.models.farm import Farm
    from tests.conftest import TestingSessionLocal

    db = TestingSessionLocal()
    try:
        legacy_farm = Farm(
            id="legacy-farm-002",
            name="Legacy Farm Beta",
            latitude=30.0,
            longitude=75.0,
            total_area_hectares=10.0,
            soil_type="loam",
            primary_irrigation="rainfed",
            owner_id=None,
        )
        db.add(legacy_farm)
        db.commit()
        db.refresh(legacy_farm)
        legacy_farm_id = legacy_farm.id
    finally:
        db.close()

    response = auth_client.get(f"/api/farms/{legacy_farm_id}")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_user_cannot_access_legacy_farm_put(auth_client: TestClient):
    """Normal user receives 404 when PUTting a legacy farm (NULL owner_id)."""
    from app.models.farm import Farm
    from tests.conftest import TestingSessionLocal

    db = TestingSessionLocal()
    try:
        legacy_farm = Farm(
            id="legacy-farm-003",
            name="Legacy Farm Gamma",
            latitude=30.0,
            longitude=75.0,
            total_area_hectares=10.0,
            soil_type="loam",
            primary_irrigation="rainfed",
            owner_id=None,
        )
        db.add(legacy_farm)
        db.commit()
        db.refresh(legacy_farm)
        legacy_farm_id = legacy_farm.id
    finally:
        db.close()

    response = auth_client.put(f"/api/farms/{legacy_farm_id}", json={
        "name": "Hacked Legacy Farm",
        "latitude": 30.0,
        "longitude": 75.0,
        "total_area_hectares": 10.0,
        "soil_type": "loam",
        "primary_irrigation": "rainfed",
    })
    assert response.status_code == 404


def test_user_cannot_access_legacy_farm_patch(auth_client: TestClient):
    """Normal user receives 404 when PATCHing a legacy farm (NULL owner_id)."""
    from app.models.farm import Farm
    from tests.conftest import TestingSessionLocal

    db = TestingSessionLocal()
    try:
        legacy_farm = Farm(
            id="legacy-farm-004",
            name="Legacy Farm Delta",
            latitude=30.0,
            longitude=75.0,
            total_area_hectares=10.0,
            soil_type="loam",
            primary_irrigation="rainfed",
            owner_id=None,
        )
        db.add(legacy_farm)
        db.commit()
        db.refresh(legacy_farm)
        legacy_farm_id = legacy_farm.id
    finally:
        db.close()

    response = auth_client.patch(f"/api/farms/{legacy_farm_id}", json={"name": "Hacked"})
    assert response.status_code == 404


def test_user_cannot_access_legacy_farm_delete(auth_client: TestClient):
    """Normal user receives 404 when DELETEing a legacy farm (NULL owner_id)."""
    from app.models.farm import Farm
    from tests.conftest import TestingSessionLocal

    db = TestingSessionLocal()
    try:
        legacy_farm = Farm(
            id="legacy-farm-005",
            name="Legacy Farm Epsilon",
            latitude=30.0,
            longitude=75.0,
            total_area_hectares=10.0,
            soil_type="loam",
            primary_irrigation="rainfed",
            owner_id=None,
        )
        db.add(legacy_farm)
        db.commit()
        db.refresh(legacy_farm)
        legacy_farm_id = legacy_farm.id
    finally:
        db.close()

    response = auth_client.delete(f"/api/farms/{legacy_farm_id}")
    assert response.status_code == 404


def test_user_cannot_set_owner_id_via_put(auth_client: TestClient):
    """PUT cannot transfer farm ownership via owner_id in payload."""
    # Create a farm owned by the authenticated user
    created = auth_client.post("/api/farms", json=get_sample_farm_payload()).json()
    farm_id = created["id"]
    assert created["owner_id"] == "test-user-123"

    # Try to change owner_id via PUT (should be ignored)
    updated_payload = get_sample_farm_payload()
    updated_payload["name"] = "Updated Name"
    updated_payload["owner_id"] = "some-other-user-id"  # This field isn't in FarmCreate schema

    put_resp = auth_client.put(f"/api/farms/{farm_id}", json=updated_payload)
    assert put_resp.status_code == 200
    data = put_resp.json()
    # Owner should remain the original authenticated user
    assert data["owner_id"] == "test-user-123"
    assert data["name"] == "Updated Name"


def test_user_cannot_set_owner_id_via_patch(auth_client: TestClient):
    """PATCH cannot transfer farm ownership via owner_id in payload."""
    # Create a farm owned by the authenticated user
    created = auth_client.post("/api/farms", json=get_sample_farm_payload()).json()
    farm_id = created["id"]
    assert created["owner_id"] == "test-user-123"

    # Try to change owner_id via PATCH (should be ignored)
    patch_payload = {
        "name": "Patched Name",
        "owner_id": "some-other-user-id",  # This field isn't in FarmUpdate schema
    }

    patch_resp = auth_client.patch(f"/api/farms/{farm_id}", json=patch_payload)
    assert patch_resp.status_code == 200
    data = patch_resp.json()
    # Owner should remain the original authenticated user
    assert data["owner_id"] == "test-user-123"
    assert data["name"] == "Patched Name"


# --- Root endpoint test ---

def test_root_endpoint_includes_farms_endpoint(client: TestClient):
    """Root GET / endpoint should include farms endpoint discovery link."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "farms_endpoint" in data
    assert data["farms_endpoint"] == "/api/farms"