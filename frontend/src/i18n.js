import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import LanguageDetector from 'i18next-browser-languagedetector'
import en from './locales/en.json'
import bn from './locales/bn.json'

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      en: { translation: en },
      bn: { translation: bn },
    },
    fallbackLng: 'en',
    supportedLngs: ['en', 'bn'],
    load: 'languageOnly',
    interpolation: { escapeValue: false }, // React already escapes values
    detection: {
      // Only use the language the user picked earlier; otherwise English.
      order: ['localStorage'],
      lookupLocalStorage: 'agroverseLang',
      caches: ['localStorage'],
    },
  })

const setHtmlLang = (lng) => {
  document.documentElement.lang = lng && lng.startsWith('bn') ? 'bn' : 'en'
}
setHtmlLang(i18n.resolvedLanguage || i18n.language)
i18n.on('languageChanged', setHtmlLang)

export default i18n
