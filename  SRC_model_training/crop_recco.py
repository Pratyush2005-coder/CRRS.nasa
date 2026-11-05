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

    def __init__(
        self,
        farmer_df,
        selected_seasons,
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
        available_crops,
        season
    ):

        candidate_df = self.create_candidate_dataframe(
            soil_state,
            available_crops,
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

        available_crops = self.CROPS.copy()

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
                    available_crops,
                    season
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
                    available_crops,
                    season
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

            available_crops.remove(selected_crop)

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
            self.CROPS,
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

    farmer_df = pd.DataFrame({
        "crop": [
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
        ],

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