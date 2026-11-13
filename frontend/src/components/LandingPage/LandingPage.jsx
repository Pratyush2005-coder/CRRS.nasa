import React from 'react'
import { useTranslation } from 'react-i18next'
import LanguageSwitcher from '../LanguageSwitcher/LanguageSwitcher'
import CropRecommendation from '../CropTools/CropRecommendation'
import CropRotation from '../CropTools/CropRotation'

function LandingPage({ onGetStarted, onLoginClick }) {
  const { t } = useTranslation()

  return (
    <div style={styles.landingContainer}>
      {/* Header / Navbar */}
      <header style={styles.navbar}>
        <div style={styles.logo}>🌱 AGROVERSE AI</div>
        <nav style={styles.navLinks}>
          <a href="#features" style={styles.link}>{t('landing.navFeatures')}</a>
          <a href="#crop-recommendation-section" style={styles.link}>{t('nav.cropRecommendation')}</a>
          <a href="#crop-rotation-section" style={styles.link}>{t('nav.cropRotation')}</a>
          <a href="#about" style={styles.link}>{t('landing.navAbout')}</a>
          <a href="#contact" style={styles.link}>{t('landing.navContact')}</a>
        </nav>
        <div style={styles.authButtons}>
          <LanguageSwitcher />
          <button style={styles.loginBtn} onClick={onLoginClick}>{t('landing.signIn')}</button>
          <button style={styles.signupBtn} onClick={onGetStarted}>{t('landing.signUp')}</button>
        </div>
      </header>

      {/* Hero Section */}
      <section style={styles.hero}>
        <div style={styles.heroText}>
          <h1 style={styles.heroTitle}>{t('landing.heroTitle')}</h1>
          <p style={styles.heroSubtitle}>
            {t('landing.heroSubtitle')}
          </p>
          <button style={styles.ctaBtn} onClick={onGetStarted}>
            {t('landing.getStarted')}
          </button>
        </div>
        <div style={styles.heroImage}>
          <img 
            src="https://cdn-icons-png.flaticon.com/512/2909/2909760.png" 
            alt="Agroverse AI" 
            style={{ width: '80%', maxWidth: '400px' }} 
          />
        </div>
      </section>

      {/* Features Overview Section */}
      <section id="features" style={styles.featuresSection}>
        <h2 style={{ textAlign: 'center', color: '#166534', marginBottom: '30px', fontSize: '32px' }}>
          {t('landing.whyTitle')}
        </h2>
        <div style={styles.featuresGrid}>
          <div style={styles.featureCard}>
            <h3>{t('landing.f1Title')}</h3>
            <p>{t('landing.f1Text')}</p>
          </div>
          <div style={styles.featureCard}>
            <h3>{t('landing.f2Title')}</h3>
            <p>{t('landing.f2Text')}</p>
          </div>
          <div style={styles.featureCard}>
            <h3>{t('landing.f3Title')}</h3>
            <p>{t('landing.f3Text')}</p>
          </div>
          <div style={styles.featureCard}>
            <h3>{t('landing.f4Title')}</h3>
            <p>{t('landing.f4Text')}</p>
          </div>
        </div>
      </section>

      {/* Crop Recommendation + Crop Rotation: free to use, no login needed */}
      <section id="crop-recommendation-section" style={styles.toolSectionLight}>
        <div style={styles.toolInner}>
          <CropRecommendation />
        </div>
      </section>
      <section id="crop-rotation-section" style={styles.toolSectionGreen}>
        <div style={styles.toolInner}>
          <CropRotation />
        </div>
      </section>

      {/* 🟢 ১. About Us Section (নতুন যুক্ত করা হয়েছে) */}
      <section id="about" style={styles.aboutSection}>
        <div style={{ maxWidth: '1000px', margin: '0 auto', textAlign: 'center' }}>
          <h2 style={{ color: '#166534', marginBottom: '20px', fontSize: '32px' }}>{t('landing.aboutTitle')}</h2>
          <p style={{ fontSize: '18px', color: '#475569', lineHeight: '1.8' }}>
            {t('landing.aboutText')}
          </p>
        </div>
      </section>

      {/* 🟢 ২. Contact Section (নতুন যুক্ত করা হয়েছে) */}
      <section id="contact" style={styles.contactSection}>
        <div style={{ maxWidth: '800px', margin: '0 auto', textAlign: 'center' }}>
          <h2 style={{ color: '#166534', marginBottom: '15px', fontSize: '32px' }}>{t('landing.contactTitle')}</h2>
          <p style={{ fontSize: '16px', color: '#64748b', marginBottom: '30px' }}>
            {t('landing.contactText')}
          </p>
          <div style={styles.contactCardsGroup}>
            <div style={styles.contactCard}>
              <h4>{t('landing.officeTitle')}</h4>
              <p>{t('place.puruliaIndia')}</p>
            </div>
            <div style={styles.contactCard}>
              <h4>{t('landing.emailTitle')}</h4>
              <p>support@agroverse.ai</p>
            </div>
            <div style={styles.contactCard}>
              <h4>{t('landing.callTitle')}</h4>
              <p>+91 98765 43210</p>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer style={styles.footer}>
        <p>{t('landing.footer')}</p>
      </footer>
    </div>
  )
}

const styles = {
  landingContainer: {
    fontFamily: "'Segoe UI', Tahoma, Geneva, Verdana, 'Noto Sans Bengali', sans-serif",
    backgroundColor: '#f8fafc',
    color: '#1e293b',
    minHeight: '100vh',
    scrollBehavior: 'smooth', // স্মুথ স্ক্রলিং এর জন্য
  },
  navbar: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: '12px',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '20px 40px',
    backgroundColor: '#ffffff',
    boxShadow: '0 2px 10px rgba(0,0,0,0.05)',
    position: 'sticky',
    top: 0,
    zIndex: 100,
  },
  logo: {
    fontSize: '24px',
    fontWeight: 'bold',
    color: '#15803d',
  },
  navLinks: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: '25px',
  },
  link: {
    textDecoration: 'none',
    color: '#475569',
    fontWeight: '600',
    transition: 'color 0.2s',
  },
  authButtons: {
    display: 'flex',
    gap: '15px',
  },
  loginBtn: {
    padding: '8px 20px',
    border: '1px solid #16a34a',
    backgroundColor: 'transparent',
    color: '#16a34a',
    borderRadius: '8px',
    cursor: 'pointer',
    fontWeight: 'bold',
  },
  signupBtn: {
    padding: '8px 20px',
    border: 'none',
    backgroundColor: '#16a34a',
    color: '#ffffff',
    borderRadius: '8px',
    cursor: 'pointer',
    fontWeight: 'bold',
  },
  hero: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '80px 40px',
    maxWidth: '1200px',
    margin: '0 auto',
    flexWrap: 'wrap',
  },
  heroText: {
    flex: '1 1 500px',
  },
  heroTitle: {
    fontSize: '48px',
    color: '#14532d',
    marginBottom: '20px',
  },
  heroSubtitle: {
    fontSize: '18px',
    color: '#64748b',
    lineHeight: '1.6',
    marginBottom: '30px',
  },
  ctaBtn: {
    padding: '14px 32px',
    fontSize: '18px',
    backgroundColor: '#16a34a',
    color: '#ffffff',
    border: 'none',
    borderRadius: '10px',
    cursor: 'pointer',
    fontWeight: 'bold',
    boxShadow: '0 4px 14px rgba(22, 163, 74, 0.4)',
  },
  heroImage: {
    flex: '1 1 400px',
    display: 'flex',
    justifyContent: 'center',
  },
  toolSectionLight: {
    padding: '20px 40px',
    backgroundColor: '#f8fafc',
    scrollMarginTop: '80px',
  },
  toolSectionGreen: {
    padding: '20px 40px',
    backgroundColor: '#f0fdf4',
    scrollMarginTop: '80px',
  },
  toolInner: {
    maxWidth: '1200px',
    margin: '0 auto',
  },
  featuresSection: {
    padding: '80px 40px',
    backgroundColor: '#ffffff',
  },
  featuresGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
    gap: '20px',
    maxWidth: '1200px',
    margin: '0 auto',
  },
  featureCard: {
    padding: '24px',
    backgroundColor: '#f0fdf4',
    borderRadius: '12px',
    border: '1px solid #dcfce7',
  },
  // 🟢 About Section এর স্টাইল
  aboutSection: {
    padding: '80px 40px',
    backgroundColor: '#f1f5f9',
  },
  // 🟢 Contact Section এর স্টাইল
  contactSection: {
    padding: '80px 40px',
    backgroundColor: '#ffffff',
  },
  contactCardsGroup: {
    display: 'flex',
    justifyContent: 'space-around',
    gap: '20px',
    flexWrap: 'wrap',
    marginTop: '30px',
  },
  contactCard: {
    padding: '20px',
    backgroundColor: '#f8fafc',
    borderRadius: '10px',
    border: '1px solid #e2e8f0',
    flex: '1 1 200px',
  },
  footer: {
    textAlign: 'center',
    padding: '20px',
    backgroundColor: '#0f172a',
    color: '#94a3b8',
  }
}

export default LandingPage