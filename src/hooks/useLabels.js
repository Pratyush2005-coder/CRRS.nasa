import { useTranslation } from 'react-i18next'

// Shared translation helpers. Crop / soil names stay English internally;
// only the label that is shown on screen is translated.
export default function useLabels() {
  const { t, i18n } = useTranslation()
  const lang = (i18n.resolvedLanguage || i18n.language || 'en').startsWith('bn') ? 'bn' : 'en'

  const tCrop = (name) => (name ? t(`cropNames.${name}`, { defaultValue: name }) : name)
  const tSoil = (name) => (name ? t(`soilTypes.${name}`, { defaultValue: name }) : name)
  const cropLabel = (crop) =>
    lang === 'bn' ? `${crop.bn} (${crop.en})` : `${crop.en} (${crop.bn})`

  return { t, lang, tCrop, tSoil, cropLabel }
}
