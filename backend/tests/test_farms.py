"""Comprehensive tests for Farm Profile Management CRUD API."""

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


def test_create_farm_success(client: TestClient):
    """POST /api/farms with valid data should return 201 and created farm with UUID."""
    payload = get_sample_farm_payload()
    response = client.post("/api/farms", json=payload)
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


def test_create_farm_invalid_latitude_returns_422(client: TestClient):
    """Latitude > 90 must fail validation."""
    payload = get_sample_farm_payload()
    payload["latitude"] = 95.0
    response = client.post("/api/farms", json=payload)
    assert response.status_code == 422
    assert "latitude" in str(response.json()).lower()


def test_create_farm_invalid_longitude_returns_422(client: TestClient):
    """Longitude < -180 must fail validation."""
    payload = get_sample_farm_payload()
    payload["longitude"] = -195.0
    response = client.post("/api/farms", json=payload)
    assert response.status_code == 422
    assert "longitude" in str(response.json()).lower()


def test_create_farm_invalid_area_returns_422(client: TestClient):
    """Area <= 0 must fail validation."""
    payload = get_sample_farm_payload()
    payload["total_area_hectares"] = -5.0
    response = client.post("/api/farms", json=payload)
    assert response.status_code == 422


def test_create_farm_invalid_soil_type_returns_422(client: TestClient):
    """Unrecognized soil_type enum must return 422."""
    payload = get_sample_farm_payload()
    payload["soil_type"] = "martian_dust"
    response = client.post("/api/farms", json=payload)
    assert response.status_code == 422


def test_create_farm_missing_required_fields_returns_422(client: TestClient):
    """Missing required name or coordinates returns 422."""
    response = client.post("/api/farms", json={"soil_type": "clay"})
    assert response.status_code == 422


def test_get_farm_by_id_success(client: TestClient):
    """GET /api/farms/{farm_id} should return existing farm."""
    created = client.post("/api/farms", json=get_sample_farm_payload()).json()
    farm_id = created["id"]

    response = client.get(f"/api/farms/{farm_id}")
    assert response.status_code == 200
    fetched = response.json()
    assert fetched["id"] == farm_id
    assert fetched["name"] == created["name"]


def test_get_farm_by_id_not_found(client: TestClient):
    """GET /api/farms/{non_existent_id} should return 404."""
    random_id = str(uuid.uuid4())
    response = client.get(f"/api/farms/{random_id}")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_list_farms_empty_and_populated(client: TestClient):
    """GET /api/farms should list all farm profiles with count."""
    # Initially empty
    empty_resp = client.get("/api/farms")
    assert empty_resp.status_code == 200
    assert empty_resp.json()["total"] == 0
    assert empty_resp.json()["items"] == []

    # Insert two farms
    p1 = get_sample_farm_payload()
    p1["name"] = "Farm Alpha"
    client.post("/api/farms", json=p1)

    p2 = get_sample_farm_payload()
    p2["name"] = "Farm Beta"
    client.post("/api/farms", json=p2)

    list_resp = client.get("/api/farms")
    assert list_resp.status_code == 200
    data = list_resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


def test_list_farms_pagination(client: TestClient):
    """Pagination query params (skip, limit) should be respected."""
    for i in range(5):
        p = get_sample_farm_payload()
        p["name"] = f"Plot {i+1}"
        client.post("/api/farms", json=p)

    resp = client.get("/api/farms", params={"skip": 2, "limit": 2})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 5
    assert len(data["items"]) == 2
    assert data["skip"] == 2
    assert data["limit"] == 2


def test_list_farms_search_filter(client: TestClient):
    """Searching should match name, farmer_name, region, or country."""
    p1 = get_sample_farm_payload()
    p1["name"] = "Golden Wheat Estate"
    p1["region"] = "Sonipat"
    p1["soil_type"] = "clay"
    client.post("/api/farms", json=p1)

    p2 = get_sample_farm_payload()
    p2["name"] = "Silver Valley"
    p2["region"] = "Bathinda"
    p2["soil_type"] = "sandy"
    client.post("/api/farms", json=p2)

    # Search by region
    search_resp = client.get("/api/farms", params={"search": "Sonipat"})
    assert search_resp.status_code == 200
    items = search_resp.json()["items"]
    assert len(items) == 1
    assert items[0]["name"] == "Golden Wheat Estate"

    # Filter by soil type
    soil_resp = client.get("/api/farms", params={"soil_type": "sandy"})
    assert soil_resp.status_code == 200
    soil_items = soil_resp.json()["items"]
    assert len(soil_items) == 1
    assert soil_items[0]["name"] == "Silver Valley"


def test_put_farm_success(client: TestClient):
    """PUT /api/farms/{id} should fully update farm attributes."""
    created = client.post("/api/farms", json=get_sample_farm_payload()).json()
    farm_id = created["id"]

    updated_payload = get_sample_farm_payload()
    updated_payload["name"] = "Updated Station Name"
    updated_payload["total_area_hectares"] = 48.0
    updated_payload["soil_type"] = "clay"

    put_resp = client.put(f"/api/farms/{farm_id}", json=updated_payload)
    assert put_resp.status_code == 200
    data = put_resp.json()
    assert data["id"] == farm_id
    assert data["name"] == "Updated Station Name"
    assert data["total_area_hectares"] == 48.0
    assert data["soil_type"] == "clay"


def test_put_farm_not_found(client: TestClient):
    """PUT /api/farms/{non_existent_id} should return 404."""
    random_id = str(uuid.uuid4())
    resp = client.put(f"/api/farms/{random_id}", json=get_sample_farm_payload())
    assert resp.status_code == 404


def test_patch_farm_partial_update(client: TestClient):
    """PATCH /api/farms/{id} should update only provided fields."""
    created = client.post("/api/farms", json=get_sample_farm_payload()).json()
    farm_id = created["id"]

    patch_payload = {
        "name": "Partially Modified Farm",
        "soil_ph": 8.0,
    }
    patch_resp = client.patch(f"/api/farms/{farm_id}", json=patch_payload)
    assert patch_resp.status_code == 200
    data = patch_resp.json()
    assert data["name"] == "Partially Modified Farm"
    assert data["soil_ph"] == 8.0
    # Unmodified fields should remain untouched
    assert data["latitude"] == created["latitude"]
    assert data["total_area_hectares"] == created["total_area_hectares"]
    assert data["soil_type"] == created["soil_type"]


def test_patch_farm_not_found(client: TestClient):
    """PATCH /api/farms/{non_existent_id} should return 404."""
    random_id = str(uuid.uuid4())
    resp = client.patch(f"/api/farms/{random_id}", json={"name": "New Name"})
    assert resp.status_code == 404


def test_delete_farm_success(client: TestClient):
    """DELETE /api/farms/{id} should return 204 and remove the resource."""
    created = client.post("/api/farms", json=get_sample_farm_payload()).json()
    farm_id = created["id"]

    del_resp = client.delete(f"/api/farms/{farm_id}")
    assert del_resp.status_code == 204

    # Subsequent GET should return 404
    get_resp = client.get(f"/api/farms/{farm_id}")
    assert get_resp.status_code == 404


def test_delete_farm_not_found(client: TestClient):
    """DELETE /api/farms/{non_existent_id} should return 404."""
    random_id = str(uuid.uuid4())
    resp = client.delete(f"/api/farms/{random_id}")
    assert resp.status_code == 404


def test_root_endpoint_includes_farms_endpoint(client: TestClient):
    """Root GET / endpoint should include farms endpoint discovery link."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "farms_endpoint" in data
    assert data["farms_endpoint"] == "/api/farms"
