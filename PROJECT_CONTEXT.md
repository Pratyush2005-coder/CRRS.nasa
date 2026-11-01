# AGROVERSE AI — Project Context & Architecture

**NASA Space Apps Challenge 2026**  
**Theme:** Space Data for Smarter Farming  
**Project:** AGROVERSE AI — NASA-Data-Powered Crop Rotation Decision Support Platform  

---

## 1. Project Purpose & Vision

Crop rotation is one of the most critical agricultural practices for soil health, pest management, and water conservation. However, smallholder and regional farmers frequently lack access to high-resolution historical climate insights and agro-ecological modeling tailored to their specific coordinates.

**AGROVERSE AI** bridges Earth observation data from NASA and on-the-ground agricultural decision-making. By leveraging historical climate intelligence (precipitation, temperature extremes, solar radiation, humidity) alongside soil and crop biology, AGROVERSE AI provides:
* Actionable, multi-season crop rotation recommendations.
* Climate resilience scoring for candidate crop sequences.
* Transparent risk modeling (drought, frost, heat stress).
* Clear distinctions between satellite observations, agronomic heuristics, and localized field variables.

---

## 2. Core Features

1. **Location & Geospatial Profiling:**
   * Global coordinate lookup (latitude, longitude).
   * Regional agro-climatological context mapping.
2. **NASA Climate Intelligence:**
   * Multi-year historical weather patterns from NASA POWER.
   * Parameter-level analysis: Precipitation Corrected (`PRECTOTCORR`), 2-meter Temperatures (`T2M`, `T2M_MAX`, `T2M_MIN`), Solar Irradiance (`ALLSKY_SFC_SW_DWN`), and Relative Humidity (`RH2M`).
3. **Soil, Moisture & Water Context:**
   * Soil moisture proxies and precipitation distribution throughout growing seasons.
4. **Crop Rotation Strategy Comparison:**
   * Nitrogen-fixing rotations, water-efficient sequences, and disease-break rotations.
5. **Explainable Recommendations:**
   * Plain-language reasoning explaining *why* a particular crop sequence was recommended.
6. **Farmer-Friendly Field Calendars:**
   * Seasonal planting and harvesting windows based on historical temperature thresholds.

---

## 3. Technology Stack

### Backend
* **Language:** Python 3.12+
* **Framework:** FastAPI (high-performance asynchronous API framework)
* **Data Processing:** Pandas, NumPy
* **Data Validation & Settings:** Pydantic v2, Pydantic-Settings
* **HTTP Client:** HTTPX (async client for NASA POWER API requests)
* **Testing:** Pytest, HTTPX TestClient

### Frontend (Future Integration)
* **Framework:** React, TypeScript
* **Styling:** Tailwind CSS / Vanilla CSS
* **Mapping & Visualizations:** Leaflet / Mapbox, Recharts / Chart.js

### Data Sources
* **NASA POWER API (Agroclimatology Community - AG):**
  * Temporal API (Daily Point queries).
  * GMAO MERRA-2 assimilation model (Meteorological parameters).
  * NASA CERES / FLASHFlux / SRB (Solar radiation parameters).

---

## 4. NASA Data Principles & Scientific Integrity

Scientific honesty and transparency are non-negotiable foundations of AGROVERSE AI:

1. **Zero Fabrication Policy:**
   * Real NASA data, simulated demonstration data, and user-provided inputs must never be conflated.
   * `is_simulated` must be set to `false` **only** when data was successfully retrieved from live NASA APIs.
   * Fallback, placeholder, or synthetic demo figures must never be labeled as real NASA observations.

2. **Parameter-Specific Spatial Resolutions:**
   * NASA POWER data is **not** homogeneous in resolution. Each parameter's source and grid resolution must be explicitly disclosed:
     * **Meteorological parameters (`T2M`, `T2M_MAX`, `T2M_MIN`, `PRECTOTCORR`, `RH2M`):** Derived from NASA GMAO MERRA-2 assimilation at **`0.5° latitude x 0.625° longitude`** (~50 km × 60 km grid).
     * **Solar parameters (`ALLSKY_SFC_SW_DWN`):** Derived from satellite observations (NASA CERES SYN1deg / FLASHFlux / SRB) at **`1.0° latitude x 1.0° longitude`** (~110 km × 110 km grid).

3. **Regional Satellite Estimates vs. In-Situ Sensors:**
   * Satellite and global atmospheric reanalyses provide regional approximations.
   * Field-level micro-climates, slope effects, localized soil variations, and hyper-local rain events cannot be captured at 50 km resolution.
   * The platform clearly presents recommendations as **decision-support estimates**, not infallible replacements for local agronomic expertise or in-ground sensors.

4. **Missing Value Handling:**
   * NASA POWER uses `-999.0` (or `-999`) to indicate missing or uncomputed observations.
   * These must **never** be interpreted as valid `0.0` or actual negative values.
   * Missing observations are converted to `null` (`None`) and explicitly tracked in `missing_parameters` lists.

---

## 5. Backend Architecture & API Design

```
backend/
├── app/
│   ├── main.py              # FastAPI app instance, CORS middleware, API routers
│   ├── core/
│   │   ├── config.py        # Settings via Pydantic-Settings, parameter resolution registry
│   ├── api/
│   │   └── routes/
│   │       ├── health.py    # GET /api/health
│   │       └── climate.py   # GET /api/climate
│   ├── schemas/
│   │   ├── health.py        # Pydantic schemas for health checks
│   │   └── climate.py       # Pydantic schemas for inputs, records, metadata & summaries
│   └── services/
│       └── nasa_power.py    # Async client for NASA POWER API, parsing, aggregation
└── tests/
    ├── conftest.py          # Pytest fixtures and mocks
    ├── test_health.py       # Health check test suite
    └── test_climate.py      # Input validation & data parsing tests
```

### Initial Endpoints
* `GET /api/health`:
  * Returns system health, version, timestamp, and environment.
* `GET /api/climate`:
  * Accepts `latitude` (-90 to 90), `longitude` (-180 to 180), `start_date` (YYYY-MM-DD), `end_date` (YYYY-MM-DD).
  * Validates coordinates and dates.
  * Queries NASA POWER Daily Point API for agroclimatology.
  * Formats daily observations with `-999.0` missing-data protection.
  * Returns comprehensive parameter metadata (units, sources, resolutions) and scientific caveats.

---

## 6. Development & Git Rules

1. **Workspace Boundary:** Work is restricted strictly to the `nasa` workspace folder.
2. **Branch Discipline:** Active development remains on `feature/backend`. Do not switch to or modify `main`, `integration`, or other branches.
3. **No Pushing:** Do not push to remote GitHub repositories without user approval.
4. **Modularity:** The backend is self-contained in `backend/` to ensure clean separation from the future React frontend.
