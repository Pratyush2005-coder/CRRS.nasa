import { useState } from 'react'
import LanguageSwitcher from '../LanguageSwitcher/LanguageSwitcher'
import useLabels from '../../hooks/useLabels'
import { cropOptions, cropEmoji, soilTypeOptions, soilEmoji } from '../../data/crops'
import { signUp } from '../../services/authService'
import '../Login/Login.css'
import '../Auth/AuthExtras.css'

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

const emptyValues = {
  name: '',
  email: '',
  password: '',
  confirmPassword: '',
  landArea: '',
  farmSoil: '',
  currentCrop: '',
}

export default function Signup({ onSignedUp, onLoginClick }) {
  const { t, tSoil, cropLabel } = useLabels()
  const [values, setValues] = useState(emptyValues)
  const [errors, setErrors] = useState({})
  const [formError, setFormError] = useState('')
  const [loading, setLoading] = useState(false)

  const setField = (field) => (e) => {
    const value = e.target.value
    setValues((prev) => ({ ...prev, [field]: value }))
    setErrors((prev) => ({ ...prev, [field]: undefined }))
  }

  const setSoil = (soil) => {
    setValues((prev) => ({ ...prev, farmSoil: soil }))
    setErrors((prev) => ({ ...prev, farmSoil: undefined }))
  }

  const validate = () => {
    const found = {}
    if (!values.name.trim()) found.name = 'nameRequired'
    if (!EMAIL_PATTERN.test(values.email.trim())) found.email = 'emailInvalid'
    if (values.password.length < 6) found.password = 'passwordShort'
    if (values.confirmPassword !== values.password) found.confirmPassword = 'passwordMismatch'
    if (!(Number(values.landArea) > 0)) found.landArea = 'landAreaInvalid'
    if (!values.farmSoil) found.farmSoil = 'soilRequired'
    if (!values.currentCrop) found.currentCrop = 'cropRequired'
    return found
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setFormError('')

    const found = validate()
    setErrors(found)
    if (Object.keys(found).length > 0) return

    setLoading(true)
    const result = await signUp(values)
    setLoading(false)

    if (result.ok) {
      onSignedUp(result.user)
    } else if (result.error === 'emailExists') {
      setErrors({ email: 'emailExists' })
    } else {
      setFormError(result.error || 'generic')
    }
  }

  const fieldError = (field) =>
    errors[field] ? <small className="auth-error">{t('auth.errors.' + errors[field])}</small> : null

  return (
    <div className="login-wrapper auth-wrapper">
      <LanguageSwitcher floating />
      <div className="login-box signup-box">
        <h2>🌱 AGROVERSE AI</h2>
        <p>{t('auth.signupSubtitle')}</p>

        <form onSubmit={handleSubmit} noValidate>
          {formError && <div className="auth-error-box">{t('auth.errors.' + formError)}</div>}

          <h3 className="auth-section-title">{t('auth.accountSection')}</h3>

          <div className="auth-field">
            <label>{t('auth.fullName')}</label>
            <input
              type="text"
              value={values.name}
              onChange={setField('name')}
              placeholder={t('auth.fullNamePh')}
            />
            {fieldError('name')}
          </div>

          <div className="auth-field">
            <label>{t('login.emailLabel')}</label>
            <input
              type="email"
              value={values.email}
              onChange={setField('email')}
              placeholder={t('login.emailPlaceholder')}
            />
            {fieldError('email')}
          </div>

          <div className="auth-field">
            <label>{t('login.passwordLabel')}</label>
            <input
              type="password"
              value={values.password}
              onChange={setField('password')}
              placeholder={t('auth.passwordPh')}
            />
            {fieldError('password')}
          </div>

          <div className="auth-field">
            <label>{t('auth.confirmPassword')}</label>
            <input
              type="password"
              value={values.confirmPassword}
              onChange={setField('confirmPassword')}
              placeholder={t('auth.confirmPasswordPh')}
            />
            {fieldError('confirmPassword')}
          </div>

          <h3 className="auth-section-title">{t('auth.farmSection')}</h3>

          <div className="auth-field">
            <label>{t('farmProfile.location')}</label>
            <input type="text" value={t('place.purulia')} disabled readOnly />
            <small className="auth-hint">{t('auth.locationFixed')}</small>
          </div>

          <div className="auth-field">
            <label>{t('farmProfile.landArea')}</label>
            <input
              type="number"
              min="0"
              step="any"
              value={values.landArea}
              onChange={setField('landArea')}
              placeholder={t('farmProfile.landAreaPh')}
            />
            {fieldError('landArea')}
          </div>

          <div className="auth-field">
            <label>{t('farmProfile.soilType')}</label>
            <div className="crop-grid">
              {soilTypeOptions.map((soil) => (
                <button
                  key={soil}
                  type="button"
                  className={values.farmSoil === soil ? 'crop-option selected' : 'crop-option'}
                  onClick={() => setSoil(soil)}
                >
                  {values.farmSoil === soil ? '✅ ' : soilEmoji[soil] + ' '}
                  {tSoil(soil)}
                </button>
              ))}
            </div>
            {fieldError('farmSoil')}
          </div>

          <div className="auth-field">
            <label>{t('farmProfile.currentCrop')}</label>
            <select value={values.currentCrop} onChange={setField('currentCrop')}>
              <option value="">{t('farmProfile.selectCrop')}</option>
              {cropOptions.map((crop) => (
                <option key={crop.en} value={crop.en}>
                  {cropEmoji[crop.en]} {cropLabel(crop)}
                </option>
              ))}
            </select>
            {fieldError('currentCrop')}
          </div>

          <button type="submit" className="auth-btn" disabled={loading}>
            {loading ? t('auth.creatingAccount') : t('auth.createAccount')}
          </button>
        </form>

        <p className="auth-switch">
          {t('auth.haveAccount')}{' '}
          <button type="button" className="auth-link" onClick={onLoginClick}>
            {t('auth.signInLink')}
          </button>
        </p>
      </div>
    </div>
  )
}
