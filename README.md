# AGROVERSE AI

### From Space Data to Smarter Farming

AGROVERSE AI is a NASA-data-powered Crop Rotation Decision Support Platform developed for NASA Space Apps Challenge 2026.

## Project Vision

Help farmers make more informed crop rotation decisions using NASA Earth observation data, historical climate information, soil and water context, crop requirements, and farmer priorities.

## Core Features

* Farm Location and Profile
* NASA Climate Intelligence
* Soil and Water Context
* Crop Rotation Strategy Comparison
* Explainable Recommendations
* Farmer-Friendly Field Plans

## Technology Stack

| Layer | Technology |
|-------|------------|
| Frontend | React, TypeScript, Tailwind CSS, Vite |
| Backend | Python, FastAPI, SQLAlchemy 2.0, Alembic |
| Data | NASA POWER, MERRA-2, CERES |
| Visualization | Recharts, Leaflet, React-Leaflet |
| Authentication | JWT (HS256), PBKDF2-SHA256 (600k rounds) |
| Rate Limiting | SlowAPI (Redis-backed with in-memory fallback) |
| Security | Security Headers, CORS Validation, Gitleaks CI |
| ML Pipeline | scikit-learn, joblib, pandas, numpy |

## System Architecture

### Backend (FastAPI)

**API Layer:**
- RESTful endpoints with Pydantic v2 validation
- OpenAPI 3.0 auto-generated at `/openapi.json`
- Bearer token authentication (JWT)
- Role-based access control (USER/ADMIN)
- Farm ownership enforcement

**Core Services:**
- **NASA POWER Integration**: Async client for MERRA-2 (0.5°×0.625°) and CERES (1°×1°) datasets
- **Climate Analyzer**: Rainfall, temperature, GDD, heat/cold risk, crop suitability scoring
- **Crop Rotation Engine**: 6 rotation rules, 4 strategies, backtracking optimization, legume frequency enforcement
- **Farm Management**: CRUD with ownership, JSON crop history, enum serialization

**Security:**
- JWT access/refresh tokens with HS256, explicit algorithm pinning
- Password hashing: PBKDF2-SHA256, 600,000 rounds (OWASP 2024)
- Refresh token rotation with replay attack detection
- Account lockout: 5 attempts/15min sliding window (email+IP), 15min cooldown
- Rate limiting: Configurable limits, Redis-backed distributed, in-memory fallback
- Security headers: HSTS, CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy
- CORS: Strict origin validation, HTTPS enforcement in production
- Request logging: Correlation IDs, sensitive data redaction (41 fields + 7 patterns)
- Secret scanning: Gitleaks full-history CI scanning

**Database:**
- SQLAlchemy 2.0 with synchronous engine
- PostgreSQL QueuePool (pool_size=5, max_overflow=10, pre_ping)
- Alembic migrations (7 versions, linear chain)
- Production guards: `create_all()` skipped, `DATABASE_ECHO` rejected, async drivers rejected

### Frontend (React + Vite)

**Structure:**
- Component-based architecture with React 19
- Vite 8 for development and production builds
- ESLint for code quality
- React-Leaflet for interactive farm mapping
- Recharts for climate data visualization

**Key Components:**
- Farm drawing with Leaflet Draw integration
- Login/Authentication flows
- Landing page with project overview
- Navigation with auth state

### CRRS ML Pipeline (Crop Recommendation & Rotation System)

The CRRS system combines machine learning with agronomic logic to generate multi-season crop rotation plans based on predicted ROI.

#### 🔄 Model & Recommendation Flow

```text
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

#### 🧠 1. Feature Engineering

Training data is generated using crop, soil, and environmental conditions.

Two additional features are created:
- `water_availability = rainfall_mm × humidity_pct / 100`
- `heat_stress = temperature_c × humidity_pct`

Columns directly used to generate the target (yield, revenue, cost, market price, profit) are removed to avoid **data leakage**.

Outliers in numerical features are handled using the **IQR method**.

---

#### 📊 2. Model Features

The final `X` contains **7 features**:

```text
crop
soil_type
season
rainfall_mm
temperature_c
soil_ph
phosphorus_kg_ha
```

The target variable is:

```text
ROI_pct
```

ROI is calculated as:

```text
ROI (%) = (Profit / Cost) × 100
```

---

#### ⚙️ 3. Preprocessing

A `ColumnTransformer` is used inside the saved ML pipeline.

**Categorical features:**
```text
crop
soil_type
season
```
Processed using **OneHotEncoder**.

**Numerical features:**
```text
rainfall_mm
temperature_c
soil_ph
phosphorus_kg_ha
```
Processed using **StandardScaler**.

The complete preprocessing + model pipeline is saved as:
```text
Models/crop_profit_model(ROI).joblib
```

This same saved pipeline is used during prediction, ensuring that new input goes through the exact preprocessing used during training.

---

#### 🤖 4. Model Training

Multiple regression models are evaluated using cross-validation with:
- R²
- RMSE
- MAE

The best-performing model is selected and saved together with the preprocessing pipeline.

The final target is **ROI prediction**, not direct crop classification.

---

#### 🌾 5. Prediction in `crop_recco.py`

For every selected season, `crop_recco.py` creates candidate inputs for the available crops:

```text
crop
soil_type
season
rainfall_mm
temperature_c
soil_ph
phosphorus_kg_ha
```

These candidates are passed to the saved pipeline:
```text
Candidate Crops
      ↓
Saved Preprocessing
      ↓
ROI Model
      ↓
Predicted ROI
```

The crops are then ranked according to predicted ROI.

For the first season, the **top 3 crops** are selected as starting points for three different rotation plans.

---

#### 🔄 6. Crop Rotation

For subsequent seasons:
1. Remaining crops are evaluated.
2. ROI is predicted for each crop.
3. The highest-ROI crop is selected.
4. The selected crop is removed to prevent repetition.
5. Its effect on **soil pH and phosphorus** is applied.
6. The updated soil state is used for the next season.

```text
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

The system finally produces **three multi-season crop rotation plans**, along with their predicted ROI and resulting soil state.

---

#### 🎯 In Short

CRRS combines:
```text
Machine Learning
      +
ROI Prediction
      +
Soil Effect Logic
      +
Crop Rotation
```

to move from simply **predicting a profitable crop** to generating a **multi-season crop rotation recommendation** based on expected ROI and changing soil conditions.

## Security

- **Authentication**: JWT HS256 with explicit algorithm pinning (`algorithms=["HS256"]`) prevents algorithm confusion attacks
- **Password Hashing**: PBKDF2-SHA256, 600,000 rounds (exceeds OWASP 2024)
- **Token Management**: Access tokens (30 min), refresh tokens (7 days) with rotation and replay detection
- **Rate Limiting**: Configurable per-endpoint limits, Redis-backed with in-memory fallback
- **Security Headers**: HSTS, CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy
- **CORS**: Strict origin validation, HTTPS enforcement for non-localhost in production
- **Secret Scanning**: Gitleaks full-history CI scanning with custom config
- **Dependency Scanning**: pip-audit in CI pipeline
- **Audit Trail**: Comprehensive phase audit documentation (Phase 4.7)

## Data Principles

- Real NASA data, user-provided information, and simulated demonstration data must always be clearly distinguished
- Recommendations are decision-support estimates and do not replace local agricultural expertise
- NASA POWER data limitations disclosed: regional averages (0.5°–1° resolution), not hyper-local
- Missing value convention: -999.0 treated as missing

## Setup and Installation

### Prerequisites
- Python 3.12+
- Node.js 18+
- PostgreSQL 15+ (production) or SQLite (development)

### Backend Setup
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your configuration
alembic upgrade head
uvicorn app.main:app --reload
```

### Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

### Environment Variables
Key backend variables (see `backend/.env.example`):
- `SECRET_KEY` — JWT signing key (required, no default)
- `DATABASE_URL` — PostgreSQL URL (required for production)
- `ENVIRONMENT` — `development` or `production`
- `NASA_POWER_BASE_URL` — API endpoint
- `BEHIND_TRUSTED_PROXY` — Set to `true` if behind reverse proxy

## Running Tests

### Backend Tests
```bash
cd backend
pytest tests/ -v
# 482+ tests covering:
# - Authentication (27 tests)
# - Security & Headers (18 tests)
# - Rate Limiting (13 tests)
# - Database Pool & Session (15 tests)
# - Farms & Rotations APIs (30+ tests)
# - Climate Analyzer (12 tests)
# - Logging & Correlation IDs (57 tests)
# - Account Lockout, Password Reset, Sessions
```

### Frontend Tests
```bash
cd frontend
npm run lint
```

## Deployment

### Production Checklist
- [ ] Set `ENVIRONMENT=production`
- [ ] Configure `SECRET_KEY` (32+ chars)
- [ ] Set `DATABASE_URL` to PostgreSQL
- [ ] Set `BEHIND_TRUSTED_PROXY=true` if behind reverse proxy
- [ ] Configure CORS origins for frontend domain
- [ ] Run `alembic upgrade head` for migrations
- [ ] Ensure `gitleaks` and `pip-audit` pass in CI

### Docker (Optional)
```dockerfile
# Backend example
FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## Documentation

- **Phase 4.7A**: Dependency Security Investigation (`PHASE_4.7A_DEPENDENCY_SECURITY_INVESTIGATION.md`)
- **Phase 4.7A**: Executive Summary (`PHASE_4.7A_EXECUTIVE_SUMMARY.md`)
- **Phase 4.7B**: PyJWT Migration Completion (`PHASE_4.7B_MIGRATION_COMPLETION_REPORT.md`)
- **Phase 4.7**: Executive Summary (`PHASE_4.7_EXECUTIVE_SUMMARY.md`)
- **Phase 4.7**: Production Readiness Audit (`PHASE_4.7_PRODUCTION_READINESS_AUDIT.md`)
- **API Documentation**: Available at `/openapi.json` when running
- **Project Context**: `PROJECT_CONTEXT.md`

---

*AGROVERSE AI — NASA Space Apps Challenge 2026*