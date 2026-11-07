import pandas as pd
import numpy as np
import random
from pathlib import Path


def random_default_input_creator(number_of_seasons=1):

    # 1991-2020 NASA POWER/MERRA-2 seasonal P10-P90 ranges for Kolkata
    # (Kharif: Jun-Sep, Rabi: Oct-Mar, Zaid: Apr-May); not statewide averages.
    rain_kharif = random.randint(872, 1385)
    temp_kharif = round(random.uniform(28.1, 28.9), 1)

    rain_rabi = random.randint(134, 344)
    temp_rabi = round(random.uniform(21.3, 22.6), 1)

    rain_zaid = random.randint(100, 264)
    temp_zaid = round(random.uniform(30.2, 32.3), 1)

    # Match the synthetic soil-feature distributions used in Model_trainning.ipynb.
    soil_ph = np.clip(np.random.normal(6.5, 0.8), 4.5, 8.5)
    phosphorus_kg_ha = np.clip(np.random.normal(30, 10), 10, 80)

    soils = [
        "sandy clay loam",
        "clay",
        "sandy loam",
        "loam",
        "loamy sand",
        "clay loam"
    ]
    soil_probs = [1 / len(soils)] * len(soils)

    soil_type = np.random.choice(soils, p=soil_probs)

    # ------------------------------------------------------
    # SEASONS FARMER WANTS
    # ------------------------------------------------------

    seasons = [
        "Kharif",
        "Rabi",
        "Zaid"
    ]

    season_probs = [0.70, 0.25, 0.05]
    number_of_seasons = min(number_of_seasons, len(seasons))

    if number_of_seasons < 1:
        raise ValueError("number_of_seasons must be at least 1.")

    selected_seasons = np.random.choice(
        seasons,
        size=number_of_seasons,
        replace=False,
        p=season_probs
    ).tolist()

    # Keep seasons in the normal agricultural order.
    season_order = {
        "Kharif": 0,
        "Rabi": 1,
        "Zaid": 2
    }

    selected_seasons = sorted(
        selected_seasons,
        key=lambda season: season_order[season]
    )

    # ------------------------------------------------------
    # CROPS AVAILABLE IN EACH SEASON
    # ------------------------------------------------------

    season_crop_groups = {
        "Kharif": [
            "rice",
            "maize",
            "ragi",
            "horse_gram",
            "moth_bean",
            "peas_beans",
            "tomato",
            "brinjal",
            "cucurbits",
            "bhindi",
            "onion"
        ],

        "Rabi": [
            "horse_gram",
            "moth_bean",
            "peas_beans",
            "safflower",
            "potato",
            "tomato",
            "brinjal",
            "cabbage",
            "cauliflower",
            "onion"
        ],

        "Zaid": [
            "maize",
            "ragi",
            "peas_beans",
            "potato",
            "tomato",
            "brinjal",
            "cucurbits",
            "bhindi",
            "onion"
        ]
    }

    # ------------------------------------------------------
    # RANDOMLY SELECT CROPS FOR EACH SELECTED SEASON
    #
    # A farmer can choose different crops for different
    # seasons. Therefore selected_crops is season-specific.
    # Example:
    #
    # {
    #     "Kharif": ["rice", "maize"],
    #     "Rabi": ["potato", "cabbage", "onion"]
    # }
    # ------------------------------------------------------

    selected_crops = {}

    for season in selected_seasons:

        suitable_crops = season_crop_groups[season]

        # Random number of crops for this particular season.
        number_of_crops = random.randint(
            1,
            len(suitable_crops)
        )

        selected_crops[season] = random.sample(
            suitable_crops,
            number_of_crops
        )

    # ------------------------------------------------------
    # ROTATION NEEDS AT LEAST 3 CROPS
    #
    # If random selection happened to produce fewer than
    # three crops across all selected seasons, add random
    # suitable crops without duplicating any crop.
    # ------------------------------------------------------

    total_selected_crops = sum(
        len(crops)
        for crops in selected_crops.values()
    )

    if total_selected_crops < 3:

        while total_selected_crops < 3:

            season = random.choice(selected_seasons)

            remaining_crops = [
                crop
                for crop in season_crop_groups[season]
                if crop not in selected_crops[season]
            ]

            if not remaining_crops:
                continue

            selected_crops[season].append(
                random.choice(remaining_crops)
            )

            total_selected_crops += 1

    # ------------------------------------------------------
    # FARMER DATA
    #
    # The crop column contains the complete crop vocabulary.
    # selected_crops separately tells the rotation logic
    # which crops the farmer chose for which season.
    # ------------------------------------------------------

    all_crops = [
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

    farmer_df = pd.DataFrame({
        "crop": all_crops,
        "soil_type": [soil_type] * len(all_crops),

        # Base season remains the first selected season.
        # The actual season-specific crop choices are stored
        # in selected_crops.
        "season": [selected_seasons[0]] * len(all_crops),

        "rainfall_mm": [rain_kharif] * len(all_crops),
        "temperature_c": [temp_kharif] * len(all_crops),
        "soil_ph": [soil_ph] * len(all_crops),
        "phosphorus_kg_ha": [phosphorus_kg_ha] * len(all_crops)
    })

    # ------------------------------------------------------
    # ENVIRONMENTAL CONDITIONS FOR EACH SEASON
    # ------------------------------------------------------

    season_conditions = {

        "Kharif": {
            "rainfall_mm": rain_kharif,
            "temperature_c": temp_kharif
        },

        "Rabi": {
            "rainfall_mm": rain_rabi,
            "temperature_c": temp_rabi
        },

        "Zaid": {
            "rainfall_mm": rain_zaid,
            "temperature_c": temp_zaid
        }
    }

    return {
        "farmer_df": farmer_df,
        "season_conditions": season_conditions,
        "selected_seasons": selected_seasons,
        "selected_crops": selected_crops
    }


if __name__ == "__main__":

    result = random_default_input_creator()

    output_dir = Path.cwd()

    farmer_path = output_dir / "default_farmer_inputs.csv"
    result["farmer_df"].to_csv(
        farmer_path,
        index=False
    )

    season_conditions = pd.DataFrame.from_dict(
        result["season_conditions"],
        orient="index"
    )

    season_conditions.index.name = "season"

    season_conditions["selected"] = [
        season in result["selected_seasons"]
        for season in season_conditions.index
    ]

    conditions_path = output_dir / "default_season_conditions.csv"

    season_conditions.to_csv(
        conditions_path
    )

    print(f"Farmer inputs saved to: {farmer_path}")
    print(f"Season conditions saved to: {conditions_path}")

    print("\nSelected seasons:")
    for season in result["selected_seasons"]:
        print(f"  {season}: {result['selected_crops'][season]}")

    print(
        "\nTotal selected crops:",
        sum(
            len(crops)
            for crops in result["selected_crops"].values()
        )
    )
