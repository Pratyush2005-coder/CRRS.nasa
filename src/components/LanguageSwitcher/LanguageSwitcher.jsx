import { useTranslation } from 'react-i18next'

const languages = [
  { code: 'en', label: 'English' },
  { code: 'bn', label: 'বাংলা' },
]

// floating = true -> fixed to the top-right corner (used on pages with no navbar, e.g. Login)
export default function LanguageSwitcher({ floating = false }) {
  const { t, i18n } = useTranslation()
  const current = (i18n.resolvedLanguage || i18n.language || 'en').startsWith('bn') ? 'bn' : 'en'

  const wrapperStyle = {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '6px',
    padding: '6px 10px',
    backgroundColor: '#ffffff',
    border: '1px solid #16a34a',
    borderRadius: '8px',
    color: '#16a34a',
    fontWeight: 'bold',
    ...(floating
      ? { position: 'fixed', top: '16px', right: '16px', zIndex: 1000 }
      : {}),
  }

  const selectStyle = {
    border: 'none',
    background: 'transparent',
    color: 'inherit',
    font: 'inherit',
    cursor: 'pointer',
  }

  return (
    <div style={wrapperStyle}>
      <span aria-hidden="true">🌐</span>
      <select
        aria-label={t('language.label')}
        value={current}
        onChange={(e) => i18n.changeLanguage(e.target.value)}
        style={selectStyle}
      >
        {languages.map((lang) => (
          <option key={lang.code} value={lang.code}>
            {lang.label}
          </option>
        ))}
      </select>
    </div>
  )
}
