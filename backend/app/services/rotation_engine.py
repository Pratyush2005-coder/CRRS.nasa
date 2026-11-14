"""Crop Rotation Decision Support Engine (Phase 3B).

Provides deterministic, evidence-based crop rotation recommendations
using verified crop catalog data and NASA climate intelligence.

Scientific restrictions:
- No exact nitrogen gain calculations.
- No unsupported pest/disease predictions.
- No economic, yield or profit predictions.
- No invented planting dates.
- No unsupported irrigation assumptions.
- Clearly label heuristic scoring.
"""

from datetime import date, datetime, timezone
from typing import Dict, List, Optional, Set, Tuple, Any

from app.schemas.rotation import (
    NormalizedSeason,
    SeasonSlot,
    EvidenceLevel,
    RotationRule,
    StrategyType,
    IrrigationFeasibility,
    FallowReason,
    RuleEvidence,
    RuleEvaluation,
    CropSeasonFit,
    PlantedStep,
    FallowStep,
    SequenceStep,
    EvidenceReport,
    RotationStrategy,
    RotationRecommendation,
    RotationRequest,
    FarmRotationRequest,
    VERIFIED_SEASON_MAP,
    UNRESOLVED_SEASON_MAP,
    BORO_IRRIGATION_FEASIBILITY,
    BORO_OCCUPIED_SLOTS,
    SLOT_MONTH_RANGES,
    STRATEGY_TEMPLATES,
    RULE_WEIGHTS,
    THERMAL_SCORE_MAP,
    WATER_SCORE_MAP,
    is_planted,
    is_fallow,
    get_planted_steps,
)
from app.schemas.crop import (
    BotanicalFamily,
    NitrogenRole,
    RootingDepthClass,
    WaterDemandClass,
    SoilType,
    Crop,
)
from app.schemas.farm import IrrigationType
from app.schemas.climate_analyzer import (
    ThermalCompatibility,
    WaterCompatibility,
    ClimateIntelligenceReport,
)
from app.schemas.climate import ClimateResponse
from app.services.crop_catalog import CropCatalogService, crop_catalog_service
from app.services.climate_analyzer import ClimateAnalyzerService, climate_analyzer_service


# -------------------------------------------------------------------------
# Slot <-> NormalizedSeason Mapping
# -------------------------------------------------------------------------

SLOT_TO_NORMALIZED_SEASON: Dict[SeasonSlot, NormalizedSeason] = {
    SeasonSlot.Y1_AMAN: NormalizedSeason.AMAN,
    SeasonSlot.Y1_RABI: NormalizedSeason.RABI,
    SeasonSlot.Y1_SUMMER: NormalizedSeason.SUMMER,
    SeasonSlot.Y2_AMAN: NormalizedSeason.AMAN,
    SeasonSlot.Y2_RABI: NormalizedSeason.RABI,
    SeasonSlot.Y2_SUMMER: NormalizedSeason.SUMMER,
    SeasonSlot.Y3_AMAN: NormalizedSeason.AMAN,
    SeasonSlot.Y3_RABI: NormalizedSeason.RABI,
    SeasonSlot.Y3_SUMMER: NormalizedSeason.SUMMER,
    SeasonSlot.Y4_AMAN: NormalizedSeason.AMAN,
    SeasonSlot.Y4_RABI: NormalizedSeason.RABI,
    SeasonSlot.Y4_SUMMER: NormalizedSeason.SUMMER,
    SeasonSlot.Y5_AMAN: NormalizedSeason.AMAN,
    SeasonSlot.Y5_RABI: NormalizedSeason.RABI,
    SeasonSlot.Y5_SUMMER: NormalizedSeason.SUMMER,
}


def get_slot_year(slot: SeasonSlot) -> int:
    """Extract year number from slot (1-5)."""
    return int(slot.value[1])


def get_slots_for_years(max_years: int) -> List[SeasonSlot]:
    """Get ordered list of slots for the given number of years."""
    all_slots = list(SeasonSlot)
    return [s for s in all_slots if get_slot_year(s) <= max_years]


class RotationEngine:
    """Core rotation recommendation engine with dependency injection."""

    def __init__(
        self,
        crop_catalog: Optional[CropCatalogService] = None,
        climate_analyzer: Optional[ClimateAnalyzerService] = None,
    ) -> None:
        """Initialize engine with injected services.

        Args:
            crop_catalog: CropCatalogService instance (default: global singleton)
            climate_analyzer: ClimateAnalyzerService instance (default: global singleton)
        """
        self._crop_catalog = crop_catalog or crop_catalog_service
        self._climate_analyzer = climate_analyzer or climate_analyzer_service

    # ---------------------------------------------------------------------
    # Crop Catalog Access Helpers
    # ---------------------------------------------------------------------

    def get_crop(self, crop_id: str) -> Optional[Crop]:
        """Fetch a crop by ID from the catalog."""
        return self._crop_catalog.get_crop(crop_id)

    def get_all_crops(self) -> List[Crop]:
        """Return all crops in the catalog."""
        return self._crop_catalog.get_all_crops()

    def get_crops_by_season(self, season: NormalizedSeason) -> List[Crop]:
        """Return crops that have a verified mapping for the given normalized season."""
        crop_ids: List[str] = []
        for cid, seasons in VERIFIED_SEASON_MAP.items():
            if season in seasons:
                crop = self.get_crop(cid)
                if crop:
                    crop_ids.append(cid)
        return [self.get_crop(cid) for cid in crop_ids]

    def get_crop_season_fit(
        self,
        crop_id: str,
        season: NormalizedSeason,
        climate_report: ClimateIntelligenceReport,
    ) -> Optional[CropSeasonFit]:
        """Build a CropSeasonFit from catalog data and climate analyzer output."""
        crop = self.get_crop(crop_id)
        if not crop:
            return None

        # Verify this crop has a VERIFIED mapping for this season
        if season not in VERIFIED_SEASON_MAP.get(crop_id, set()):
            return None

        # Find climate suitability from analyzer report
        suitability = next(
            (s for s in climate_report.crop_suitability if s.crop_id == crop_id),
            None,
        )

        irrigation_required = (crop_id == "rice" and season == NormalizedSeason.BORO)

        if suitability is not None:
            # Climate suitability data available - VERIFIED evidence
            return CropSeasonFit(
                crop_id=crop.crop_id,
                crop_name=crop.crop_name,
                normalized_season=season,
                thermal_compatibility=suitability.thermal_compatibility,
                water_compatibility=suitability.water_compatibility,
                overall_climate_score=suitability.overall_climate_score,
                agronomic_caveats=suitability.agronomic_caveats,
                irrigation_required=irrigation_required,
                evidence_level=EvidenceLevel.VERIFIED,
            )
        else:
            # No climate suitability data for this crop - INSUFFICIENT_DATA
            # Use neutral scores that don't reward or penalize
            return CropSeasonFit(
                crop_id=crop.crop_id,
                crop_name=crop.crop_name,
                normalized_season=season,
                thermal_compatibility=ThermalCompatibility.MARGINAL,
                water_compatibility=WaterCompatibility.DEFICIT_RISK,
                overall_climate_score=None,
                agronomic_caveats=[
                    f"No climate suitability data available for {crop.crop_name} in {season.value} season. "
                    "Thermal and water compatibility defaulted to conservative estimates."
                ],
                irrigation_required=irrigation_required,
                evidence_level=EvidenceLevel.INSUFFICIENT_DATA,
            )

    def get_unresolved_seasons(self, crop_id: str) -> Set[NormalizedSeason]:
        """Return unresolved season mappings for a crop (for transparency)."""
        return UNRESOLVED_SEASON_MAP.get(crop_id, set())

    # ---------------------------------------------------------------------
    # Climate Suitability Helpers
    # ---------------------------------------------------------------------

    async def generate_climate_report(
        self,
        latitude: float,
        longitude: float,
        start_date: date,
        end_date: date,
        crop_id: Optional[str] = None,
    ) -> ClimateIntelligenceReport:
        """Generate or fetch climate intelligence report for a location and period."""
        return await self._climate_analyzer.generate_report(
            latitude=latitude,
            longitude=longitude,
            start_date=start_date,
            end_date=end_date,
            crop_id=crop_id,
        )

    def analyze_climate_response(
        self,
        climate_response: ClimateResponse,
        crop_id: Optional[str] = None,
    ) -> ClimateIntelligenceReport:
        """Analyze a pre-fetched climate response."""
        return self._climate_analyzer.analyze_climate_response(
            climate_response=climate_response,
            crop_id=crop_id,
        )

    # ---------------------------------------------------------------------
    # Input Validation Helpers
    # ---------------------------------------------------------------------

    def validate_rotation_request(self, request: RotationRequest) -> List[str]:
        """Validate a RotationRequest and return list of errors (empty if valid)."""
        errors: List[str] = []

        if request.max_cycle_years < 2 or request.max_cycle_years > 5:
            errors.append("max_cycle_years must be between 2 and 5")

        if request.soil_ph is not None and (request.soil_ph < 3.0 or request.soil_ph > 10.0):
            errors.append("soil_ph must be between 3.0 and 10.0")

        if request.organic_matter_pct is not None and (
            request.organic_matter_pct < 0.0 or request.organic_matter_pct > 100.0
        ):
            errors.append("organic_matter_pct must be between 0.0 and 100.0")

        # Validate excluded crops exist in catalog
        for crop_id in request.exclude_crops:
            if not self.get_crop(crop_id):
                errors.append(f"Excluded crop '{crop_id}' not found in catalog")

        # Validate previous crops exist in catalog
        for crop_id in request.previous_crops:
            if not self.get_crop(crop_id):
                errors.append(f"Previous crop '{crop_id}' not found in catalog")

        # Validate preferred start slot format
        if request.preferred_start_slot and not isinstance(
            request.preferred_start_slot, SeasonSlot
        ):
            errors.append("preferred_start_slot must be a valid SeasonSlot")

        return errors

    def validate_farm_rotation_request(self, request: FarmRotationRequest) -> List[str]:
        """Validate a FarmRotationRequest and return list of errors (empty if valid)."""
        errors: List[str] = []

        if request.max_cycle_years < 2 or request.max_cycle_years > 5:
            errors.append("max_cycle_years must be between 2 and 5")

        # Validate excluded crops exist in catalog
        for crop_id in request.exclude_crops:
            if not self.get_crop(crop_id):
                errors.append(f"Excluded crop '{crop_id}' not found in catalog")

        return errors

    # ---------------------------------------------------------------------
    # Boro Occupancy Helpers
    # ---------------------------------------------------------------------

    def get_boro_occupied_slots(self, planting_slot: SeasonSlot) -> Set[SeasonSlot]:
        """Return the set of slots occupied by Boro rice when planted in a RABI slot.

        Boro rice spans RABI + SUMMER slots of the same year.
        Only defined for RABI planting slots.
        """
        return BORO_OCCUPIED_SLOTS.get(planting_slot, set())

    def is_boro_planting_slot(self, slot: SeasonSlot) -> bool:
        """Check if a slot is a valid Boro rice planting slot (RABI slots only)."""
        return slot in BORO_OCCUPIED_SLOTS

    def get_occupied_slots_for_crop(
        self, crop_id: str, planting_slot: SeasonSlot
    ) -> Set[SeasonSlot]:
        """Return all slots occupied by a crop when planted in a given slot."""
        if crop_id == "rice" and SLOT_TO_NORMALIZED_SEASON.get(planting_slot) == NormalizedSeason.RABI:
            return self.get_boro_occupied_slots(planting_slot)
        return {planting_slot}

    # ---------------------------------------------------------------------
    # Irrigation Feasibility Helpers
    # ---------------------------------------------------------------------

    def get_boro_irrigation_feasibility(
        self, irrigation_type: IrrigationType
    ) -> IrrigationFeasibility:
        """Return Boro rice irrigation feasibility for a given irrigation type."""
        return BORO_IRRIGATION_FEASIBILITY.get(irrigation_type, IrrigationFeasibility.NOT_SUPPORTED)

    def get_irrigation_feasibility(
        self, crop_id: str, season: NormalizedSeason, irrigation_type: IrrigationType
    ) -> IrrigationFeasibility:
        """Return irrigation feasibility for a crop in a season given irrigation type."""
        if crop_id == "rice" and season == NormalizedSeason.BORO:
            return self.get_boro_irrigation_feasibility(irrigation_type)

        # For non-Boro crops, rainfed is generally feasible for most crops in their season
        # but we mark as REQUIRES_CONFIRMATION for non-rainfed irrigation types
        if irrigation_type == IrrigationType.RAINFED:
            return IrrigationFeasibility.SUPPORTED
        elif irrigation_type == IrrigationType.NONE:
            # No irrigation - depends on crop water demand and season rainfall
            # Heuristic: mark as REQUIRES_CONFIRMATION
            return IrrigationFeasibility.REQUIRES_CONFIRMATION
        else:
            return IrrigationFeasibility.REQUIRES_CONFIRMATION

    # ---------------------------------------------------------------------
    # Season Compatibility & Valid Crops per Slot
    # ---------------------------------------------------------------------

    def get_valid_crops_for_slot(
        self,
        slot: SeasonSlot,
        climate_report: ClimateIntelligenceReport,
        excluded_crops: Optional[Set[str]] = None,
        irrigation_type: Optional[IrrigationType] = None,
    ) -> List[Tuple[CropSeasonFit, Optional[IrrigationFeasibility]]]:
        """Return all valid crops for a given slot based on verified season mappings.

        Excludes unresolved mappings. Respects Boro occupancy.
        Returns tuples of (CropSeasonFit, irrigation_feasibility).
        """
        excluded = excluded_crops or set()
        season = SLOT_TO_NORMALIZED_SEASON.get(slot)
        if not season:
            return []

        valid_fits: List[Tuple[CropSeasonFit, Optional[IrrigationFeasibility]]] = []

        for crop_id in VERIFIED_SEASON_MAP:
            if crop_id in excluded:
                continue

            # Check if crop is valid for this slot
            crop_seasons = VERIFIED_SEASON_MAP[crop_id]
            is_valid = season in crop_seasons

            # Special case: Boro rice (rice with BORO season) is planted in RABI slots
            if not is_valid and season == NormalizedSeason.RABI and NormalizedSeason.BORO in crop_seasons:
                # Use BORO season for climate suitability lookup
                fit = self.get_crop_season_fit(crop_id, NormalizedSeason.BORO, climate_report)
                if fit:
                    feas = None
                    if irrigation_type:
                        feas = self.get_irrigation_feasibility(crop_id, NormalizedSeason.BORO, irrigation_type)
                    valid_fits.append((fit, feas))
                continue

            if not is_valid:
                continue

            fit = self.get_crop_season_fit(crop_id, season, climate_report)
            if fit:
                # Check irrigation feasibility
                feas = None
                if irrigation_type:
                    feas = self.get_irrigation_feasibility(crop_id, season, irrigation_type)
                valid_fits.append((fit, feas))

        return valid_fits

    def is_slot_available(
        self, slot: SeasonSlot, occupied_slots: Set[SeasonSlot]
    ) -> bool:
        """Check if a slot is available (not occupied by a multi-slot crop)."""
        return slot not in occupied_slots

    # ---------------------------------------------------------------------
    # Rotation Rule Evaluators
    # ---------------------------------------------------------------------

    def _evaluate_thermal_suitability(
        self,
        prev_step: Optional[SequenceStep],
        current_fit: CropSeasonFit,
        climate_report: ClimateIntelligenceReport,
    ) -> RuleEvaluation:
        """Evaluate thermal suitability rule."""
        thermal_comp = current_fit.thermal_compatibility
        score = THERMAL_SCORE_MAP.get(thermal_comp, 50.0)
        passed = score >= 75.0  # OPTIMAL or SUITABLE

        rationale = f"Thermal compatibility: {thermal_comp.value}. Score: {score:.0f}/100"
        if current_fit.agronomic_caveats:
            rationale += f". Caveats: {'; '.join(current_fit.agronomic_caveats)}"

        # Use evidence level from the fit (VERIFIED or INSUFFICIENT_DATA)
        evidence_level = current_fit.evidence_level

        return RuleEvaluation(
            rule=RotationRule.THERMAL_SUITABILITY,
            passed=passed,
            score=score,
            rationale=rationale,
            evidence=RuleEvidence(
                level=evidence_level,
                source="climate_analyzer" if evidence_level == EvidenceLevel.VERIFIED else "climate_analyzer_missing",
                citation=(
                    "NASA POWER MERRA-2, FAO-56 thermal thresholds"
                    if evidence_level == EvidenceLevel.VERIFIED
                    else "No climate suitability data available for this crop/season"
                ),
            ),
            caveats=current_fit.agronomic_caveats.copy(),
            data_gaps=(
                []
                if evidence_level == EvidenceLevel.VERIFIED
                else ["Crop-specific thermal suitability not available from climate analyzer"]
            ),
        )

    def _evaluate_water_suitability(
        self,
        prev_step: Optional[SequenceStep],
        current_fit: CropSeasonFit,
        climate_report: ClimateIntelligenceReport,
        irrigation_type: Optional[IrrigationType] = None,
    ) -> RuleEvaluation:
        """Evaluate water suitability rule."""
        water_comp = current_fit.water_compatibility
        score = WATER_SCORE_MAP.get(water_comp, 50.0)
        passed = score >= 60.0  # OPTIMAL or DEFICIT_RISK (manageable)

        rationale = f"Water compatibility: {water_comp.value}. Score: {score:.0f}/100"
        if current_fit.agronomic_caveats:
            rationale += f". Caveats: {'; '.join(current_fit.agronomic_caveats)}"

        # Use evidence level from the fit (propagated from climate analyzer)
        evidence_level = current_fit.evidence_level
        if irrigation_type and current_fit.irrigation_required:
            feas = self.get_irrigation_feasibility(
                current_fit.crop_id, current_fit.normalized_season, irrigation_type
            )
            if feas == IrrigationFeasibility.REQUIRES_CONFIRMATION:
                evidence_level = EvidenceLevel.HEURISTIC
                rationale += ". Irrigation feasibility requires local confirmation."

        data_gaps = []
        if evidence_level == EvidenceLevel.INSUFFICIENT_DATA:
            data_gaps.append("Crop-specific water suitability not available from climate analyzer")

        # Determine source based on evidence level (consistent with thermal evaluator)
        source = (
            "climate_analyzer_missing"
            if evidence_level == EvidenceLevel.INSUFFICIENT_DATA
            else "climate_analyzer"
        )

        return RuleEvaluation(
            rule=RotationRule.WATER_SUITABILITY,
            passed=passed,
            score=score,
            rationale=rationale,
            evidence=RuleEvidence(
                level=evidence_level,
                source=source,
                citation="NASA POWER precipitation, FAO-56 crop water requirements",
            ),
            caveats=current_fit.agronomic_caveats.copy(),
            data_gaps=data_gaps,
        )

    def _evaluate_family_diversification(
        self,
        prev_step: Optional[SequenceStep],
        current_fit: CropSeasonFit,
    ) -> RuleEvaluation:
        """Evaluate botanical family diversification rule."""
        if not prev_step or is_fallow(prev_step):
            # No previous crop to compare - neutral score
            return RuleEvaluation(
                rule=RotationRule.BOTANICAL_FAMILY_DIVERSIFICATION,
                passed=True,
                score=75.0,
                rationale="No previous crop in sequence; family diversification not applicable.",
                evidence=RuleEvidence(
                    level=EvidenceLevel.HEURISTIC,
                    source="agronomic_heuristic",
                    citation="Standard rotation principle: alternate botanical families",
                ),
                caveats=["Heuristic principle; does not guarantee pest/disease prevention."],
                data_gaps=["Regional pathogen pressure data not available."],
            )

        current_crop = self.get_crop(current_fit.crop_id)
        if not current_crop:
            return RuleEvaluation(
                rule=RotationRule.BOTANICAL_FAMILY_DIVERSIFICATION,
                passed=False,
                score=0.0,
                rationale="Current crop not found in catalog.",
                evidence=RuleEvidence(
                    level=EvidenceLevel.INSUFFICIENT_DATA,
                    source="crop_catalog",
                ),
            )

        current_family = current_crop.botanical_family
        prev_crop = self.get_crop(prev_step.crop_id)
        if not prev_crop:
            return RuleEvaluation(
                rule=RotationRule.BOTANICAL_FAMILY_DIVERSIFICATION,
                passed=True,
                score=75.0,
                rationale="Previous crop not in catalog; cannot verify family change.",
                evidence=RuleEvidence(
                    level=EvidenceLevel.INSUFFICIENT_DATA,
                    source="crop_catalog",
                ),
            )

        prev_family = prev_crop.botanical_family
        passed = current_family != prev_family
        score = 100.0 if passed else 40.0

        rationale = (
            f"Family transition: {prev_family.value} -> {current_family.value}. "
            f"{'Different families (diversified).' if passed else 'Same family (not diversified).'}"
        )

        return RuleEvaluation(
            rule=RotationRule.BOTANICAL_FAMILY_DIVERSIFICATION,
            passed=passed,
            score=score,
            rationale=rationale,
            evidence=RuleEvidence(
                level=EvidenceLevel.HEURISTIC,
                source="agronomic_heuristic",
                citation="ICAR/BCKV rotation principles; no verified regional pathogen data",
            ),
            caveats=[
                "Heuristic principle; does not guarantee pest/disease prevention.",
                "No verified regional pathogen pressure data available.",
            ],
            data_gaps=["Regional pathogen pressure data not available."],
        )

    def _evaluate_nitrogen_sequence(
        self,
        prev_step: Optional[SequenceStep],
        current_fit: CropSeasonFit,
    ) -> RuleEvaluation:
        """Evaluate nitrogen role sequencing rule.

        Qualitative only: prefers nitrogen_fixer -> heavy_feeder transitions.
        No quantitative N balance calculations.
        """
        current_crop = self.get_crop(current_fit.crop_id)
        if not current_crop:
            return RuleEvaluation(
                rule=RotationRule.NITROGEN_ROLE_SEQUENCE,
                passed=False,
                score=0.0,
                rationale="Current crop not found in catalog.",
                evidence=RuleEvidence(
                    level=EvidenceLevel.INSUFFICIENT_DATA,
                    source="crop_catalog",
                ),
            )

        current_role = current_crop.nitrogen_management.role

        if not prev_step or is_fallow(prev_step):
            # No previous crop - neutral
            return RuleEvaluation(
                rule=RotationRule.NITROGEN_ROLE_SEQUENCE,
                passed=True,
                score=75.0,
                rationale=f"No previous crop. Current crop nitrogen role: {current_role.value}.",
                evidence=RuleEvidence(
                    level=EvidenceLevel.HEURISTIC,
                    source="agronomic_heuristic",
                    citation="Qualitative nitrogen role sequencing principle",
                ),
                caveats=[
                    "Qualitative only; no quantitative N balance calculated.",
                    "Does not account for residual N from previous seasons.",
                ],
                data_gaps=["Soil nitrogen test data not available."],
            )

        prev_crop = self.get_crop(prev_step.crop_id)
        if not prev_crop:
            return RuleEvaluation(
                rule=RotationRule.NITROGEN_ROLE_SEQUENCE,
                passed=True,
                score=75.0,
                rationale="Previous crop not in catalog; cannot evaluate N sequence.",
                evidence=RuleEvidence(
                    level=EvidenceLevel.INSUFFICIENT_DATA,
                    source="crop_catalog",
                ),
            )

        prev_role = prev_crop.nitrogen_management.role

        # Preferred transitions: fixer -> feeder, fixer -> moderate, moderate -> feeder
        preferred = False
        if prev_role == NitrogenRole.NITROGEN_FIXER and current_role in (
            NitrogenRole.HEAVY_FEEDER,
            NitrogenRole.MODERATE_FEEDER,
        ):
            preferred = True
        elif prev_role == NitrogenRole.MODERATE_FEEDER and current_role == NitrogenRole.HEAVY_FEEDER:
            preferred = True

        score = 100.0 if preferred else 60.0
        passed = preferred

        rationale = (
            f"Nitrogen role transition: {prev_role.value} -> {current_role.value}. "
            f"{'Preferred sequence (fixer/moderate -> feeder).' if preferred else 'Suboptimal sequence.'}"
        )

        return RuleEvaluation(
            rule=RotationRule.NITROGEN_ROLE_SEQUENCE,
            passed=passed,
            score=score,
            rationale=rationale,
            evidence=RuleEvidence(
                level=EvidenceLevel.HEURISTIC,
                source="agronomic_heuristic",
                citation="Qualitative nitrogen role principle; no field-validated N balance",
            ),
            caveats=[
                "Qualitative only; no quantitative N gain/loss calculated.",
                "Does not account for fertilizer application rates.",
                "Residual N effect varies by soil type and management.",
            ],
            data_gaps=["Soil nitrogen test data not available."],
        )

    def _evaluate_root_depth_alternation(
        self,
        prev_step: Optional[SequenceStep],
        current_fit: CropSeasonFit,
    ) -> RuleEvaluation:
        """Evaluate root depth alternation rule."""
        current_crop = self.get_crop(current_fit.crop_id)
        if not current_crop:
            return RuleEvaluation(
                rule=RotationRule.ROOT_DEPTH_ALTERNATION,
                passed=False,
                score=0.0,
                rationale="Current crop not found in catalog.",
                evidence=RuleEvidence(
                    level=EvidenceLevel.INSUFFICIENT_DATA,
                    source="crop_catalog",
                ),
            )

        current_depth = current_crop.rooting_depth_class

        if not prev_step or is_fallow(prev_step):
            return RuleEvaluation(
                rule=RotationRule.ROOT_DEPTH_ALTERNATION,
                passed=True,
                score=75.0,
                rationale=f"No previous crop. Current root depth: {current_depth.value}.",
                evidence=RuleEvidence(
                    level=EvidenceLevel.HEURISTIC,
                    source="agronomic_heuristic",
                    citation="Root depth alternation principle for soil resource partitioning",
                ),
                caveats=["Heuristic principle; soil profile data not available."],
                data_gaps=["Field-level soil profile data not available."],
            )

        prev_crop = self.get_crop(prev_step.crop_id)
        if not prev_crop:
            return RuleEvaluation(
                rule=RotationRule.ROOT_DEPTH_ALTERNATION,
                passed=True,
                score=75.0,
                rationale="Previous crop not in catalog; cannot evaluate root depth alternation.",
                evidence=RuleEvidence(
                    level=EvidenceLevel.INSUFFICIENT_DATA,
                    source="crop_catalog",
                ),
            )

        prev_depth = prev_crop.rooting_depth_class
        passed = current_depth != prev_depth
        score = 100.0 if passed else 60.0

        rationale = (
            f"Root depth transition: {prev_depth.value} -> {current_depth.value}. "
            f"{'Alternated (different depth classes).' if passed else 'Same depth class (no alternation).'}"
        )

        return RuleEvaluation(
            rule=RotationRule.ROOT_DEPTH_ALTERNATION,
            passed=passed,
            score=score,
            rationale=rationale,
            evidence=RuleEvidence(
                level=EvidenceLevel.HEURISTIC,
                source="agronomic_heuristic",
                citation="Root depth alternation principle; no verified regional soil profile data",
            ),
            caveats=["Heuristic principle; soil profile data not available."],
            data_gaps=["Field-level soil profile data not available."],
        )

    def _evaluate_irrigation_feasibility(
        self,
        prev_step: Optional[SequenceStep],
        current_fit: CropSeasonFit,
        irrigation_type: Optional[IrrigationType],
    ) -> RuleEvaluation:
        """Evaluate irrigation feasibility rule."""
        if not irrigation_type:
            return RuleEvaluation(
                rule=RotationRule.IRRIGATION_FEASIBILITY,
                passed=True,
                score=75.0,
                rationale="No irrigation type specified; cannot evaluate feasibility.",
                evidence=RuleEvidence(
                    level=EvidenceLevel.INSUFFICIENT_DATA,
                    source="farm_profile",
                ),
                data_gaps=["Farm irrigation type not provided."],
            )

        # Compute feasibility from crop_id, season, and irrigation_type
        feasibility = self.get_irrigation_feasibility(
            current_fit.crop_id, current_fit.normalized_season, irrigation_type
        )

        if feasibility == IrrigationFeasibility.SUPPORTED:
            score = 100.0
            passed = True
            rationale = f"Irrigation type {irrigation_type.value} supports this crop."
        elif feasibility == IrrigationFeasibility.REQUIRES_CONFIRMATION:
            score = 60.0
            passed = True  # Not a hard failure, but needs confirmation
            rationale = (
                f"Irrigation type {irrigation_type.value} may support this crop; "
                "local confirmation required."
            )
        else:  # NOT_SUPPORTED
            score = 20.0
            passed = False
            rationale = (
                f"Irrigation type {irrigation_type.value} does not support this crop's "
                "water requirements."
            )

        return RuleEvaluation(
            rule=RotationRule.IRRIGATION_FEASIBILITY,
            passed=passed,
            score=score,
            rationale=rationale,
            evidence=RuleEvidence(
                level=EvidenceLevel.VERIFIED if feasibility == IrrigationFeasibility.SUPPORTED else EvidenceLevel.HEURISTIC,
                source="farm_profile",
                citation="Irrigation feasibility per crop water demand and irrigation method",
            ),
            caveats=[
                "Boro rice feasibility based on West Bengal canal irrigation evidence.",
                "Drip/sprinkler/flood feasibility requires local confirmation.",
            ],
            data_gaps=["Field-level irrigation infrastructure not verified."],
        )

    def evaluate_all_rules(
        self,
        prev_step: Optional[SequenceStep],
        current_fit: CropSeasonFit,
        climate_report: ClimateIntelligenceReport,
        irrigation_type: Optional[IrrigationType] = None,
    ) -> List[RuleEvaluation]:
        """Evaluate all six rotation rules for a crop transition."""
        return [
            self._evaluate_thermal_suitability(prev_step, current_fit, climate_report),
            self._evaluate_water_suitability(prev_step, current_fit, climate_report, irrigation_type),
            self._evaluate_family_diversification(prev_step, current_fit),
            self._evaluate_nitrogen_sequence(prev_step, current_fit),
            self._evaluate_root_depth_alternation(prev_step, current_fit),
            self._evaluate_irrigation_feasibility(prev_step, current_fit, irrigation_type),
        ]

    # ---------------------------------------------------------------------
    # Sequence Generation (Backtracking)
    # ---------------------------------------------------------------------

    def _generate_sequences_recursive(
        self,
        slots: List[SeasonSlot],
        index: int,
        occupied_slots: Set[SeasonSlot],
        current_sequence: List[SequenceStep],
        valid_crops_per_slot: Dict[SeasonSlot, List[Tuple[CropSeasonFit, Optional[IrrigationFeasibility]]]],
        climate_report: ClimateIntelligenceReport,
        irrigation_type: Optional[IrrigationType],
        all_sequences: List[List[SequenceStep]],
        max_sequences: int,
        previous_crop_id: Optional[str] = None,
    ) -> None:
        """Recursive backtracking to generate valid sequences."""
        if len(all_sequences) >= max_sequences:
            return

        if index >= len(slots):
            all_sequences.append(current_sequence.copy())
            return

        slot = slots[index]

        # Skip if slot is already occupied (e.g., by Boro rice spanning into SUMMER)
        if slot in occupied_slots:
            # Add a fallow step for the occupied slot
            fallow_step = FallowStep(
                slot=slot,
                reason=FallowReason.NO_VALID_CROP,
            )
            current_sequence.append(fallow_step)
            self._generate_sequences_recursive(
                slots, index + 1, occupied_slots, current_sequence,
                valid_crops_per_slot, climate_report, irrigation_type,
                all_sequences, max_sequences, previous_crop_id
            )
            current_sequence.pop()
            return

        # Get valid crops for this slot
        valid_fits = valid_crops_per_slot.get(slot, [])

        if not valid_fits:
            # No valid crops - add fallow step
            fallow_step = FallowStep(slot=slot, reason=FallowReason.NO_VALID_CROP)
            current_sequence.append(fallow_step)
            self._generate_sequences_recursive(
                slots, index + 1, occupied_slots, current_sequence,
                valid_crops_per_slot, climate_report, irrigation_type,
                all_sequences, max_sequences, previous_crop_id
            )
            current_sequence.pop()
            return

        # Try each valid crop
        for fit, feas in valid_fits:
            # Check if this crop would create occupancy conflicts
            new_occupied = set(occupied_slots)
            crop_occupied = self.get_occupied_slots_for_crop(fit.crop_id, slot)
            conflict = False
            for occ_slot in crop_occupied:
                if occ_slot in new_occupied and occ_slot != slot:
                    conflict = True
                    break
            if conflict:
                continue

            new_occupied.update(crop_occupied)

            # Build PlantedStep with rule evaluations
            prev_step = current_sequence[-1] if current_sequence else None
            rule_evals = self.evaluate_all_rules(
                prev_step, fit, climate_report, irrigation_type
            )

            # Get crop details for PlantedStep
            crop = self.get_crop(fit.crop_id)
            if not crop:
                continue

            planted_step = PlantedStep(
                slot=slot,
                crop_id=fit.crop_id,
                crop_name=fit.crop_name,
                normalized_season=fit.normalized_season,
                duration_typical_days=crop.duration.typical_days,
                botanical_family=crop.botanical_family,
                nitrogen_role=crop.nitrogen_management.role,
                root_depth_class=crop.rooting_depth_class,
                water_demand_class=crop.water_requirement.demand_class,
                thermal_compatibility=fit.thermal_compatibility,
                water_compatibility=fit.water_compatibility,
                overall_climate_score=fit.overall_climate_score,
                agronomic_caveats=fit.agronomic_caveats,
                irrigation_feasibility=feas or IrrigationFeasibility.REQUIRES_CONFIRMATION,
                rule_evaluations=rule_evals,
            )

            current_sequence.append(planted_step)
            self._generate_sequences_recursive(
                slots, index + 1, new_occupied, current_sequence,
                valid_crops_per_slot, climate_report, irrigation_type,
                all_sequences, max_sequences, fit.crop_id
            )
            current_sequence.pop()

        # Also try fallow for this slot
        fallow_step = FallowStep(slot=slot, reason=FallowReason.NO_VALID_CROP)
        current_sequence.append(fallow_step)
        self._generate_sequences_recursive(
            slots, index + 1, occupied_slots, current_sequence,
            valid_crops_per_slot, climate_report, irrigation_type,
            all_sequences, max_sequences, previous_crop_id
        )
        current_sequence.pop()

    def generate_sequences(
        self,
        climate_report: ClimateIntelligenceReport,
        max_cycle_years: int,
        excluded_crops: Optional[Set[str]] = None,
        irrigation_type: Optional[IrrigationType] = None,
        preferred_start_slot: Optional[SeasonSlot] = None,
        previous_crops: Optional[List[str]] = None,
    ) -> List[List[SequenceStep]]:
        """Generate valid crop sequences using backtracking.

        Returns up to 10 deterministic sequences.
        """
        excluded = excluded_crops or set()
        prev_crops = previous_crops or []

        # Determine slots to fill
        all_slots = get_slots_for_years(max_cycle_years)

        # Determine start index
        start_index = 0
        if preferred_start_slot:
            try:
                start_index = all_slots.index(preferred_start_slot)
            except ValueError:
                start_index = 0

        slots_to_fill = all_slots[start_index:]

        # Pre-compute valid crops for each slot
        valid_crops_per_slot: Dict[SeasonSlot, List[Tuple[CropSeasonFit, Optional[IrrigationFeasibility]]]] = {}
        for slot in slots_to_fill:
            valid_crops_per_slot[slot] = self.get_valid_crops_for_slot(
                slot, climate_report, excluded, irrigation_type
            )

        # Sort crops deterministically for reproducible output
        for slot in valid_crops_per_slot:
            valid_crops_per_slot[slot].sort(key=lambda t: t[0].crop_id)

        all_sequences: List[List[SequenceStep]] = []
        initial_occupied: Set[SeasonSlot] = set()

        self._generate_sequences_recursive(
            slots_to_fill,
            0,
            initial_occupied,
            [],
            valid_crops_per_slot,
            climate_report,
            irrigation_type,
            all_sequences,
            max_sequences=10,
        )

        return all_sequences

    # ---------------------------------------------------------------------
    # Scoring
    # ---------------------------------------------------------------------

    def score_sequence(
        self,
        sequence: List[SequenceStep],
        strategy_type: StrategyType,
    ) -> Dict[str, float]:
        """Score a sequence according to a strategy type.

        Returns dict with sub-scores and composite score.
        """
        planted_steps = get_planted_steps(sequence)
        if not planted_steps:
            return {
                "thermal_suitability_score": 0.0,
                "water_suitability_score": 0.0,
                "family_diversification_score": 0.0,
                "nitrogen_sequence_score": 0.0,
                "root_depth_score": 0.0,
                "irrigation_feasibility_score": 0.0,
                "composite_score": 0.0,
            }

        # Collect rule scores per rule
        rule_scores: Dict[RotationRule, List[float]] = {r: [] for r in RotationRule}

        for step in planted_steps:
            for eval_ in step.rule_evaluations:
                rule_scores[eval_.rule].append(eval_.score)

        # Average scores per rule
        avg_scores = {}
        for rule, scores in rule_scores.items():
            avg_scores[rule] = sum(scores) / len(scores) if scores else 0.0

        # Strategy-specific weights (modify base RULE_WEIGHTS)
        weights = dict(RULE_WEIGHTS)

        if strategy_type == StrategyType.NITROGEN_SEQUENCE:
            weights[RotationRule.NITROGEN_ROLE_SEQUENCE] = 0.40
            weights[RotationRule.THERMAL_SUITABILITY] = 0.15
            weights[RotationRule.WATER_SUITABILITY] = 0.15
            weights[RotationRule.BOTANICAL_FAMILY_DIVERSIFICATION] = 0.10
            weights[RotationRule.ROOT_DEPTH_ALTERNATION] = 0.10
            weights[RotationRule.IRRIGATION_FEASIBILITY] = 0.10
        elif strategy_type == StrategyType.WATER_ALIGNED:
            weights[RotationRule.WATER_SUITABILITY] = 0.40
            weights[RotationRule.THERMAL_SUITABILITY] = 0.20
            weights[RotationRule.IRRIGATION_FEASIBILITY] = 0.15
            weights[RotationRule.NITROGEN_ROLE_SEQUENCE] = 0.10
            weights[RotationRule.BOTANICAL_FAMILY_DIVERSIFICATION] = 0.10
            weights[RotationRule.ROOT_DEPTH_ALTERNATION] = 0.05
        elif strategy_type == StrategyType.FAMILY_DIVERSIFICATION:
            weights[RotationRule.BOTANICAL_FAMILY_DIVERSIFICATION] = 0.40
            weights[RotationRule.NITROGEN_ROLE_SEQUENCE] = 0.20
            weights[RotationRule.ROOT_DEPTH_ALTERNATION] = 0.15
            weights[RotationRule.THERMAL_SUITABILITY] = 0.10
            weights[RotationRule.WATER_SUITABILITY] = 0.10
            weights[RotationRule.IRRIGATION_FEASIBILITY] = 0.05
        # COMPOSITE uses base RULE_WEIGHTS

        # Calculate composite
        composite = sum(avg_scores.get(rule, 0.0) * weight for rule, weight in weights.items())

        return {
            "thermal_suitability_score": round(avg_scores.get(RotationRule.THERMAL_SUITABILITY, 0.0), 1),
            "water_suitability_score": round(avg_scores.get(RotationRule.WATER_SUITABILITY, 0.0), 1),
            "family_diversification_score": round(avg_scores.get(RotationRule.BOTANICAL_FAMILY_DIVERSIFICATION, 0.0), 1),
            "nitrogen_sequence_score": round(avg_scores.get(RotationRule.NITROGEN_ROLE_SEQUENCE, 0.0), 1),
            "root_depth_score": round(avg_scores.get(RotationRule.ROOT_DEPTH_ALTERNATION, 0.0), 1),
            "irrigation_feasibility_score": round(avg_scores.get(RotationRule.IRRIGATION_FEASIBILITY, 0.0), 1),
            "composite_score": round(composite, 1),
        }

    # ---------------------------------------------------------------------
    # Evidence Reporting
    # ---------------------------------------------------------------------

    def build_evidence_report(
        self, sequence: List[SequenceStep]
    ) -> EvidenceReport:
        """Build evidence report for a sequence."""
        counts: Dict[str, Dict[EvidenceLevel, int]] = {
            rule.value: {level: 0 for level in EvidenceLevel}
            for rule in RotationRule
        }

        limitations: List[str] = []
        data_gaps: List[str] = []

        planted_steps = get_planted_steps(sequence)
        total_evals = 0
        verified_evals = 0

        for step in planted_steps:
            for eval_ in step.rule_evaluations:
                total_evals += 1
                rule_name = eval_.rule.value
                level = eval_.evidence.level
                counts[rule_name][level] += 1

                if level == EvidenceLevel.VERIFIED:
                    verified_evals += 1

                limitations.extend(eval_.caveats)
                data_gaps.extend(eval_.data_gaps)

        # Deduplicate
        limitations = list(dict.fromkeys(limitations))
        data_gaps = list(dict.fromkeys(data_gaps))

        # Add global limitations
        limitations.extend([
            "Rotation rules are heuristic principles; not field-validated for this region.",
            "Boro rice climate evaluation uses single-year proxy data.",
            "Multi-year climate normals not modeled.",
            "Relay planting (Utera) not modeled.",
        ])

        data_gaps.extend([
            "Field-level soil test data (N, P, K, pH, EC) not available.",
            "Regional pest/disease pressure data not available.",
            "Farm-specific irrigation infrastructure not verified.",
            "Multi-year climate normals not available.",
        ])

        verified_coverage = (verified_evals / total_evals * 100) if total_evals > 0 else 0.0

        return EvidenceReport(
            counts=counts,
            verified_coverage_pct=round(verified_coverage, 1),
            limitations=limitations,
            data_gaps=data_gaps,
        )

    # ---------------------------------------------------------------------
    # Strategy Generation
    # ---------------------------------------------------------------------

    def _build_strategy(
        self,
        strategy_type: StrategyType,
        sequence: List[SequenceStep],
        total_years: int,
    ) -> RotationStrategy:
        """Build a RotationStrategy from a sequence and strategy type."""
        planted_steps = get_planted_steps(sequence)
        fallow_steps = [s for s in sequence if is_fallow(s)]

        scores = self.score_sequence(sequence, strategy_type)
        evidence_report = self.build_evidence_report(sequence)

        # Determine overall evidence level
        evidence_levels = [step.rule_evaluations[0].evidence.level for step in planted_steps if step.rule_evaluations]
        # Simplified: if any heuristic, overall is heuristic
        if any(l == EvidenceLevel.HEURISTIC for l in evidence_levels):
            overall_evidence = EvidenceLevel.HEURISTIC
        elif any(l == EvidenceLevel.INSUFFICIENT_DATA for l in evidence_levels):
            overall_evidence = EvidenceLevel.INSUFFICIENT_DATA
        else:
            overall_evidence = EvidenceLevel.VERIFIED

        template = STRATEGY_TEMPLATES[strategy_type]

        return RotationStrategy(
            strategy_type=strategy_type,
            name=template["name"],
            description=template["description"],
            evidence_level=overall_evidence,
            sequence=sequence,
            total_years=total_years,
            planted_count=len(planted_steps),
            fallow_count=len(fallow_steps),
            thermal_suitability_score=scores["thermal_suitability_score"],
            water_suitability_score=scores["water_suitability_score"],
            family_diversification_score=scores["family_diversification_score"],
            nitrogen_sequence_score=scores["nitrogen_sequence_score"],
            root_depth_score=scores["root_depth_score"],
            irrigation_feasibility_score=scores["irrigation_feasibility_score"],
            composite_score=scores["composite_score"],
            evidence_report=evidence_report,
        )

    def generate_strategies(
        self,
        sequences: List[List[SequenceStep]],
        max_cycle_years: int,
    ) -> List[RotationStrategy]:
        """Generate all four strategy variants from candidate sequences."""
        all_strategies: List[RotationStrategy] = []

        for strategy_type in StrategyType:
            # Score all sequences for this strategy
            scored = [(seq, self.score_sequence(seq, strategy_type)["composite_score"]) for seq in sequences]
            if not scored:
                continue

            # Sort by composite score descending (deterministic tie-break by sequence string)
            scored.sort(key=lambda x: (-x[1], str(x[0])))

            # Take top sequence for this strategy
            best_sequence = scored[0][0]
            strategy = self._build_strategy(strategy_type, best_sequence, max_cycle_years)
            all_strategies.append(strategy)

        return all_strategies

    # ---------------------------------------------------------------------
    # Main Entry Point
    # ---------------------------------------------------------------------

    async def generate_recommendation(
        self,
        request: RotationRequest,
        climate_report: Optional[ClimateIntelligenceReport] = None,
    ) -> RotationRecommendation:
        """Generate a complete rotation recommendation from a request."""
        # Validate request
        errors = self.validate_rotation_request(request)
        if errors:
            raise ValueError(f"Invalid request: {'; '.join(errors)}")

        # Generate climate report if not provided
        if climate_report is None:
            # Default to last 3 full years
            end_year = date.today().year - 1
            start_year = end_year - 2
            start_date = date(start_year, 1, 1)
            end_date = date(end_year, 12, 31)
            climate_report = await self.generate_climate_report(
                latitude=request.latitude,
                longitude=request.longitude,
                start_date=start_date,
                end_date=end_date,
            )

        # Generate sequences
        sequences = self.generate_sequences(
            climate_report=climate_report,
            max_cycle_years=request.max_cycle_years,
            excluded_crops=set(request.exclude_crops),
            irrigation_type=request.irrigation_type,
            preferred_start_slot=request.preferred_start_slot,
            previous_crops=request.previous_crops,
        )

        if not sequences:
            raise ValueError("No valid sequences could be generated.")

        # Generate strategies
        strategies = self.generate_strategies(sequences, request.max_cycle_years)

        # Select primary strategy (highest composite score)
        primary = max(strategies, key=lambda s: s.composite_score)

        # Build climate summary
        climate_summary = {
            "period_days": climate_report.date_range_days,
            "data_completeness": climate_report.missing_data.completeness_category.value,
            "total_rainfall_mm": climate_report.rainfall_analysis.total_rainfall_mm,
            "mean_temperature_c": climate_report.temperature_analysis.mean_temperature_c,
            "heat_risk_level": climate_report.heat_risk.heat_risk_level.value,
            "cold_risk_level": climate_report.cold_risk.frost_hazard_level.value,
        }

        from datetime import datetime
        return RotationRecommendation(
            farm_id=request.farm_id,
            latitude=request.latitude,
            longitude=request.longitude,
            analysis_date=date.today(),
            climate_summary=climate_summary,
            strategies=strategies,
            primary_strategy=primary,
            generated_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            engine_version="1.0.0",
        )

    def generate_recommendation_from_farm(
        self,
        request: FarmRotationRequest,
        farm_profile: Any,  # FarmResponse type
        climate_report: Optional[ClimateIntelligenceReport] = None,
    ) -> RotationRecommendation:
        """Generate recommendation using an existing farm profile."""
        # Convert farm profile to RotationRequest
        # Note: FarmResponse uses 'previous_crops' field (not 'crop_history')
        previous_crops = []
        if hasattr(farm_profile, 'previous_crops') and farm_profile.previous_crops:
            previous_crops = [
                h.crop_name.lower().replace(" ", "_").replace("-", "_")
                for h in farm_profile.previous_crops
            ]

        rot_request = RotationRequest(
            latitude=farm_profile.latitude,
            longitude=farm_profile.longitude,
            farm_id=request.farm_id,
            soil_type=farm_profile.soil_type,
            soil_ph=farm_profile.soil_ph,
            organic_matter_pct=farm_profile.organic_matter_pct,
            irrigation_type=farm_profile.primary_irrigation,
            previous_crops=previous_crops,
            max_cycle_years=request.max_cycle_years,
            exclude_crops=request.exclude_crops,
        )

        # This is sync version - in practice would need async
        # For now, we'll require climate_report to be passed
        if climate_report is None:
            raise ValueError("climate_report must be provided for sync farm-based recommendation")

        sequences = self.generate_sequences(
            climate_report=climate_report,
            max_cycle_years=request.max_cycle_years,
            excluded_crops=set(request.exclude_crops),
            irrigation_type=farm_profile.primary_irrigation,
            previous_crops=rot_request.previous_crops,
        )

        if not sequences:
            raise ValueError("No valid sequences could be generated.")

        strategies = self.generate_strategies(sequences, request.max_cycle_years)
        primary = max(strategies, key=lambda s: s.composite_score)

        climate_summary = {
            "period_days": climate_report.date_range_days,
            "data_completeness": climate_report.missing_data.completeness_category.value,
            "total_rainfall_mm": climate_report.rainfall_analysis.total_rainfall_mm,
            "mean_temperature_c": climate_report.temperature_analysis.mean_temperature_c,
            "heat_risk_level": climate_report.heat_risk.heat_risk_level.value,
            "cold_risk_level": climate_report.cold_risk.frost_hazard_level.value,
        }

        return RotationRecommendation(
            farm_id=request.farm_id,
            latitude=farm_profile.latitude,
            longitude=farm_profile.longitude,
            analysis_date=date.today(),
            climate_summary=climate_summary,
            strategies=strategies,
            primary_strategy=primary,
            generated_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            engine_version="1.0.0",
        )


# Global singleton instance
rotation_engine = RotationEngine()