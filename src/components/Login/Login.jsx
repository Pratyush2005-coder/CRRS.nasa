import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import LanguageSwitcher from '../LanguageSwitcher/LanguageSwitcher';
import ForgotPasswordModal from '../ForgotPassword/ForgotPasswordModal';
import { signIn } from '../../services/authService';
import './Login.css';
import '../Auth/AuthExtras.css';

const Login = ({ onLogin, onSignupClick }) => {
  const { t } = useTranslation();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [showForgot, setShowForgot] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    const result = await signIn(email, password);
    setLoading(false);

    if (result.ok) {
      if (onLogin) onLogin(result.user);
    } else {
      setError(result.error);
    }
  };

  return (
    <div className="login-wrapper">
      <LanguageSwitcher floating />
      <div className="login-box">
        <h2>🌱 AGROVERSE AI</h2>
        <p>{t('login.subtitle')}</p>
        
        <form onSubmit={handleSubmit}>
          {error && <div className="auth-error-box">{t('auth.errors.' + error)}</div>}

          <div className="form-group">
            <label>{t('login.emailLabel')}</label>
            <input 
              type="email" 
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder={t('login.emailPlaceholder')} 
              required 
            />
          </div>

          <div className="form-group">
            <label>{t('login.passwordLabel')}</label>
            <input 
              type="password" 
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder={t('login.passwordPlaceholder')} 
              required 
            />
          </div>

          <div className="form-options">
            <label><input type="checkbox" /> {t('login.remember')}</label>
            <a
              href="#forgot"
              onClick={(e) => {
                e.preventDefault();
                setShowForgot(true);
              }}
            >
              {t('login.forgot')}
            </a>
          </div>

          <button type="submit" className="login-btn" disabled={loading}>
            {loading ? t('auth.signingIn') : t('login.signIn')}
          </button>
        </form>

        <p className="auth-switch">
          {t('auth.newHere')}{' '}
          <button type="button" className="auth-link" onClick={onSignupClick}>
            {t('auth.createAccountLink')}
          </button>
        </p>
      </div>

      {showForgot && (
        <ForgotPasswordModal initialEmail={email} onClose={() => setShowForgot(false)} />
      )}
    </div>
  );
};

export default Login;
