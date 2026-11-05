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

* Frontend: React, TypeScript, Tailwind CSS
* Backend: Python, FastAPI
* Data: NASA POWER and other relevant NASA Earth observation datasets
* Visualization: Interactive maps and data charts

## Important Data Principles

Real NASA data, user-provided information, and simulated demonstration data must always be clearly distinguished.

Recommendations are decision-support estimates and do not replace local agricultural expertise.

## Project Status

Initial development and project setup.  

# 🌱 CRRS - Crop Recommendation & Rotation System

CRRS uses a **machine-learning-based ROI prediction system** to recommend profitable crops and generate multi-season crop rotation plans.

## 🔄 Model & Recommendation Flow

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

## 🧠 1. Feature Engineering

The training data is generated using crop, soil and environmental conditions.

Two additional features are created:

- `water_availability = rainfall_mm × humidity_pct / 100`
- `heat_stress = temperature_c × humidity_pct`

Columns directly used to generate the target, such as yield, revenue, cost, market price and profit, are removed to avoid **data leakage**.

Outliers in numerical features are handled using the **IQR method**.

---

## 📊 2. Model Features

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

## ⚙️ 3. Preprocessing

A `ColumnTransformer` is used inside the saved ML pipeline.

### Categorical features

```text
crop
soil_type
season
```

are processed using **OneHotEncoder**.

### Numerical features

```text
rainfall_mm
temperature_c
soil_ph
phosphorus_kg_ha
```

are processed using **StandardScaler**.

The complete preprocessing + model pipeline is saved as:

```text
Models/crop_profit_model(ROI).joblib
```

This same saved pipeline is used during prediction, ensuring that new input goes through the exact preprocessing used during training.

---

## 🤖 4. Model Training

Multiple regression models are evaluated using cross-validation with:

- R²
- RMSE
- MAE

The best-performing model is selected and saved together with the preprocessing pipeline.

The final target is **ROI prediction**, not direct crop classification.

---

## 🌾 5. Prediction in `crop_recco.py`

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

## 🔄 6. Crop Rotation

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

## 🎯 In Short

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
