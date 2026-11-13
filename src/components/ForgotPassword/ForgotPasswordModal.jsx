import { useState } from 'react'
import Modal from '../Modal/Modal'
import useLabels from '../../hooks/useLabels'
import { resetPassword } from '../../services/authService'
import '../Auth/AuthExtras.css'

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

export default function ForgotPasswordModal({ initialEmail = '', onClose }) {
  const { t } = useLabels()
  const [email, setEmail] = useState(initialEmail)
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState('')
  const [done, setDone] = useState(false)
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')

    if (!EMAIL_PATTERN.test(email.trim())) return setError('emailInvalid')
    if (password.length < 6) return setError('passwordShort')
    if (password !== confirm) return setError('passwordMismatch')

    setLoading(true)
    const result = await resetPassword(email, password)
    setLoading(false)

    if (result.ok) setDone(true)
    else setError(result.error)
  }

  return (
    <Modal title={t('auth.forgotTitle')} onClose={onClose}>
      {done ? (
        <>
          <div className="auth-success-box">{t('auth.resetDone')}</div>
          <button type="button" className="auth-btn" onClick={onClose}>
            {t('common.close')}
          </button>
        </>
      ) : (
        <form onSubmit={handleSubmit} noValidate>
          <p style={{ color: '#6b7280', fontSize: '14px', marginBottom: '16px' }}>{t('auth.forgotText')}</p>

          {error && <div className="auth-error-box">{t('auth.errors.' + error)}</div>}

          <div className="auth-field">
            <label>{t('login.emailLabel')}</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder={t('login.emailPlaceholder')}
            />
          </div>

          <div className="auth-field">
            <label>{t('auth.newPassword')}</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder={t('auth.passwordPh')}
            />
          </div>

          <div className="auth-field">
            <label>{t('auth.confirmPassword')}</label>
            <input
              type="password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              placeholder={t('auth.confirmPasswordPh')}
            />
          </div>

          <button type="submit" className="auth-btn" disabled={loading}>
            {loading ? t('auth.resetting') : t('auth.resetButton')}
          </button>
        </form>
      )}
    </Modal>
  )
}
