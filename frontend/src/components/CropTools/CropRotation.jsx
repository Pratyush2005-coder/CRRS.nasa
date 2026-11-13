import { useState } from 'react'
import useLabels from '../../hooks/useLabels'
import { seasons, seasonMeta, cropOptions, cropsBySeason, cropEmoji, soilTypeOptions, soilEmoji } from '../../data/crops'

// Crop Rotation planner - the same section is used on the landing page (no login needed)
// and inside the dashboard.
export default function CropRotation() {
  const { t, tCrop, tSoil, cropLabel } = useLabels()
  const [selectedCrops, setSelectedCrops] = useState([]);
  const [selectedRotationSeasons, setSelectedRotationSeasons] = useState([]);
  const [selectedRotationSoil, setSelectedRotationSoil] = useState('');
  const [rotationResult, setRotationResult] = useState(null);

  return (
    <section className="crop-rotation">
      <h2 id="crop-rotation">🌱 {t('rotation.title')}</h2>
      <p>{t('rotation.subtitle')}</p>

      <div className="profile-card">
        <h3>🌦️ {t('rotation.selectSeasons')}</h3>
        <div className="crop-grid">
          {seasons.map((season) => (
            <button
              key={season}
              type="button"
              className={
                selectedRotationSeasons.includes(season)
                  ? "crop-option selected"
                  : "crop-option"
              }
              onClick={() =>
                setSelectedRotationSeasons((prev) =>
                  prev.includes(season)
                    ? prev.filter((s) => s !== season)
                    : [...prev, season]
                )
              }
            >
              {selectedRotationSeasons.includes(season) ? "✅ " : seasonMeta[season].emoji + " "}
              {t('seasons.' + season)}
            </button>
          ))}
        </div>

        <h3>🌱 {t('common.soilType')}</h3>
        <div className="crop-grid">
          {soilTypeOptions.map((soil) => (
            <button
              key={soil}
              type="button"
              className={
                selectedRotationSoil === soil
                  ? "crop-option selected"
                  : "crop-option"
              }
              onClick={() => setSelectedRotationSoil(soil)}
            >
              {selectedRotationSoil === soil ? "✅ " : soilEmoji[soil] + " "}
              {tSoil(soil)}
            </button>
          ))}
        </div>

        <h3>🌾 {t('rotation.selectCrops')}</h3>
        {selectedRotationSeasons.length === 0 && (
          <p>{t('rotation.pickSeasonHint')}</p>
        )}

        {selectedRotationSeasons.map((season) => (
          <div key={season} className="crop-category">
            <h4>{seasonMeta[season].emoji} {t('rotation.seasonCrops', { season: t('seasons.' + season) })}</h4>
            <div className="crop-grid">
              {cropOptions
                .filter((crop) => cropsBySeason[season].includes(crop.en))
                .map((crop) => (
                  <button
                    key={`${season}-${crop.en}`}
                    type="button"
                    className={
                      selectedCrops.includes(crop.en)
                        ? "crop-option selected"
                        : "crop-option"
                    }
                    onClick={() =>
                      setSelectedCrops((prev) =>
                        prev.includes(crop.en)
                          ? prev.filter((c) => c !== crop.en)
                          : [...prev, crop.en]
                      )
                    }
                  >
                    {selectedCrops.includes(crop.en) ? "✅ " : cropEmoji[crop.en] + " "}
                    {cropLabel(crop)}
                  </button>
                ))}
            </div>
          </div>
        ))}

        <p>
          {t('common.selectedSeasons')}: <strong>{selectedRotationSeasons.length}</strong>
        </p>
        <p>
          {t('common.selectedCrops')}: <strong>{selectedCrops.length}</strong>
        </p>

        <button
          type="button"
          className="rotation-primary-button"
          onClick={() => {
            if (selectedRotationSeasons.length === 0) {
              alert(t('rotation.alertSeason'));
              return;
            }

            if (!selectedRotationSoil) {
              alert(t('rotation.alertSoil'));
              return;
            }

            if (selectedCrops.length < 3) {
              alert(t('rotation.alertCrops'));
              return;
            }

            const seasonsWithoutCrops = selectedRotationSeasons.filter(
              (season) =>
                !selectedCrops.some((crop) =>
                  cropsBySeason[season].includes(crop)
                )
            );

            if (seasonsWithoutCrops.length > 0) {
              alert(
                t('rotation.alertSeasonNoCrop', { seasons: seasonsWithoutCrops.map((s) => t('seasons.' + s)).join(', ') })
              );
              return;
            }

            const firstSeason = selectedRotationSeasons[0];
            const firstSeasonCrops = selectedCrops.filter((crop) =>
              cropsBySeason[firstSeason].includes(crop)
            );

            if (firstSeasonCrops.length < 3) {
              alert(
                t('rotation.alertFirstSeason', { season: t('seasons.' + firstSeason) })
              );
              return;
            }

            setRotationResult({ seasons: selectedRotationSeasons, soil: selectedRotationSoil, crops: selectedCrops });
          }}
        >
          {t('rotation.generate')}
        </button>

        {rotationResult && (
          <div className="rotation-result">
            <h3>🌿 {t('rotation.resultTitle')}</h3>
            <p>{`${rotationResult.seasons.map((s) => t('seasons.' + s)).join(' → ')} | ${tSoil(rotationResult.soil)} | ${rotationResult.crops.map(tCrop).join(' → ')}`}</p>
          </div>
        )}
      </div>
    </section>
  )
}
