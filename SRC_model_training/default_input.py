import pandas as pd 
import numpy as np
import random 
from pathlib import Path

def random_default_input_creator():

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
        soils = ['sandy clay loam', 'clay', 'sandy loam', 'loam', 'loamy sand', 'clay loam']
        soil_probs = [1 / len(soils)] * len(soils)

        soil_type = np.random.choice(soils, p=soil_probs)

        seasons = [  
            "Kharif",
            "Rabi",
            "Zaid"
        ]
        season_probs = [0.70, 0.25, 0.05]
        #'season': np.random.choice(seasons, n_rows, p=season_probs)
        number_of_seasons = random.randint(1, 3)
        selected_seasons = np.random.choice(
        seasons,
        size=number_of_seasons,
        replace=False,
        p=season_probs
        ).tolist()

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

        "soil_type": [soil_type] * 15,

        "season": [selected_seasons[0]] * 15,

        "rainfall_mm": [rain_kharif] * 15,

        "temperature_c": [temp_kharif] * 15,

        "soil_ph": [soil_ph] * 15,

        "phosphorus_kg_ha": [phosphorus_kg_ha] * 15
    })

    # ------------------------------------------------------
    # SEASONS FARMER WANTS
    # ------------------------------------------------------




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
        return {"farmer_df":farmer_df,
                "season_conditions":season_conditions,
                "selected_seasons":selected_seasons}


if __name__ == "__main__":
    result = random_default_input_creator()
    output_dir = Path.cwd()

    farmer_path = output_dir / "default_farmer_inputs.csv"
    result["farmer_df"].to_csv(farmer_path, index=False)

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
    season_conditions.to_csv(conditions_path)

    print(f"Farmer inputs saved to: {farmer_path}")
    print(f"Season conditions saved to: {conditions_path}")