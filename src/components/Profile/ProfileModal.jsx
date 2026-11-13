import { useState } from 'react'
import Modal from '../Modal/Modal'
import useLabels from '../../hooks/useLabels'
import { cropOptions, cropEmoji, soilTypeOptions, soilEmoji } from '../../data/crops'
import { updateProfile } from '../../services/authService'
import '../Auth/AuthExtras.css'

// "My Profile" popup: shows all the farmer's details and lets them change them.
// Email and location are read-only.
export default function ProfileModal({ user, onClose, onSaved }) {
  const { t, tSoil, cropLabel } = useLabels()
  const [values, setValues] = useState({
    name: user.name || '',
    landArea: user.landArea || '',
    farmSoil: user.farmSoil || '',
    currentCrop: user.currentCrop || '',
  })
  const [errors, setErrors] = useState({})
  const [formError, setFormError] = useState('')
  const [saved, setSaved] = useState(false)
  const [loading, setLoading] = useState(false)

  const setField = (field) => (e) => {
    const value = e.target.value
    setValues((prev) => ({ ...prev, [field]: value }))
    setErrors((prev) => ({ ...prev, [field]: undefined }))
    setSaved(false)
  }

  const setSoil = (soil) => {
    setValues((prev) => ({ ...prev, farmSoil: soil }))
    setErrors((prev) => ({ ...prev, farmSoil: undefined }))
    setSaved(false)
  }

  const validate = () => {
    const found = {}
    if (!values.name.trim()) found.name = 'nameRequired'
    if (!(Number(values.landArea) > 0)) found.landArea = 'landAreaInvalid'
    if (!values.farmSoil) found.farmSoil = 'soilRequired'
    if (!values.currentCrop) found.currentCrop = 'cropRequired'
    return found
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setFormError('')
    setSaved(false)

    const found = validate()
    setErrors(found)
    if (Object.keys(found).length > 0) return

    setLoading(true)
    const result = await updateProfile(values)
    setLoading(false)

    if (result.ok) {
      onSaved(result.user)
      setSaved(true)
    } else {
      setFormError(result.error || 'generic')
    }
  }

  const fieldError = (field) =>
    errors[field] ? <small className="auth-error">{t('auth.errors.' + errors[field])}</small> : null

  return (
    <Modal title={t('profile.title')} onClose={onClose}>
      <form onSubmit={handleSubmit} noValidate>
        {formError && <div className="auth-error-box">{t('auth.errors.' + formError)}</div>}
        {saved && <div className="auth-success-box">{t('profile.saved')}</div>}

        <div className="auth-field">
          <label>{t('auth.fullName')}</label>
          <input type="text" value={values.name} onChange={setField('name')} placeholder={t('auth.fullNamePh')} />
          {fieldError('name')}
        </div>

        <div className="auth-field">
          <label>{t('login.emailLabel')}</label>
          <input type="email" value={user.email} disabled readOnly />
          <small className="auth-hint">{t('profile.emailReadonly')}</small>
        </div>

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
          {loading ? t('profile.saving') : t('profile.save')}
        </button>
        <button type="button" className="auth-btn secondary" onClick={onClose}>
          {t('common.close')}
        </button>
      </form>
    </Modal>
  )
}
