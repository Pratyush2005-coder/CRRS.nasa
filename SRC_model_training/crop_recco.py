import pandas as pd
import joblib
import json


class CropRecommendation:

    CROPS = [
        "rice",
        "maize",
        "ragi",
        "horse_gram",
        "moth_bean",
        "peas_beans",
        "safflower",
        "potato",
        "tomato",
        "brinjal",
        "cucurbits",
        "cabbage",
        "cauliflower",
        "bhindi",
        "onion"
    ]

    SEASON_ORDER = {
        "Kharif": 0,
        "Rabi": 1,
        "Zaid": 2
    }

    # Seasonal suitability used to restrict the farmer-selected crop pool.
    SEASONAL_CROPS = {
        "Kharif": {"rice", "maize", "ragi", "horse_gram", "moth_bean", "peas_beans", "tomato", "brinjal", "cucurbits", "bhindi", "onion"},
        "Rabi": {"horse_gram", "moth_bean", "peas_beans", "safflower", "potato", "tomato", "brinjal", "cabbage", "cauliflower", "onion"},
        "Zaid": {"maize", "ragi", "peas_beans", "potato", "tomato", "brinjal", "cucurbits", "bhindi", "onion"}
    }

    def __init__(
        self,
        farmer_df,
        selected_seasons,
        selected_crops,
        season_conditions,
        model_path=r"..\Models\crop_profit_model(ROI).joblib"
    ):

        self.farmer_df = farmer_df.copy()

        # --------------------------------------------------
        # LOAD SAVED MODEL / PIPELINE
        # --------------------------------------------------

        self.model = joblib.load(model_path)

        # --------------------------------------------------
        # CHECK REQUIRED COLUMNS
        # --------------------------------------------------

        required_columns = [
            "crop",
            "soil_type",
            "season",
            "rainfall_mm",
            "temperature_c",
            "soil_ph",
            "phosphorus_kg_ha"
        ]

        missing = [
            col for col in required_columns
            if col not in self.farmer_df.columns
        ]

        if missing:
            raise ValueError(
                f"Missing columns in farmer_df: {missing}"
            )

        # --------------------------------------------------
        # SORT SEASONS CHRONOLOGICALLY
        # --------------------------------------------------

        self.selected_seasons = sorted(
            selected_seasons,
            key=lambda x: self.SEASON_ORDER[x]
        )

        if not self.selected_seasons:
            raise ValueError("At least one season must be selected.")

        # selected_crops can be either:
        # 1. a list for Crop Recommendation (one selected season), or
        # 2. a dictionary for Crop Rotation, where each season has its
        #    own selected crop list.
        if isinstance(selected_crops, dict):
            self.selected_crops = {
                season: list(dict.fromkeys(crops))
                for season, crops in selected_crops.items()
            }
        else:
            self.selected_crops = list(dict.fromkeys(selected_crops))

        all_selected_crops = self._flatten_selected_crops()

        invalid_crops = [
            crop for crop in all_selected_crops
            if crop not in self.CROPS
        ]

        if invalid_crops:
            raise ValueError(
                f"Invalid selected crops: {invalid_crops}"
            )

        self.season_conditions = season_conditions

        # --------------------------------------------------
        # INITIAL SOIL STATE
        # --------------------------------------------------

        first_row = self.farmer_df.iloc[0]

        self.initial_soil_state = {
            "soil_ph": float(first_row["soil_ph"]),
            "phosphorus_kg_ha": float(
                first_row["phosphorus_kg_ha"]
            )
        }

    def _flatten_selected_crops(self):
        """Return all farmer-selected crops as one unique list."""

        if isinstance(self.selected_crops, dict):
            return list(dict.fromkeys(
                crop
                for crops in self.selected_crops.values()
                for crop in crops
            ))

        return self.selected_crops.copy()

    def _selected_crops_for_season(self, season):
        """Return only the crops the farmer selected for this season."""

        if isinstance(self.selected_crops, dict):
            return self.selected_crops.get(season, []).copy()

        # Recommendation mode has one crop list because only one season
        # is selected.
        return self.selected_crops.copy()

    # ======================================================
    # CREATE DATAFRAME FOR CROP PREDICTION
    # ======================================================

    def create_candidate_dataframe(
        self,
        soil_state,
        available_crops,
        season
    ):

        first_row = self.farmer_df.iloc[0]

        rainfall = self.season_conditions[season]["rainfall_mm"]
        temperature = self.season_conditions[season]["temperature_c"]

        rows = []

        for crop in available_crops:

            rows.append({
                "crop": crop,
                "soil_type": first_row["soil_type"],
                "season": season,
                "rainfall_mm": rainfall,
                "temperature_c": temperature,
                "soil_ph": soil_state["soil_ph"],
                "phosphorus_kg_ha": soil_state[
                    "phosphorus_kg_ha"
                ]
            })

        return pd.DataFrame(rows)

    # ======================================================
    # PREDICT ROI FOR ALL AVAILABLE CROPS
    # ======================================================

    def evaluate_crops(
        self,
        soil_state,
        season,
        available_crops=None
    ):

        # Start from the crops explicitly selected by the farmer for this
        # season. If a rotation plan has already used a crop, available_crops
        # can further restrict that season's pool.
        selected_for_season = self._selected_crops_for_season(season)

        if available_crops is not None:
            selected_for_season = [
                crop for crop in selected_for_season
                if crop in available_crops
            ]

        # Only season-suitable crops are allowed into prediction.
        seasonal_crops = self.SEASONAL_CROPS[season]
        season_available_crops = [
            crop for crop in selected_for_season
            if crop in seasonal_crops
        ]

        if not season_available_crops:
            raise ValueError(
                f"No selected crops are available for the {season} season."
            )

        candidate_df = self.create_candidate_dataframe(
            soil_state,
            season_available_crops,
            season
        )

        # --------------------------------------------------
        # IMPORTANT:
        # Your saved pipeline already contains preprocessing.
        # Therefore we directly call predict().
        # --------------------------------------------------

        predicted_roi = self.model.predict(candidate_df)

        candidate_df["predicted_ROI"] = predicted_roi

        candidate_df = candidate_df.sort_values(
            by="predicted_ROI",
            ascending=False
        ).reset_index(drop=True)

        return candidate_df

    # ======================================================
    # UPDATE SOIL AFTER A CROP IS ACTUALLY SELECTED
    # ======================================================

    def update_soil_state(
        self,
        soil_state,
        selected_crop
    ):

        new_state = soil_state.copy()

        # ==================================================
        # PUT YOUR FINAL CROP EFFECT VALUES HERE
        # ==================================================
        #
        # pH effect:
        # positive  -> soil pH increases
        # negative  -> soil pH decreases
        #
        # phosphorus effect:
        # positive  -> phosphorus increases
        # negative  -> phosphorus decreases
        #
        # These are deliberately kept as 0 until you put
        # your finalized crop-specific values here.
        # ==================================================

        crop_effects = {

    "rice": {
        "ph": -0.10,
        "phosphorus": -0.40
    },

    "maize": {
        "ph": -0.08,
        "phosphorus": -0.55
    },

    "ragi": {
        "ph": -0.06,
        "phosphorus": -0.35
    },

    "horse_gram": {
        "ph": -0.04,
        "phosphorus": -0.30
    },

    "moth_bean": {
        "ph": -0.04,
        "phosphorus": -0.30
    },

    "peas_beans": {
        "ph": -0.03,
        "phosphorus": -0.45
    },

    "safflower": {
        "ph": -0.07,
        "phosphorus": -0.50
    },

    "potato": {
        "ph": -0.05,
        "phosphorus": -0.20
    },

    "tomato": {
        "ph": -0.06,
        "phosphorus": -0.35
    },

    "brinjal": {
        "ph": -0.05,
        "phosphorus": -0.35
    },

    "cucurbits": {
        "ph": -0.04,
        "phosphorus": -0.30
    },

    "cabbage": {
        "ph": -0.06,
        "phosphorus": -0.35
    },

    "cauliflower": {
        "ph": -0.06,
        "phosphorus": -0.35
    },

    "bhindi": {
        "ph": -0.05,
        "phosphorus": -0.30
    },

    "onion": {
        "ph": -0.04,
        "phosphorus": -0.15
    }
}

        effect = crop_effects[selected_crop]

        # --------------------------------------------------
        # UPDATE SOIL pH
        # --------------------------------------------------

        new_state["soil_ph"] += effect["ph"]

        # Keep pH in realistic range
        new_state["soil_ph"] = max(
            0,
            min(14, new_state["soil_ph"])
        )

        # --------------------------------------------------
        # UPDATE PHOSPHORUS
        # --------------------------------------------------

        new_state["phosphorus_kg_ha"] += effect[
            "phosphorus"
        ]

        # Prevent negative phosphorus
        new_state["phosphorus_kg_ha"] = max(
            0,
            new_state["phosphorus_kg_ha"]
        )

        return new_state

    # ======================================================
    # CREATE ONE ROTATION PLAN
    # ======================================================

    def create_rotation_plan(
        self,
        first_crop
    ):

        used_crops = set()

        current_soil_state = self.initial_soil_state.copy()

        plan = []

        total_roi = 0

        # --------------------------------------------------
        # GO THROUGH ONLY SELECTED SEASONS
        # --------------------------------------------------

        for season_index, season in enumerate(
            self.selected_seasons
        ):

            # ==============================================
            # FIRST SEASON
            # ==============================================

            if season_index == 0:

                selected_crop = first_crop

                # Find ROI of selected first crop
                evaluation_df = self.evaluate_crops(
                    current_soil_state,
                    season,
                    available_crops=[
                        crop for crop in self._selected_crops_for_season(season)
                        if crop not in used_crops
                    ]
                )

                selected_row = evaluation_df[
                    evaluation_df["crop"] == selected_crop
                ].iloc[0]

                roi = float(
                    selected_row["predicted_ROI"]
                )

            # ==============================================
            # NEXT SEASONS
            # ==============================================

            else:

                evaluation_df = self.evaluate_crops(
                    current_soil_state,
                    season,
                    available_crops=[
                        crop for crop in self._selected_crops_for_season(season)
                        if crop not in used_crops
                    ]
                )

                # Highest ROI remaining crop
                selected_row = evaluation_df.iloc[0]

                selected_crop = selected_row["crop"]

                roi = float(
                    selected_row["predicted_ROI"]
                )

            # --------------------------------------------------
            # ADD SELECTED CROP TO PLAN
            # --------------------------------------------------

            plan.append({
                "season": season,
                "crop": selected_crop,
                "predicted_ROI": roi,
                "soil_ph_before": current_soil_state[
                    "soil_ph"
                ],
                "phosphorus_before": current_soil_state[
                    "phosphorus_kg_ha"
                ]
            })

            total_roi += roi

            # --------------------------------------------------
            # REMOVE CROP FROM THIS PLAN
            # --------------------------------------------------

            used_crops.add(selected_crop)

            # --------------------------------------------------
            # UPDATE SOIL ONLY AFTER CROP IS SELECTED
            # --------------------------------------------------

            current_soil_state = self.update_soil_state(
                current_soil_state,
                selected_crop
            )

        # --------------------------------------------------
        # FINAL PLAN RESULT
        # --------------------------------------------------

        return {
            "plan": plan,
            "total_ROI": total_roi,
            "final_soil_state": current_soil_state
        }

    # ======================================================
    # MAIN PREDICTOR
    # ======================================================

    def predictor(self):

        # --------------------------------------------------
        # FIRST SEASON
        # --------------------------------------------------

        first_season = self.selected_seasons[0]

        first_season_evaluation = self.evaluate_crops(
            self.initial_soil_state,
            first_season
        )

        # --------------------------------------------------
        # TOP 3 CROPS FOR THREE DIFFERENT PLANS
        # --------------------------------------------------

        top_3_crops = first_season_evaluation.head(3)[
            "crop"
        ].tolist()

        # --------------------------------------------------
        # CREATE 3 INDEPENDENT ROTATION PLANS
        # --------------------------------------------------

        rotation_plans = []

        for i, first_crop in enumerate(top_3_crops, start=1):

            plan_result = self.create_rotation_plan(
                first_crop
            )

            rotation_plans.append({
                "rotation_plan": i,
                "starting_crop": first_crop,
                "total_ROI": plan_result["total_ROI"],
                "seasons": plan_result["plan"],
                "final_soil_state": plan_result[
                    "final_soil_state"
                ]
            })

        # --------------------------------------------------
        # RETURN RESULT
        # --------------------------------------------------

        return rotation_plans


# ==========================================================
# EXAMPLE USAGE
# ==========================================================

if __name__ == "__main__":

    # ------------------------------------------------------
    # YOUR FARMER DATA
    # ------------------------------------------------------

    selected_crops = {
        "Kharif": ["rice", "maize", "ragi"],
        "Rabi": ["potato", "cabbage", "onion"],
        "Zaid": ["cucurbits", "bhindi", "tomato"]
    }

    farmer_df = pd.DataFrame({
        "crop": CropRecommendation.CROPS,
        "soil_type": ["loamy"] * 15,
        "season": ["Kharif"] * 15,
        "rainfall_mm": [850] * 15,
        "temperature_c": [28] * 15,
        "soil_ph": [6.5] * 15,
        "phosphorus_kg_ha": [42] * 15
    })

    # ------------------------------------------------------
    # SEASONS FARMER WANTS
    # ------------------------------------------------------

    selected_seasons = [
        "Kharif",
        "Rabi",
        "Zaid"
    ]

    # ------------------------------------------------------
    # ENVIRONMENTAL CONDITIONS FOR EACH SEASON
    # ------------------------------------------------------

    season_conditions = {

        "Kharif": {
            "rainfall_mm": 850,
            "temperature_c": 28
        },

        "Rabi": {
            "rainfall_mm": 450,
            "temperature_c": 20
        },

        "Zaid": {
            "rainfall_mm": 300,
            "temperature_c": 30
        }
    }

    # ------------------------------------------------------
    # CREATE RECOMMENDER
    # ------------------------------------------------------

    recommender = CropRecommendation(
        farmer_df=farmer_df,
        selected_seasons=selected_seasons,
        selected_crops=selected_crops,
        season_conditions=season_conditions,
        model_path=r"..\Models\crop_profit_model(ROI).joblib"
    )

    # ------------------------------------------------------
    # GENERATE 3 ROTATION PLANS
    # ------------------------------------------------------

    results = recommender.predictor()

    # ------------------------------------------------------
    # SAVE AS JSON
    # ------------------------------------------------------

    with open(
        "rotation_plans.json",
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            results,
            file,
            indent=4
        )

    print("\n===== ROTATION PLANS =====\n")

    print(
        json.dumps(
            results,
            indent=4
        )
    )