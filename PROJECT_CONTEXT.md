# AGROVERSE AI — Project Context

## 1. Project Overview

**Project Name:** AGROVERSE AI
**Challenge:** NASA Space Apps Challenge 2026 — Field Shift: Adapting Farms with NASA Data
**Project Type:** AI-Powered Crop Rotation Decision Support Platform
**Initial Pilot Region:** West Bengal, India

AGROVERSE AI is a NASA-data-powered agricultural decision support platform that helps farmers explore better crop rotation strategies using historical climate information, soil and water context, and agricultural knowledge.

Our goal is not to build another generic weather or crop recommendation application. We want to help farmers compare different crop rotation strategies and understand why one strategy may be more suitable than another.

## 2. Core Problem

Farmers often make crop rotation decisions without having easy access to understandable climate insights, soil and water context, and comparisons of alternative cropping strategies.

AGROVERSE AI aims to make this information easier to understand and use.

## 3. Main Objectives

* Use real NASA Earth observation and climate datasets.
* Allow farmers to create a basic farm profile.
* Analyze historical climate conditions for a selected location.
* Consider soil type, irrigation availability, and previous crops.
* Compare multiple crop rotation strategies.
* Explain the benefits, risks, and limitations of each strategy.
* Generate an understandable crop rotation field plan.

## 4. Core Features

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
* Potential soil health benefits.
* Agricultural risks.

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
* Reason for the recommendation.
* Seasonal crop sequence.
* Potential benefits.
* Risks and limitations.

## 5. Technology Stack

### Frontend

* React
* Vite
* TypeScript
* Tailwind CSS
* Recharts
* Leaflet (for maps)

### Backend

* Python
* FastAPI
* Pandas
* NumPy

### Data

* NASA POWER API
* NASA GPM (optional)
* NASA SMAP (optional)
* NASA MODIS (optional)

### Version Control

* Git
* GitHub

Use a simple, maintainable architecture. Avoid unnecessary complexity.

## 6. API Contract

The frontend and backend must follow a consistent API contract.

Initial endpoints:

* `GET /api/health` — backend health check.
* `GET /api/climate` — retrieve climate information using latitude, longitude, and date range.
* `POST /api/farms` — create or process a farm profile.
* `POST /api/rotation/compare` — compare crop rotation strategies.

Responses should use consistent JSON structures.

Where relevant, include:

* `source`
* `retrieved_at`
* `units`
* `spatial_resolution`
* `is_demo`
* `limitations`

Do not expose NASA API credentials or other secrets in frontend code.

## 7. Data Integrity and Scientific Rules

These rules are mandatory:

1. Never fabricate NASA data.
2. Clearly distinguish real NASA data, user-entered information, and simulated demonstration data.
3. Never label simulated data as real satellite observations.
4. Do not claim field-level precision from coarse satellite datasets.
5. Do not guarantee crop yield, income, or agricultural success.
6. Explain uncertainty and dataset limitations.
7. Use credible agricultural references to validate local crop suitability.
8. If an API fails, show a clear error or explicitly labelled demo mode.

## 8. User Experience Requirements

The application should have:

* Modern, clean, professional agricultural dashboard.
* Responsive desktop and mobile layouts.
* Simple navigation.
* Easy-to-understand visualizations.
* Interactive farm location selection.
* Clear climate charts.
* Crop rotation comparison cards.
* An understandable final report.

Avoid excessive animations and unnecessarily complex UI elements.

The application must prioritize usability, performance, and clarity.

## 9. GitHub Branch Strategy

The repository uses the following branches:

* `main` — stable approved version.
* `integration` — combined project and integration testing.
* `feature/frontend` — Lovable frontend development.
* `feature/backend` — Antigravity backend development.
* `feature/qa` — Replit testing and QA.

Rules:

* Never push experimental changes directly to `main`.
* Do not overwrite another agent's work.
* Work only in the assigned branch.
* Use Pull Requests for merging.
* Do not rewrite the entire project unnecessarily.
* Preserve existing working functionality.

## 10. AI Agent Responsibilities

### Lovable — Frontend

Responsible for:

* Building the frontend interface.
* Farm profile forms.
* Dashboard.
* Climate visualizations.
* Crop rotation comparison UI.
* API integration with the agreed contract.

### Google Antigravity — Backend

Responsible for:

* Project backend structure.
* FastAPI endpoints.
* NASA API integration.
* Climate data processing.
* Crop rotation decision-support logic.
* Backend validation and error handling.

### Replit Agent — QA and Integration Support

Responsible for:

* Testing frontend and backend integration.
* API testing.
* Identifying bugs.
* Responsive UI testing.
* Data validation.
* Preparing deployment and testing documentation.

Agents must follow this document and the existing project architecture.

## 11. Minimum Viable Product (MVP)

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

## 12. Definition of Done

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

## 13. Development Philosophy

Build a working, scientifically responsible, understandable prototype rather than an unnecessarily complicated application.

Prioritize:

**Real NASA Data → Reliable Processing → Useful Crop Rotation Logic → Clear Comparison → Explainable Recommendations.**

Every contributor and AI coding agent must treat this document as the shared project reference.

