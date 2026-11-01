# AGROVERSE AI — Backend

Backend API service for **AGROVERSE AI**, developed for the **NASA Space Apps Challenge 2026**.

This service serves as the core intelligence engine, ingesting, parsing, and validating Earth observation data from the NASA POWER API to power crop rotation decision-support models.

---

## 1. Features

* **NASA POWER Agroclimatology Integration:** Automated ingestion of daily precipitation, 2m temperature (mean, min, max), solar radiation, and relative humidity.
* **Scientific Integrity & Provenance:**
  * Parameter-specific spatial resolution and observational source tracking.
  * Explicit detection and handling of NASA fill values (`-999.0`) mapped to `null` with missing indicators.
  * Strict `is_simulated: false` guarantee for authentic NASA POWER observations.
* **Statistical Summaries:** Aggregated temperature ranges, total rainfall, mean solar irradiance, and valid observation counts powered by Pandas and NumPy.
* **Modular FastAPI Architecture:** Decoupled structure ready for frontend integration with modern React/TypeScript clients.
* **Input Validation:** Strict coordinate bounding (`[-90, 90]`, `[-180, 180]`), chronological date bounds, and maximum range limits.

---

## 2. Directory Structure

```text
backend/
├── app/
│   ├── main.py              # Application entry point, CORS middleware, API mounting
│   ├── core/
│   │   ├── config.py        # Settings via Pydantic-Settings & scientific metadata registry
│   ├── api/
│   │   └── routes/
│   │       ├── health.py    # GET /api/health
│   │       └── climate.py   # GET /api/climate
│   ├── schemas/
│   │   ├── health.py        # Health schemas
│   │   └── climate.py       # Pydantic models for queries, daily records, and metadata
│   └── services/
│       └── nasa_power.py    # Asynchronous NASA POWER client and Pandas aggregator
├── tests/
│   ├── conftest.py          # Pytest fixtures and mock NASA responses
│   ├── test_health.py       # Health check test suite
│   └── test_climate.py      # Input validation & scientific parsing tests
├── requirements.txt         # Backend Python dependencies
├── .env.example             # Configuration defaults
└── README.md                # This documentation
```

---

## 3. Installation & Setup

### Prerequisites
* Python 3.10+ (Tested on Python 3.12)
* `pip` and virtual environment tool (`venv`)

### 1. Create and Activate Virtual Environment
From the `backend/` directory:

**Windows (PowerShell):**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**macOS / Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

---

## 4. Running the Development Server

Start the FastAPI application with Uvicorn:

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

* **Interactive Swagger UI:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
* **ReDoc Documentation:** [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)
* **Health Check:** [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health)

---

## 5. API Endpoints

### `GET /api/health`
Returns backend operational status and version.

**Sample Response:**
```json
{
  "status": "healthy",
  "service": "AGROVERSE AI Backend",
  "version": "0.1.0",
  "environment": "development",
  "timestamp": "2026-11-02T00:36:00.000000Z"
}
```

---

### `GET /api/climate`
Fetches agro-climatological observations from NASA POWER for specified coordinates and date range.

**Query Parameters:**
| Parameter | Type | Required | Range / Format | Description |
|---|---|---|---|---|
| `latitude` | `float` | Yes | `-90.0` to `90.0` | Latitude in decimal degrees |
| `longitude` | `float` | Yes | `-180.0` to `180.0` | Longitude in decimal degrees |
| `start_date` | `string` | Yes | `YYYY-MM-DD` | Start date (cannot be after end_date) |
| `end_date` | `string` | Yes | `YYYY-MM-DD` | End date (cannot be in the future, max span 366 days) |

**Example Request:**
```http
GET /api/climate?latitude=28.6139&longitude=77.2090&start_date=2023-01-01&end_date=2023-01-05
```

**Sample Response Structure:**
```json
{
  "metadata": {
    "data_source": "NASA Langley Research Center (LaRC) POWER Project - Agroclimatology (AG) Community",
    "retrieval_timestamp": "2026-11-02T00:36:00.000000Z",
    "coordinates": {
      "latitude": 28.6139,
      "longitude": 77.209
    },
    "date_range": {
      "start_date": "2023-01-01",
      "end_date": "2023-01-05"
    },
    "parameters_info": {
      "T2M": {
        "name": "Temperature at 2 Meters",
        "units": "°C",
        "source": "NASA GMAO MERRA-2 Assimilation Model",
        "spatial_resolution": "0.5° latitude x 0.625° longitude (~50 km x ~60 km)",
        "description": "Daily mean air temperature at 2 meters above ground level."
      },
      "ALLSKY_SFC_SW_DWN": {
        "name": "All Sky Surface Shortwave Downward Irradiance",
        "units": "MJ/m²/day",
        "source": "NASA CERES SYN1deg / FLASHFlux / SRB Satellite Observations",
        "spatial_resolution": "1.0° latitude x 1.0° longitude (~110 km x ~110 km)",
        "description": "Total solar irradiance incident on a horizontal surface at the Earth's surface."
      }
    },
    "data_limitations": "NASA POWER data is based on global satellite observations and regional numerical reanalyses...",
    "is_simulated": false
  },
  "summary": {
    "avg_temperature_c": 13.52,
    "min_temperature_c": 7.1,
    "max_temperature_c": 19.8,
    "total_precipitation_mm": 0.0,
    "avg_precipitation_daily_mm": 0.0,
    "avg_solar_radiation_mj_m2": 12.45,
    "avg_relative_humidity_pct": 68.4,
    "total_days": 5,
    "valid_data_days": 5
  },
  "records": [
    {
      "date": "2023-01-01",
      "temperature_mean_c": 13.5,
      "temperature_max_c": 19.8,
      "temperature_min_c": 7.1,
      "precipitation_mm": 0.0,
      "solar_radiation_mj_m2": 12.45,
      "relative_humidity_pct": 68.4,
      "missing_parameters": []
    }
  ]
}
```

---

## 6. Scientific Rules & Provenance

1. **Parameter Resolution Disclosures:**
   * Meteorological parameters (`T2M`, `T2M_MAX`, `T2M_MIN`, `PRECTOTCORR`, `RH2M`) are sourced from **NASA GMAO MERRA-2** at **0.5° x 0.625°** (~50 km x ~60 km).
   * Solar radiation (`ALLSKY_SFC_SW_DWN`) is sourced from **NASA CERES SYN1deg / FLASHFlux / SRB** satellite measurements at **1.0° x 1.0°** (~110 km x ~110 km).
2. **Missing Observations Handling:**
   * NASA POWER fill values (`-999.0` or `-999`) are automatically identified and mapped to Python `None` (`null` in JSON), rather than numeric zero. Missing parameters are explicitly listed in `missing_parameters`.
3. **Simulated vs. Real Data Policy:**
   * `is_simulated` is set to `false` strictly when verified data is returned from NASA POWER. Mock/demo data will never be presented as real NASA measurements.
4. **Regional Estimates:**
   * Satellite reanalysis data models regional grid cells and does not account for micro-climates or field-specific topography.

---

## 7. Running Tests

Run the test suite using pytest:

```bash
pytest tests/ -v
```
