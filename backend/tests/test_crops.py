"""Tests for the Crop Knowledge Base catalog and crop details API."""

from fastapi.testclient import TestClient

EXPECTED_CROPS = {
    "rice",
    "wheat",
    "lentil",
    "mustard",
    "chickpea",
    "green_gram",
    "maize",
}


def test_catalog_returns_all_seven_crops(client: TestClient):
    """GET /api/crops/catalog should return all 7 calibrated crops for West Bengal."""
    response = client.get("/api/crops/catalog")
    assert response.status_code == 200
    data = response.json()

    assert data["total"] == 7
    assert data["pilot_region"] == "West Bengal, India"
    assert "provenance" in data["data_provenance_note"].lower() or "icar" in data["data_provenance_note"].lower()

    returned_ids = {c["crop_id"] for c in data["crops"]}
    assert returned_ids == EXPECTED_CROPS


def test_all_crops_have_valid_botanical_and_nitrogen_metadata(client: TestClient):
    """Verify botanical families and nitrogen dynamics adhere to established agronomic rules."""
    response = client.get("/api/crops/catalog")
    assert response.status_code == 200
    crops = {c["crop_id"]: c for c in response.json()["crops"]}

    # Legumes: Fabaceae, nitrogen fixers
    legume_ids = ["lentil", "chickpea", "green_gram"]
    for lid in legume_ids:
        crop = crops[lid]
        assert crop["botanical_family"] == "Fabaceae"
        assert crop["nitrogen_management"]["role"] == "nitrogen_fixer"
        assert crop["nitrogen_management"]["is_nitrogen_fixer"] is True
        assert crop["nitrogen_management"]["fixation_capacity_kg_ha"] is not None

    # Cereals: Poaceae, heavy feeders
    cereal_ids = ["rice", "wheat", "maize"]
    for cid in cereal_ids:
        crop = crops[cid]
        assert crop["botanical_family"] == "Poaceae"
        assert crop["nitrogen_management"]["role"] == "heavy_feeder"
        assert crop["nitrogen_management"]["is_nitrogen_fixer"] is False
        assert crop["nitrogen_management"]["fixation_capacity_kg_ha"] is None

    # Mustard: Brassicaceae, moderate feeder
    mustard = crops["mustard"]
    assert mustard["botanical_family"] == "Brassicaceae"
    assert mustard["nitrogen_management"]["role"] == "moderate_feeder"
    assert mustard["nitrogen_management"]["is_nitrogen_fixer"] is False


def test_gdd_base_temperatures_verified(client: TestClient):
    """Verify standard GDD base temperatures are defined and flagged as verified."""
    response = client.get("/api/crops/catalog")
    assert response.status_code == 200
    crops = {c["crop_id"]: c for c in response.json()["crops"]}

    # Base temperatures verified from ICAR / FAO
    expected_gdd_bases = {
        "rice": 10.0,
        "wheat": 5.0,
        "maize": 10.0,
        "chickpea": 8.0,
        "lentil": 5.0,
        "mustard": 5.0,
        "green_gram": 10.0,
    }

    for crop_id, expected_base in expected_gdd_bases.items():
        t_req = crops[crop_id]["temperature_requirement"]
        assert t_req["gdd_base_temp_c"] == expected_base
        assert t_req["gdd_base_verified"] is True


def test_water_requirement_classes(client: TestClient):
    """Verify water requirement classes match hydrological norms."""
    response = client.get("/api/crops/catalog")
    assert response.status_code == 200
    crops = {c["crop_id"]: c for c in response.json()["crops"]}

    # Rice is very high water demand (>900 mm)
    assert crops["rice"]["water_requirement"]["demand_class"] == "very_high"
    assert crops["rice"]["water_requirement"]["min_mm"] >= 900.0

    # Wheat and Maize are moderate (350-650 mm)
    assert crops["wheat"]["water_requirement"]["demand_class"] == "moderate"
    assert crops["maize"]["water_requirement"]["demand_class"] == "moderate"

    # Pulses and Mustard are low water demand (<350 mm)
    assert crops["lentil"]["water_requirement"]["demand_class"] == "low"
    assert crops["mustard"]["water_requirement"]["demand_class"] == "low"
    assert crops["chickpea"]["water_requirement"]["demand_class"] == "low"
    assert crops["green_gram"]["water_requirement"]["demand_class"] == "low"


def test_get_crop_by_id_success(client: TestClient):
    """GET /api/crops/{crop_id} should return full profile with citations."""
    response = client.get("/api/crops/rice")
    assert response.status_code == 200
    data = response.json()

    assert data["crop_id"] == "rice"
    assert data["crop_name"] == "Rice (Paddy)"
    assert data["scientific_name"] == "Oryza sativa"
    assert len(data["references"]) >= 2
    assert any("NRRI" in r["institution"] or "BCKV" in r["institution"] for r in data["references"])
    assert data["confidence_level"] == "high"


def test_get_crop_by_id_case_insensitive(client: TestClient):
    """Crop ID lookup should be case-insensitive."""
    response = client.get("/api/crops/WHEAT")
    assert response.status_code == 200
    assert response.json()["crop_id"] == "wheat"


def test_get_crop_by_id_not_found(client: TestClient):
    """Querying an unknown crop ID should return 404 with helpful detail."""
    response = client.get("/api/crops/nonexistent_crop")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()
    assert "rice" in response.json()["detail"].lower()


def test_catalog_filter_by_family(client: TestClient):
    """Filtering by botanical family should return matching subset."""
    # Fabaceae (Legumes) -> 3 crops
    fab_resp = client.get("/api/crops/catalog", params={"family": "Fabaceae"})
    assert fab_resp.status_code == 200
    fab_data = fab_resp.json()
    assert fab_data["total"] == 3
    assert {c["crop_id"] for c in fab_data["crops"]} == {"lentil", "chickpea", "green_gram"}

    # Poaceae (Cereals) -> 3 crops
    poa_resp = client.get("/api/crops/catalog", params={"family": "Poaceae"})
    assert poa_resp.status_code == 200
    poa_data = poa_resp.json()
    assert poa_data["total"] == 3
    assert {c["crop_id"] for c in poa_data["crops"]} == {"rice", "wheat", "maize"}

    # Brassicaceae (Mustard) -> 1 crop
    bras_resp = client.get("/api/crops/catalog", params={"family": "Brassicaceae"})
    assert bras_resp.status_code == 200
    bras_data = bras_resp.json()
    assert bras_data["total"] == 1
    assert bras_data["crops"][0]["crop_id"] == "mustard"


def test_catalog_filter_by_nitrogen_role(client: TestClient):
    """Filtering by nitrogen role should isolate fixers from heavy feeders."""
    fixer_resp = client.get("/api/crops/catalog", params={"nitrogen_role": "nitrogen_fixer"})
    assert fixer_resp.status_code == 200
    fixers = fixer_resp.json()
    assert fixers["total"] == 3
    assert {c["crop_id"] for c in fixers["crops"]} == {"lentil", "chickpea", "green_gram"}

    feeder_resp = client.get("/api/crops/catalog", params={"nitrogen_role": "heavy_feeder"})
    assert feeder_resp.status_code == 200
    feeders = feeder_resp.json()
    assert feeders["total"] == 3
    assert {c["crop_id"] for c in feeders["crops"]} == {"rice", "wheat", "maize"}


def test_catalog_filter_by_season(client: TestClient):
    """Filtering by season should match applicable crops."""
    # Kharif or Aman -> Rice, Maize, Green Gram
    aman_resp = client.get("/api/crops/catalog", params={"season": "Aman"})
    assert aman_resp.status_code == 200
    aman_crops = {c["crop_id"] for c in aman_resp.json()["crops"]}
    assert "rice" in aman_crops

    # Rabi -> Wheat, Lentil, Mustard, Chickpea, Maize, Boro Rice
    rabi_resp = client.get("/api/crops/catalog", params={"season": "Rabi"})
    assert rabi_resp.status_code == 200
    rabi_crops = {c["crop_id"] for c in rabi_resp.json()["crops"]}
    assert {"wheat", "lentil", "mustard", "chickpea", "maize"}.issubset(rabi_crops)


def test_catalog_filter_by_water_demand(client: TestClient):
    """Filtering by water demand class should return matching crops."""
    low_resp = client.get("/api/crops/catalog", params={"water_demand": "low"})
    assert low_resp.status_code == 200
    low_crops = {c["crop_id"] for c in low_resp.json()["crops"]}
    assert low_crops == {"lentil", "mustard", "chickpea", "green_gram"}


def test_root_endpoint_includes_crops_endpoint(client: TestClient):
    """Root GET / should include crops endpoint discovery link."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "crops_endpoint" in data
    assert data["crops_endpoint"] == "/api/crops/catalog"


def test_crop_data_credibility_and_provenance(client: TestClient):
    """Verify all crops have high confidence and non-empty institutional citations."""
    response = client.get("/api/crops/catalog")
    assert response.status_code == 200
    for crop in response.json()["crops"]:
        assert crop["confidence_level"] == "high"
        assert len(crop["references"]) > 0
        for ref in crop["references"]:
            assert ref["institution"] != ""
            assert ref["publication"] != ""
