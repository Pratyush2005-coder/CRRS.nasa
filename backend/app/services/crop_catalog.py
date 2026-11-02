"""Modular Crop Knowledge Base Service calibrated for West Bengal, India.

Scientific attributions and agronomic benchmarks are derived from:
- ICAR (Indian Council of Agricultural Research) Institutes (NRRI, IIWBR, IIPR, IIMR, DRMR)
- Bidhan Chandra Krishi Viswavidyalaya (BCKV), Mohanpur, West Bengal (Package of Practices)
- FAO Irrigation and Drainage Paper No. 56 and No. 33 (Crop Water Requirements and Yield Response)
"""

from typing import Dict, List, Optional
from app.schemas.crop import (
    BotanicalFamily,
    ConfidenceLevel,
    Crop,
    CropReference,
    DurationRange,
    NitrogenManagement,
    NitrogenRole,
    RootingDepthClass,
    SoilSuitability,
    TemperatureRequirement,
    WaterDemandClass,
    WaterRequirement,
)
from app.schemas.farm import SoilType

# Data provenance notice
PROVENANCE_STATEMENT = (
    "Calibrated for the agro-climatic zones of West Bengal (New Alluvial, Old Alluvial, "
    "Red Laterite, Coastal Saline, and Terai-Teesta tracts). Agronomic thresholds and "
    "botanical classifications are sourced from ICAR institute manuals, BCKV Package of Practices, "
    "and FAO Irrigation & Drainage Papers. Numerical values reflect established regional benchmarks "
    "and do not guarantee individual field yields."
)

WEST_BENGAL_CROPS: Dict[str, Crop] = {
    "rice": Crop(
        crop_id="rice",
        crop_name="Rice (Paddy)",
        scientific_name="Oryza sativa",
        botanical_family=BotanicalFamily.POACEAE,
        pilot_region="West Bengal, India",
        growing_seasons=["Aman (Kharif / Monsoon)", "Boro (Winter / Irrigated)", "Aus (Pre-Kharif)"],
        duration=DurationRange(
            min_days=100,
            max_days=150,
            typical_days=125,
        ),
        rooting_depth_class=RootingDepthClass.SHALLOW,
        water_requirement=WaterRequirement(
            demand_class=WaterDemandClass.VERY_HIGH,
            min_mm=900.0,
            max_mm=1500.0,
            critical_growth_stages=[
                "Seedling establishment",
                "Active tillering",
                "Panicle initiation",
                "Flowering / Anthesis",
            ],
        ),
        soil_suitability=SoilSuitability(
            suitable_soil_types=[
                SoilType.CLAY,
                SoilType.CLAY_LOAM,
                SoilType.SILT_LOAM,
            ],
            drainage_requirement="Tolerates and requires standing water (puddled lowland); low percolation preferred",
            min_ph=4.5,
            max_ph=8.0,
            optimal_min_ph=5.5,
            optimal_max_ph=7.0,
        ),
        temperature_requirement=TemperatureRequirement(
            min_temp_c=16.0,
            max_temp_c=38.0,
            optimal_min_temp_c=22.0,
            optimal_max_temp_c=32.0,
            gdd_base_temp_c=10.0,
            gdd_base_verified=True,
        ),
        nitrogen_management=NitrogenManagement(
            role=NitrogenRole.HEAVY_FEEDER,
            is_nitrogen_fixer=False,
            fixation_capacity_kg_ha=None,
            residual_nitrogen_effect=(
                "Depletes high amounts of nitrogen (80-120 kg N/ha applied). High potassium and silica extraction. "
                "Benefits significantly from green manuring (Dhaincha/Sesbania) or following a pulse crop."
            ),
        ),
        references=[
            CropReference(
                institution="ICAR-National Rice Research Institute (NRRI)",
                publication="Handbook of Rice Cultivation & Agronomic Practices",
                details="Cuttack, Odisha / West Bengal Regional Stations",
            ),
            CropReference(
                institution="Bidhan Chandra Krishi Viswavidyalaya (BCKV)",
                publication="Package of Practices for Field Crops: Kharif and Boro Rice",
                details="Directorate of Extension Education, Mohanpur, West Bengal",
            ),
            CropReference(
                institution="FAO",
                publication="Crop Evapotranspiration - Guidelines for Computing Crop Water Requirements (Paper 56)",
                details="Chapter 6, Submerged Rice Irrigation Requirements",
            ),
        ],
        confidence_level=ConfidenceLevel.HIGH,
        unverified_fields=[],
    ),
    "wheat": Crop(
        crop_id="wheat",
        crop_name="Wheat",
        scientific_name="Triticum aestivum",
        botanical_family=BotanicalFamily.POACEAE,
        pilot_region="West Bengal, India",
        growing_seasons=["Rabi (Winter)"],
        duration=DurationRange(
            min_days=100,
            max_days=120,
            typical_days=110,
        ),
        rooting_depth_class=RootingDepthClass.MEDIUM,
        water_requirement=WaterRequirement(
            demand_class=WaterDemandClass.MODERATE,
            min_mm=350.0,
            max_mm=500.0,
            critical_growth_stages=[
                "Crown root initiation (CRI, 20-25 DAS)",
                "Tillering",
                "Late jointing / Booting",
                "Flowering",
                "Milking / Grain filling",
            ],
        ),
        soil_suitability=SoilSuitability(
            suitable_soil_types=[
                SoilType.LOAM,
                SoilType.SANDY_LOAM,
                SoilType.CLAY_LOAM,
                SoilType.SILT_LOAM,
            ],
            drainage_requirement="Well-drained; highly intolerant of waterlogging and soil crusting",
            min_ph=5.5,
            max_ph=8.2,
            optimal_min_ph=6.0,
            optimal_max_ph=7.5,
        ),
        temperature_requirement=TemperatureRequirement(
            min_temp_c=5.0,
            max_temp_c=32.0,
            optimal_min_temp_c=15.0,
            optimal_max_temp_c=25.0,
            gdd_base_temp_c=5.0,
            gdd_base_verified=True,
        ),
        nitrogen_management=NitrogenManagement(
            role=NitrogenRole.HEAVY_FEEDER,
            is_nitrogen_fixer=False,
            fixation_capacity_kg_ha=None,
            residual_nitrogen_effect=(
                "Requires 100-120 kg N/ha in split applications. When rotated after a legume crop (Lentil, Mung), "
                "synthetic nitrogen application can be reduced by 20-30 kg N/ha."
            ),
        ),
        references=[
            CropReference(
                institution="ICAR-Indian Institute of Wheat and Barley Research (IIWBR)",
                publication="Wheat Production Technologies for Eastern Gangetic Plains",
                details="Karnal, Haryana & Eastern Regional Stations",
            ),
            CropReference(
                institution="Bidhan Chandra Krishi Viswavidyalaya (BCKV)",
                publication="Package of Practices for Rabi Crops: Wheat",
                details="Mohanpur, West Bengal",
            ),
            CropReference(
                institution="FAO",
                publication="Irrigation and Drainage Paper No. 33: Yield Response to Water",
                details="Wheat Crop Coefficient and Stress Sensitivity",
            ),
        ],
        confidence_level=ConfidenceLevel.HIGH,
        unverified_fields=[],
    ),
    "lentil": Crop(
        crop_id="lentil",
        crop_name="Lentil (Masoor)",
        scientific_name="Lens culinaris",
        botanical_family=BotanicalFamily.FABACEAE,
        pilot_region="West Bengal, India",
        growing_seasons=["Rabi (Winter / Post-Aman Relay / Utera)"],
        duration=DurationRange(
            min_days=95,
            max_days=115,
            typical_days=105,
        ),
        rooting_depth_class=RootingDepthClass.SHALLOW,
        water_requirement=WaterRequirement(
            demand_class=WaterDemandClass.LOW,
            min_mm=200.0,
            max_mm=300.0,
            critical_growth_stages=[
                "Branching (30-35 DAS)",
                "Pod development",
            ],
        ),
        soil_suitability=SoilSuitability(
            suitable_soil_types=[
                SoilType.LOAM,
                SoilType.CLAY_LOAM,
                SoilType.SILT_LOAM,
                SoilType.SANDY_LOAM,
            ],
            drainage_requirement="Well-drained; highly vulnerable to collar rot and root rot under standing water",
            min_ph=5.5,
            max_ph=8.0,
            optimal_min_ph=6.0,
            optimal_max_ph=7.5,
        ),
        temperature_requirement=TemperatureRequirement(
            min_temp_c=6.0,
            max_temp_c=30.0,
            optimal_min_temp_c=15.0,
            optimal_max_temp_c=22.0,
            gdd_base_temp_c=5.0,
            gdd_base_verified=True,
        ),
        nitrogen_management=NitrogenManagement(
            role=NitrogenRole.NITROGEN_FIXER,
            is_nitrogen_fixer=True,
            fixation_capacity_kg_ha="35-60 kg N/ha",
            residual_nitrogen_effect=(
                "Fixes 35-60 kg N/ha symbiotically via Rhizobium leguminosarum. Leaves 15-25 kg N/ha residual soil nitrogen, "
                "improving soil structure and reducing fertilizer requirements for succeeding cereals or oilseeds."
            ),
        ),
        references=[
            CropReference(
                institution="ICAR-Indian Institute of Pulses Research (IIPR)",
                publication="Lentil Production and Crop Improvement in Eastern India",
                details="Kanpur, Uttar Pradesh",
            ),
            CropReference(
                institution="Bidhan Chandra Krishi Viswavidyalaya (BCKV)",
                publication="Pulse Production Technologies in Gangetic Alluvial Soils",
                details="Department of Agronomy, Mohanpur, West Bengal",
            ),
        ],
        confidence_level=ConfidenceLevel.HIGH,
        unverified_fields=[],
    ),
    "mustard": Crop(
        crop_id="mustard",
        crop_name="Indian Mustard (Sarson / Rai)",
        scientific_name="Brassica juncea",
        botanical_family=BotanicalFamily.BRASSICACEAE,
        pilot_region="West Bengal, India",
        growing_seasons=["Rabi (Winter)"],
        duration=DurationRange(
            min_days=90,
            max_days=110,
            typical_days=100,
        ),
        rooting_depth_class=RootingDepthClass.MEDIUM,
        water_requirement=WaterRequirement(
            demand_class=WaterDemandClass.LOW,
            min_mm=240.0,
            max_mm=350.0,
            critical_growth_stages=[
                "Rosette / Flowering initiation (30-35 DAS)",
                "Siliqua (pod) development (55-60 DAS)",
            ],
        ),
        soil_suitability=SoilSuitability(
            suitable_soil_types=[
                SoilType.SANDY_LOAM,
                SoilType.LOAM,
                SoilType.CLAY_LOAM,
            ],
            drainage_requirement="Light to medium textured, well-drained soils; cannot tolerate water stagnation",
            min_ph=5.5,
            max_ph=8.0,
            optimal_min_ph=6.0,
            optimal_max_ph=7.2,
        ),
        temperature_requirement=TemperatureRequirement(
            min_temp_c=7.0,
            max_temp_c=28.0,
            optimal_min_temp_c=15.0,
            optimal_max_temp_c=22.0,
            gdd_base_temp_c=5.0,
            gdd_base_verified=True,
        ),
        nitrogen_management=NitrogenManagement(
            role=NitrogenRole.MODERATE_FEEDER,
            is_nitrogen_fixer=False,
            fixation_capacity_kg_ha=None,
            residual_nitrogen_effect=(
                "Requires moderate nitrogen (60-80 kg N/ha) and high sulfur (20-30 kg S/ha). "
                "Exerts beneficial bio-fumigation effect due to glucosinolate root exudates, "
                "suppressing soil-borne cereal pathogens and root-knot nematodes."
            ),
        ),
        references=[
            CropReference(
                institution="ICAR-Directorate of Rapeseed-Mustard Research (DRMR)",
                publication="Brassica Production Technologies in India",
                details="Bharatpur, Rajasthan",
            ),
            CropReference(
                institution="Bidhan Chandra Krishi Viswavidyalaya (BCKV)",
                publication="Oilseed Crops Production Practices for West Bengal",
                details="Mohanpur, West Bengal",
            ),
        ],
        confidence_level=ConfidenceLevel.HIGH,
        unverified_fields=[],
    ),
    "chickpea": Crop(
        crop_id="chickpea",
        crop_name="Chickpea (Bengal Gram / Chana)",
        scientific_name="Cicer arietinum",
        botanical_family=BotanicalFamily.FABACEAE,
        pilot_region="West Bengal, India",
        growing_seasons=["Rabi (Winter)"],
        duration=DurationRange(
            min_days=100,
            max_days=125,
            typical_days=110,
        ),
        rooting_depth_class=RootingDepthClass.DEEP,
        water_requirement=WaterRequirement(
            demand_class=WaterDemandClass.LOW,
            min_mm=200.0,
            max_mm=350.0,
            critical_growth_stages=[
                "Late branching",
                "Pod development",
            ],
        ),
        soil_suitability=SoilSuitability(
            suitable_soil_types=[
                SoilType.SANDY_LOAM,
                SoilType.LOAM,
                SoilType.CLAY_LOAM,
            ],
            drainage_requirement="Deep, porous, well-aerated soils; extremely intolerant of waterlogging and salinity",
            min_ph=6.0,
            max_ph=8.5,
            optimal_min_ph=6.5,
            optimal_max_ph=7.5,
        ),
        temperature_requirement=TemperatureRequirement(
            min_temp_c=8.0,
            max_temp_c=32.0,
            optimal_min_temp_c=18.0,
            optimal_max_temp_c=26.0,
            gdd_base_temp_c=8.0,
            gdd_base_verified=True,
        ),
        nitrogen_management=NitrogenManagement(
            role=NitrogenRole.NITROGEN_FIXER,
            is_nitrogen_fixer=True,
            fixation_capacity_kg_ha="40-80 kg N/ha",
            residual_nitrogen_effect=(
                "Symbiotically fixes 40-80 kg N/ha via Mesorhizobium ciceri. Deep taproots mobilize subsoil phosphorus "
                "through organic acid exudation (malic and citric acids). Leaves substantial residual fertility (20-40 kg N/ha)."
            ),
        ),
        references=[
            CropReference(
                institution="ICRISAT",
                publication="Chickpea Agronomy and Drought Tolerance Physiology",
                details="Patancheru, Hyderabad, India",
            ),
            CropReference(
                institution="ICAR-Indian Institute of Pulses Research (IIPR)",
                publication="Bengal Gram Cultivation in Eastern India",
                details="Kanpur, Uttar Pradesh",
            ),
        ],
        confidence_level=ConfidenceLevel.HIGH,
        unverified_fields=[],
    ),
    "green_gram": Crop(
        crop_id="green_gram",
        crop_name="Green Gram (Mung Bean / Moong)",
        scientific_name="Vigna radiata",
        botanical_family=BotanicalFamily.FABACEAE,
        pilot_region="West Bengal, India",
        growing_seasons=["Pre-Kharif / Summer (Zaid)", "Kharif"],
        duration=DurationRange(
            min_days=60,
            max_days=75,
            typical_days=65,
        ),
        rooting_depth_class=RootingDepthClass.SHALLOW,
        water_requirement=WaterRequirement(
            demand_class=WaterDemandClass.LOW,
            min_mm=200.0,
            max_mm=300.0,
            critical_growth_stages=[
                "Flowering (30-35 DAS)",
                "Pod filling (45-50 DAS)",
            ],
        ),
        soil_suitability=SoilSuitability(
            suitable_soil_types=[
                SoilType.SANDY_LOAM,
                SoilType.LOAM,
                SoilType.CLAY_LOAM,
            ],
            drainage_requirement="Well-drained fertile loam; sensitive to waterlogging",
            min_ph=5.5,
            max_ph=7.8,
            optimal_min_ph=6.2,
            optimal_max_ph=7.2,
        ),
        temperature_requirement=TemperatureRequirement(
            min_temp_c=18.0,
            max_temp_c=40.0,
            optimal_min_temp_c=25.0,
            optimal_max_temp_c=35.0,
            gdd_base_temp_c=10.0,
            gdd_base_verified=True,
        ),
        nitrogen_management=NitrogenManagement(
            role=NitrogenRole.NITROGEN_FIXER,
            is_nitrogen_fixer=True,
            fixation_capacity_kg_ha="30-50 kg N/ha",
            residual_nitrogen_effect=(
                "Fixes 30-50 kg N/ha in a short 65-day window via Bradyrhizobium. Highly valued as a summer catch crop "
                "or green manure in rice-based cropping systems, contributing 1.5-2 tonnes dry biomass/ha and saving 25% "
                "nitrogen in succeeding Aman rice."
            ),
        ),
        references=[
            CropReference(
                institution="ICAR-Indian Institute of Pulses Research (IIPR)",
                publication="Mungbean Production Technologies in Rice Fallows",
                details="Kanpur, Uttar Pradesh",
            ),
            CropReference(
                institution="Bidhan Chandra Krishi Viswavidyalaya (BCKV)",
                publication="Summer Pulse Cultivation in New Alluvial Zone of West Bengal",
                details="Mohanpur, West Bengal",
            ),
        ],
        confidence_level=ConfidenceLevel.HIGH,
        unverified_fields=[],
    ),
    "maize": Crop(
        crop_id="maize",
        crop_name="Maize (Corn)",
        scientific_name="Zea mays",
        botanical_family=BotanicalFamily.POACEAE,
        pilot_region="West Bengal, India",
        growing_seasons=["Rabi (Winter Maize)", "Kharif"],
        duration=DurationRange(
            min_days=100,
            max_days=130,
            typical_days=120,
        ),
        rooting_depth_class=RootingDepthClass.MEDIUM,
        water_requirement=WaterRequirement(
            demand_class=WaterDemandClass.MODERATE,
            min_mm=450.0,
            max_mm=650.0,
            critical_growth_stages=[
                "Knee-high vegetative stage",
                "Tasseling (male flowering)",
                "Silking (female flowering)",
                "Grain filling / Dough stage",
            ],
        ),
        soil_suitability=SoilSuitability(
            suitable_soil_types=[
                SoilType.LOAM,
                SoilType.SANDY_LOAM,
                SoilType.SILT_LOAM,
                SoilType.CLAY_LOAM,
            ],
            drainage_requirement="Deep, rich, well-drained soils; cannot tolerate water stagnation for more than 6-12 hours",
            min_ph=5.5,
            max_ph=8.0,
            optimal_min_ph=6.0,
            optimal_max_ph=7.2,
        ),
        temperature_requirement=TemperatureRequirement(
            min_temp_c=10.0,
            max_temp_c=38.0,
            optimal_min_temp_c=20.0,
            optimal_max_temp_c=30.0,
            gdd_base_temp_c=10.0,
            gdd_base_verified=True,
        ),
        nitrogen_management=NitrogenManagement(
            role=NitrogenRole.HEAVY_FEEDER,
            is_nitrogen_fixer=False,
            fixation_capacity_kg_ha=None,
            residual_nitrogen_effect=(
                "High photosynthetic efficiency C4 crop with heavy nitrogen demand (120-150 kg N/ha applied). "
                "Generates substantial root and stover biomass; must be rotated with legumes (Lentil, Chickpea, Mung) "
                "to prevent continuous nitrogen depletion."
            ),
        ),
        references=[
            CropReference(
                institution="ICAR-Indian Institute of Maize Research (IIMR)",
                publication="Rabi Maize Production Technologies for Eastern India",
                details="Ludhiana / Pusa Campus",
            ),
            CropReference(
                institution="Bidhan Chandra Krishi Viswavidyalaya (BCKV)",
                publication="Diversification of Rice-Based Systems with Rabi Maize in West Bengal",
                details="Department of Agronomy, Mohanpur, West Bengal",
            ),
            CropReference(
                institution="FAO",
                publication="Irrigation and Drainage Paper No. 56: Crop Water Requirements",
                details="Maize Evapotranspiration and Kc Stages",
            ),
        ],
        confidence_level=ConfidenceLevel.HIGH,
        unverified_fields=[],
    ),
}


class CropCatalogService:
    """Service providing access to verified crop agronomic parameters."""

    def __init__(self, catalog: Optional[Dict[str, Crop]] = None):
        self._catalog: Dict[str, Crop] = catalog or WEST_BENGAL_CROPS

    def get_crop(self, crop_id: str) -> Optional[Crop]:
        """Fetch an individual crop by its unique ID (case-insensitive)."""
        return self._catalog.get(crop_id.strip().lower())

    def get_all_crops(self) -> List[Crop]:
        """Retrieve all registered crops in the catalog."""
        return list(self._catalog.values())

    def filter_crops(
        self,
        family: Optional[str] = None,
        season: Optional[str] = None,
        nitrogen_role: Optional[str] = None,
        water_demand: Optional[str] = None,
    ) -> List[Crop]:
        """Filter crops by botanical family, growing season, nitrogen role, or water demand."""
        results = list(self._catalog.values())

        if family:
            results = [
                c for c in results if c.botanical_family.value.lower() == family.strip().lower()
            ]

        if season:
            season_clean = season.strip().lower()
            results = [
                c
                for c in results
                if any(season_clean in s.lower() for s in c.growing_seasons)
            ]

        if nitrogen_role:
            role_clean = nitrogen_role.strip().lower()
            results = [
                c for c in results if c.nitrogen_management.role.value.lower() == role_clean
            ]

        if water_demand:
            demand_clean = water_demand.strip().lower()
            results = [
                c
                for c in results
                if c.water_requirement.demand_class.value.lower() == demand_clean
            ]

        return results

    def get_provenance_statement(self) -> str:
        """Return scientific provenance and attribution statement."""
        return PROVENANCE_STATEMENT


crop_catalog_service = CropCatalogService()
