import { useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import './Modal.css'

// Simple popup: closes with the X button, the Esc key, or a click on the dark background.
export default function Modal({ title, onClose, children }) {
  const { t } = useTranslation()

  useEffect(() => {
    const onKeyDown = (e) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKeyDown)
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden' // stop the page behind from scrolling
    return () => {
      document.removeEventListener('keydown', onKeyDown)
      document.body.style.overflow = previousOverflow
    }
  }, [onClose])

  return (
    <div
      className="modal-backdrop"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div className="modal-card" role="dialog" aria-modal="true" aria-label={title}>
        <button type="button" className="modal-close" onClick={onClose} aria-label={t('common.close')}>
          ✕
        </button>
        <h2>{title}</h2>
        {children}
      </div>
    </div>
  )
}
