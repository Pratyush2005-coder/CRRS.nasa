# AGROVERSE AI — Project Context

## A. Product Vision

### NASA Space Apps Challenge 2026 Context
**Challenge:** Field Shift: Adapting Farms with NASA Data
**Theme:** Space Data for Smarter Farming
**Project Type:** AI-Powered Crop Rotation Decision Support Platform
**Initial Pilot Region:** West Bengal, India

### Core Problem
Crop rotation is one of the most critical agricultural practices for soil health, pest management, and water conservation. However, smallholder and regional farmers frequently lack access to high-resolution historical climate insights and agro-ecological modeling tailored to their specific coordinates. Farmers often make crop rotation decisions without having easy access to understandable climate insights, soil and water context, and comparisons of alternative cropping strategies.

### Main Objectives
* Use real NASA Earth observation and climate datasets.
* Allow farmers to create a basic farm profile.
* Analyze historical climate conditions for a selected location.
* Consider soil type, irrigation availability, and previous crops.
* Compare multiple crop rotation strategies.
* Explain the benefits, risks, and limitations of each strategy.
* Generate an understandable crop rotation field plan.

### Vision Statement
**AGROVERSE AI** bridges Earth observation data from NASA and on-the-ground agricultural decision-making. By leveraging historical climate intelligence (precipitation, temperature extremes, solar radiation, humidity) alongside soil and crop biology, AGROVERSE AI provides:
* Actionable, multi-season crop rotation recommendations.
* Climate resilience scoring for candidate crop sequences.
* Transparent risk modeling (drought, frost, heat stress).
* Clear distinctions between satellite observations, agronomic heuristics, and localized field variables.

Our goal is not to build another generic weather or crop recommendation application. We want to help farmers compare different crop rotation strategies and understand why one strategy may be more suitable than another.

---

## B. Core Features and Modules

### Module 1: Farm Profile
Users should be able to enter:
* Farm location (latitude and longitude or map selection).
* Farm size.
* Soil type.
* Irrigation availability.
* Previous crop.
* Current crop.
* Farming priorities.

### Module 2: NASA Climate Intelligence
Retrieve and analyze historical climate data using NASA datasets.

Primary data source:
* NASA POWER API — historical temperature, precipitation, solar radiation, and other available meteorological parameters.
* Parameter-level analysis: Precipitation Corrected (`PRECTOTCORR`), 2-meter Temperatures (`T2M`, `T2M_MAX`, `T2M_MIN`), Solar Irradiance (`ALLSKY_SFC_SW_DWN`), and Relative Humidity (`RH2M`).

Potential additional datasets:
* NASA GPM — precipitation observations.
* NASA SMAP — regional soil moisture information.
* NASA MODIS — vegetation indices such as NDVI, if time permits.

Every dataset must include its source, units, retrieval date, and relevant spatial or temporal limitations.

### Module 3: Soil and Water Context
Consider:
* User-provided soil information.
* Irrigation availability.
* Historical rainfall.
* Available regional soil moisture information.
* Soil moisture proxies and precipitation distribution throughout growing seasons.

NASA satellite soil moisture must not be presented as a direct field-level soil test.

### Module 4: Crop Rotation Engine
Build a decision-support engine that evaluates possible crop rotation sequences.

Illustrative comparison:
* Rice → Rice
* Rice → Lentil
* Rice → Mustard

These are examples for the prototype, not pre-validated recommendations. Crop suitability must be checked against local agricultural information, seasonal calendars, and available water conditions.

The engine should consider:
* Seasonal suitability.
* Historical rainfall and temperature.
* Soil compatibility.
* Water requirements.
* Crop diversity.
* Potential soil health benefits (nitrogen-fixing rotations, water-efficient sequences, disease-break rotations).
* Agricultural risks.
* Transparent risk modeling (drought, frost, heat stress).
* Climate resilience scoring for candidate crop sequences.

Do not invent scientific measurements or guaranteed yield improvements.

### Module 5: Strategy Comparison
Display at least three crop rotation strategies when sufficient information is available.

Compare them using understandable indicators:
* Climate suitability.
* Water considerations.
* Soil compatibility.
* Rotation diversity.
* Potential advantages.
* Risks and limitations.

Explain how each score is calculated. Do not present unvalidated estimates as scientifically proven results.

### Module 6: Explainable Field Plan
Generate a clear report containing:
* Selected farm information.
* Climate summary.
* Selected rotation strategy.
* Reason for the recommendation (plain-language reasoning explaining *why* a particular crop sequence was recommended).
* Seasonal crop sequence.
* Potential benefits.
* Risks and limitations.
* Farmer-friendly field calendars: Seasonal planting and harvesting windows based on historical temperature thresholds.

---

## C. Technology Stack

### Frontend
* **Framework:** React 19, Vite 8
* **Language:** JavaScript (ES Modules) — *Note: TypeScript planned for future*
* **Styling:** Vanilla CSS (Tailwind CSS planned)
* **Visualizations:** Recharts
* **Mapping:** Leaflet, React-Leaflet, Leaflet-Draw
* **Package Manager:** npm

### Backend
* **Language:** Python 3.12+
* **Framework:** FastAPI (high-performance asynchronous API framework)
* **Data Processing:** Pandas, NumPy
* **Data Validation & Settings:** Pydantic v2, Pydantic-Settings, pydantic[email]
* **HTTP Client:** HTTPX (async client for NASA POWER API requests)
* **Database:** SQLAlchemy 2.0 (sync), PostgreSQL (production), SQLite (dev)
* **Migrations:** Alembic
* **Authentication:** JWT (HS256), PBKDF2-SHA256 (600k rounds)
* **Rate Limiting:** SlowAPI (Redis-backed with in-memory fallback)
* **Testing:** Pytest, HTTPX TestClient, pytest-asyncio

### ML Pipeline (CRRS — Crop Recommendation & Rotation System)
* **Framework:** scikit-learn
* **Model Persistence:** joblib
* **Features:** 7 features (crop, soil_type, season, rainfall_mm, temperature_c, soil_ph, phosphorus_kg_ha)
* **Target:** ROI_pct (Return on Investment %)
* **Preprocessing:** ColumnTransformer (OneHotEncoder + StandardScaler)
* **Saved Pipeline:** `Models/crop_profit_model(ROI).joblib`

### Data Sources
* **NASA POWER API (Agroclimatology Community - AG):**
  * Temporal API (Daily Point queries).
  * GMAO MERRA-2 assimilation model (Meteorological parameters).
  * NASA CERES / FLASHFlux / SRB (Solar radiation parameters).
* **Potential:** NASA GPM, NASA SMAP, NASA MODIS

### Visualization
* **Charts:** Recharts (LineChart, AreaChart, BarChart)
* **Maps:** Leaflet, React-Leaflet, Esri World Imagery tiles

---

## D. API Contract

The frontend and backend must follow a consistent API contract.

### Initial Endpoints
* `GET /api/health` — backend health check.
  * Returns system health, version, timestamp, and environment.
* `GET /api/climate` — retrieve climate information using latitude, longitude, and date range.
  * Accepts `latitude` (-90 to 90), `longitude` (-180 to 180), `start_date` (YYYY-MM-DD), `end_date` (YYYY-MM-DD).
  * Validates coordinates and dates.
  * Queries NASA POWER Daily Point API for agroclimatology.
  * Formats daily observations with `-999.0` missing-data protection.
  * Returns comprehensive parameter metadata (units, sources, resolutions) and scientific caveats.
* `POST /api/farms` — create or process a farm profile.
* `POST /api/rotation/compare` — compare crop rotation strategies.

### Response Standards
Responses should use consistent JSON structures.

Where relevant, include:
* `source`
* `retrieved_at`
* `units`
* `spatial_resolution`
* `is_demo` (must be `false` **only** when data was successfully retrieved from live NASA APIs)
* `limitations`
* `missing_parameters` (list of parameters with missing observations)

Do not expose NASA API credentials or other secrets in frontend code.

---

## E. NASA Data Principles & Scientific Integrity

Scientific honesty and transparency are non-negotiable foundations of AGROVERSE AI:

### 1. Zero Fabrication Policy
* Real NASA data, simulated demonstration data, and user-provided inputs must never be conflated.
* `is_simulated` must be set to `false` **only** when data was successfully retrieved from live NASA APIs.
* Fallback, placeholder, or synthetic demo figures must never be labeled as real NASA observations.

### 2. Parameter-Specific Spatial Resolutions
NASA POWER data is **not** homogeneous in resolution. Each parameter's source and grid resolution must be explicitly disclosed:
* **Meteorological parameters (`T2M`, `T2M_MAX`, `T2M_MIN`, `PRECTOTCORR`, `RH2M`):** Derived from NASA GMAO MERRA-2 assimilation at **`0.5° latitude x 0.625° longitude`** (~50 km × 60 km grid).
* **Solar parameters (`ALLSKY_SFC_SW_DWN`):** Derived from satellite observations (NASA CERES SYN1deg / FLASHFlux / SRB) at **`1.0° latitude x 1.0° longitude`** (~110 km × 110 km grid).

### 3. Regional Satellite Estimates vs. In-Situ Sensors
* Satellite and global atmospheric reanalyses provide regional approximations.
* Field-level micro-climates, slope effects, localized soil variations, and hyper-local rain events cannot be captured at 50 km resolution.
* The platform clearly presents recommendations as **decision-support estimates**, not infallible replacements for local agronomic expertise or in-ground sensors.

### 4. Missing Value Handling
* NASA POWER uses `-999.0` (or `-999`) to indicate missing or uncomputed observations.
* These must **never** be interpreted as valid `0.0` or actual negative values.
* Missing observations are converted to `null` (`None`) and explicitly tracked in `missing_parameters` lists.

---

## F. Backend Architecture

```
backend/
├── app/
│   ├── main.py                 # FastAPI app instance, CORS middleware, API routers
│   ├── core/
│   │   ├── config.py           # Settings via Pydantic-Settings, parameter resolution registry
│   │   ├── rate_limiting.py    # SlowAPI limiter, custom exception handler, Redis backend
│   │   ├── security.py         # JWT, password hashing, token management
│   │   └── logging_config.py   # Structured logging, correlation IDs, redaction
│   ├── api/
│   │   └── routes/
│   │       ├── auth.py         # JWT auth (register, login, refresh, logout, password reset)
│   │       ├── climate.py      # NASA POWER climate data
│   │       ├── climate_analyzer.py # Climate analysis endpoints
│   │       ├── crops.py        # Crop catalog and knowledge base
│   │       ├── farms.py        # Farm CRUD with ownership
│   │       ├── health.py       # GET /api/health
│   │       ├── rotations.py    # Crop rotation recommendations
│   │       └── soil.py         # Soil pH analysis
│   ├── models/
│   │   ├── user.py             # User, RefreshToken, LoginAttempt, PasswordResetToken
│   │   ├── farm.py             # Farm, CropHistory
│   │   └── enums.py            # UserRole, SoilType, CropCategory
│   ├── schemas/
│   │   ├── auth.py             # Pydantic schemas for auth
│   │   ├── climate.py          # Pydantic schemas for climate inputs, records, metadata & summaries
│   │   ├── crops.py            # Crop schemas
│   │   ├── farms.py            # Farm schemas
│   │   ├── health.py           # Health check schemas
│   │   ├── rotations.py        # Rotation schemas
│   │   └── soil.py             # Soil schemas
│   ├── services/
│   │   ├── nasa_power.py       # Async client for NASA POWER API, parsing, aggregation
│   │   ├── climate_analyzer.py # Climate analysis logic
│   │   ├── crop_rotation.py    # Rotation engine (6 rules, 4 strategies, backtracking)
│   │   └── soil_analyzer.py    # Soil pH analysis
│   ├── db/
│   │   └── session.py          # SQLAlchemy session management
│   └── middleware/
│       └── correlation_id.py   # Request correlation ID middleware
├── alembic/                    # 7 migrations (linear chain)
├── tests/
│   ├── conftest.py             # Pytest fixtures, test isolation
│   ├── test_auth.py            # Auth, RBAC, password reset, account lockout
│   ├── test_rate_limiting.py   # Rate limiting with Redis/in-memory
│   ├── test_security_headers.py # Security headers middleware
│   ├── test_password_reset.py  # Password reset flow
│   ├── test_farms.py           # Farm CRUD, ownership
│   ├── test_rotations.py       # Rotation engine tests
│   └── test_climate.py         # Climate API tests
└── requirements.txt
```

### Key Services
* **NASA POWER Client** (`nasa_power.py`): Async HTTPX client with retry logic, parameter mapping, resolution metadata
* **Climate Analyzer** (`climate_analyzer.py`): Rainfall, temperature, GDD, heat/cold risk, crop suitability scoring
* **Crop Rotation Engine** (`crop_rotation.py`): 6 rotation rules, 4 strategies, backtracking optimization, legume frequency enforcement
* **Auth & Security**: JWT access/refresh tokens (HS256), PBKDF2-SHA256 (600k rounds), refresh token rotation with replay detection, account lockout (5 attempts/15min sliding window), security headers (HSTS, CSP, X-Frame-Options, etc.)

---

## G. Frontend Architecture and UX Requirements

### Component Structure
```
frontend/
├── src/
│   ├── App.jsx                 # Main app with login gating, dashboard, all modules
│   ├── components/
│   │   ├── Login/
│   │   │   ├── Login.jsx       # Login form with email/password
│   │   │   └── Login.css
│   │   └── FarmDraw/
│   │       └── FarmDraw.jsx    # Leaflet Draw integration
│   ├── FarmDraw.jsx            # Farm drawing component
│   ├── App.css                 # Main styles
│   └── main.jsx                # Entry point
├── index.html
├── package.json
├── vite.config.js
└── eslint.config.js
```

### UX Requirements
* Modern, clean, professional agricultural dashboard.
* Responsive desktop and mobile layouts.
* Simple navigation (sidebar with anchor links to sections).
* Easy-to-understand visualizations (Recharts line charts for climate data).
* Interactive farm location selection (Leaflet map with Draw plugin).
* Clear climate charts (Temperature, Rainfall, Humidity, Solar Radiation).
* Crop rotation comparison cards.
* AI Farming Advisor (placeholder for future LLM integration).
* Soil pH checking with backend integration.
* An understandable final report.

Avoid excessive animations and unnecessarily complex UI elements.

The application must prioritize usability, performance, and clarity.

---

## H. CRRS ML Pipeline (Crop Recommendation & Rotation System)

The CRRS system combines machine learning with agronomic logic to generate multi-season crop rotation plans based on predicted ROI.

### Model & Recommendation Flow
```
Farmer / Default Input
        ↓
Feature Engineering
        ↓
Feature Selection
        ↓
Outlier Removal
        ↓
Train-Test Split
        ↓
Preprocessing
        ↓
Model Training & Evaluation
        ↓
Saved ML Pipeline
        ↓
crop_recco.py
        ↓
Predict ROI for Available Crops
        ↓
Rank Crops by ROI
        ↓
Select Top 3 Starting Crops
        ↓
Crop Rotation + Soil Update
        ↓
Final Rotation Plans
```

### 1. Feature Engineering
Training data generated using crop, soil, and environmental conditions.

Two additional features created:
* `water_availability = rainfall_mm × humidity_pct / 100`
* `heat_stress = temperature_c × humidity_pct`

Columns directly used to generate the target (yield, revenue, cost, market price, profit) are removed to avoid **data leakage**.

Outliers in numerical features handled using the **IQR method**.

### 2. Model Features
Final `X` contains **7 features**:
```
crop
soil_type
season
rainfall_mm
temperature_c
soil_ph
phosphorus_kg_ha
```

Target variable: `ROI_pct`

ROI calculated as: `ROI (%) = (Profit / Cost) × 100`

### 3. Preprocessing
A `ColumnTransformer` is used inside the saved ML pipeline.

**Categorical features:**
```
crop
soil_type
season
```
Processed using **OneHotEncoder**.

**Numerical features:**
```
rainfall_mm
temperature_c
soil_ph
phosphorus_kg_ha
```
Processed using **StandardScaler**.

Complete preprocessing + model pipeline saved as:
`Models/crop_profit_model(ROI).joblib`

Same saved pipeline used during prediction, ensuring new input goes through exact preprocessing used during training.

### 4. Model Training
Multiple regression models evaluated using cross-validation with:
* R²
* RMSE
* MAE

Best-performing model selected and saved together with preprocessing pipeline.

Final target is **ROI prediction**, not direct crop classification.

### 5. Prediction in `crop_recco.py`
For every selected season, creates candidate inputs for available crops:
```
crop
soil_type
season
rainfall_mm
temperature_c
soil_ph
phosphorus_kg_ha
```

Candidates passed to saved pipeline:
```
Candidate Crops
      ↓
Saved Preprocessing
      ↓
ROI Model
      ↓
Predicted ROI
```

Crops ranked according to predicted ROI.

For first season, **top 3 crops** selected as starting points for three different rotation plans.

### 6. Crop Rotation
For subsequent seasons:
1. Remaining crops evaluated.
2. ROI predicted for each crop.
3. Highest-ROI crop selected.
4. Selected crop removed to prevent repetition.
5. Its effect on **soil pH and phosphorus** applied.
6. Updated soil state used for next season.

```
Current Soil
     ↓
Select Crop
     ↓
Predict ROI
     ↓
Apply Crop's Soil Effect
     ↓
Updated Soil
     ↓
Next Season
```

System produces **three multi-season crop rotation plans**, along with predicted ROI and resulting soil state.

### Summary
CRRS combines:
```
Machine Learning
      +
ROI Prediction
      +
Soil Effect Logic
      +
Crop Rotation
```
to move from simply **predicting a profitable crop** to generating a **multi-season crop rotation recommendation** based on expected ROI and changing soil conditions.

---

## I. Security and Data Integrity

### Authentication
* **JWT HS256** with explicit algorithm pinning (`algorithms=["HS256"]`) prevents algorithm confusion attacks
* **Password Hashing**: PBKDF2-SHA256, 600,000 rounds (exceeds OWASP 2024)
* **Token Management**: Access tokens (30 min), refresh tokens (7 days) with rotation and replay detection
* **Account Lockout**: 5 attempts/15min sliding window (email+IP), 15min cooldown

### Rate Limiting
* Configurable per-endpoint limits
* Redis-backed distributed rate limiting with in-memory fallback
* 429 responses include Retry-After headers and custom JSON body

### Security Headers
* HSTS, CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy

### CORS
* Strict origin validation, HTTPS enforcement for non-localhost in production

### Secret Scanning
* Gitleaks full-history CI scanning with custom config
* Dependency scanning: pip-audit in CI pipeline

### Request Logging
* Correlation IDs, sensitive data redaction (41 fields + 7 patterns)

---

## J. GitHub Branch Strategy

The repository uses the following branches:

* `main` — stable approved version.
* `integration` — combined project and integration testing.
* `feature/frontend` — Frontend development.
* `feature/backend` — Backend development.
* `feature/qa` — Testing and QA.

### Rules:
* Never push experimental changes directly to `main`.
* Do not overwrite another agent's work.
* Work only in the assigned branch.
* Use Pull Requests for merging.
* Do not rewrite the entire project unnecessarily.
* Preserve existing working functionality.

---

## K. AI Agent Responsibilities

### Frontend Agent (Lovable equivalent)
Responsible for:
* Building the frontend interface.
* Farm profile forms.
* Dashboard.
* Climate visualizations.
* Crop rotation comparison UI.
* API integration with the agreed contract.

### Backend Agent (Antigravity equivalent)
Responsible for:
* Project backend structure.
* FastAPI endpoints.
* NASA API integration.
* Climate data processing.
* Crop rotation decision-support logic.
* Backend validation and error handling.

### QA Agent (Replit equivalent)
Responsible for:
* Testing frontend and backend integration.
* API testing.
* Identifying bugs.
* Responsive UI testing.
* Data validation.
* Preparing deployment and testing documentation.

Agents must follow this document and the existing project architecture.

---

## L. MVP Checklist and Definition of Done

### Minimum Viable Product (MVP)
The first working version must include:
1. Farm profile input.
2. Location selection.
3. Real NASA POWER climate data retrieval.
4. Climate visualization.
5. Basic crop rotation comparison engine.
6. Comparison of alternative rotation strategies.
7. Explainable recommendation report.
8. Responsive interface.
9. Proper error handling.

Optional datasets and advanced features should only be added after the core workflow works reliably.

### Definition of Done
The project is considered ready for demonstration when:
* A user can enter farm information.
* The application can retrieve real NASA climate data.
* Climate information is displayed correctly.
* At least two or three rotation strategies can be compared where data permits.
* The recommendation has a transparent explanation.
* The application distinguishes real and demo data.
* Frontend and backend communicate successfully.
* Major errors and limitations are handled clearly.
* The application works on desktop and mobile.

---

## M. Development Philosophy and Git Rules

### Development Philosophy
Build a working, scientifically responsible, understandable prototype rather than an unnecessarily complicated application.

Prioritize:
**Real NASA Data → Reliable Processing → Useful Crop Rotation Logic → Clear Comparison → Explainable Recommendations.**

Every contributor and AI coding agent must treat this document as the shared project reference.

### Git Rules
1. **Workspace Boundary:** Work is restricted strictly to the `nasa` workspace folder.
2. **Branch Discipline:** Active development remains on feature branches. Do not switch to or modify `main`, `integration`, or other branches without coordination.
3. **No Pushing:** Do not push to remote GitHub repositories without user approval.
4. **Modularity:** The backend is self-contained in `backend/` to ensure clean separation from the frontend in `frontend/`.
5. **Commit Messages:** Use conventional commits (feat, fix, chore, docs, refactor, test).
6. **No Force Push:** Never force push to shared branches.

---