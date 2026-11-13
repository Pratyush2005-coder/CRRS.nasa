import './App.css'
import { useState, useEffect, useRef } from 'react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer
} from 'recharts'
import { MapContainer, TileLayer, Marker, Popup, Polygon } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import L from 'leaflet'
import 'leaflet-draw/dist/leaflet.draw.css'
import 'leaflet-draw'
import FarmDraw from './FarmDraw'
import Login from './components/Login/Login'
import useLabels from './hooks/useLabels'
import LanguageSwitcher from './components/LanguageSwitcher/LanguageSwitcher'
import Signup from './components/Signup/Signup'
import ProfileModal from './components/Profile/ProfileModal'
import CropRecommendation from './components/CropTools/CropRecommendation'
import CropRotation from './components/CropTools/CropRotation'
import { getCurrentUser, signOut } from './services/authService'
import { FARM_LOCATION, FARM_MAP_VIEW } from './config/location'
import LandingPage from './components/LandingPage/LandingPage' // 🟢 ১. LandingPage ইম্পোর্ট করা হলো

function App() {
  // 🟢 ২. পেজ নেভিগেশন কন্ট্রোল করার জন্য নতুন স্টেট ('home', 'login', 'dashboard')
  const [currentPage, setCurrentPage] = useState(() => (getCurrentUser() ? 'dashboard' : 'home'))
  const [isProfileOpen, setIsProfileOpen] = useState(false)
  const [user, setUser] = useState(() => getCurrentUser()) // logged-in farmer (null = logged out)
  const [isProfileModalOpen, setIsProfileModalOpen] = useState(false)
  const dropdownRef = useRef(null)

  // --- language helpers (react-i18next) ---
  const { t, lang, tCrop, tSoil } = useLabels()
  const dateLocale = lang === 'bn' ? 'bn-IN' : 'en-GB'
  const monthLocale = lang === 'bn' ? 'bn-IN' : 'en-US'
  const showData = (value) => (value === 'Awaiting Data' ? t('climate.awaitingData') : value)
  const showRain = (value) =>
    value === 'Awaiting Data'
      ? t('climate.awaitingData')
      : String(value).replace('(7-day total)', `(${t('climate.sevenDayTotal')})`)
  const formatMonth = (key) =>
    new Date(Number(String(key).slice(0, 4)), Number(String(key).slice(4, 6)) - 1)
      .toLocaleDateString(monthLocale, { month: 'short', year: 'numeric' })

  // --- farmer data comes from the logged-in user's profile (set up on the Sign Up page) ---
  const landArea = user?.landArea || ''
  const farmSoil = user?.farmSoil || ''
  const currentCrop = user?.currentCrop || ''
  const farmLocation = t('place.purulia') // fixed to Purulia (see src/config/location.js)

  const [activeMenu, setActiveMenu] = useState('dashboard')

  // Makes a dashboard card behave like the sidebar link: click (or Enter / Space) scrolls to the section
  const goTo = (id) => ({
    role: 'link',
    tabIndex: 0,
    onClick: () => {
      setActiveMenu(id)
      document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
      window.history.replaceState(null, '', '#' + id)
    },
    onKeyDown: (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault()
        e.currentTarget.click()
      }
    },
  })
  const [soil, setSoil] = useState('')
  const [water, setWater] = useState('')
  const [rotationSaved, setRotationSaved] = useState(false)
  const [advisorQuestion, setAdvisorQuestion] = useState('')
  const [advisorAnswer, setAdvisorAnswer] = useState(null)
  const [isAdvisorLoading, setIsAdvisorLoading] = useState(false)
  const [nextCrop, setNextCrop] = useState('Pulses')
  const [followingCrop, setFollowingCrop] = useState('Vegetables')
  const [soilPH, setSoilPH] = useState("");
  const [soilPHResult, setSoilPHResult] = useState(null);
  const [soilPHLoading, setSoilPHLoading] = useState(false);
  const [soilPHError, setSoilPHError] = useState("");
  const [temperature, setTemperature] = useState('Awaiting Data')
  const [rainfall, setRainfall] = useState('Awaiting Data')
  const [humidity, setHumidity] = useState('Awaiting Data')
  const [solarRadiation, setSolarRadiation] = useState('Awaiting Data')
  const [climateMessage, setClimateMessage] = useState(null)
  const [climateGraphData, setClimateGraphData] = useState([])
  const [selectedMonth, setSelectedMonth] = useState('all')
  const [dailyClimateData, setDailyClimateData] = useState([])

  const latitude = FARM_LOCATION.lat
  const longitude = FARM_LOCATION.lng

  useEffect(() => {
    const savedClimate = localStorage.getItem('agroverseClimate')
    if (savedClimate) {
      const climate = JSON.parse(savedClimate)
      setTemperature(climate.temperature)
      setRainfall(climate.rainfall)
      setHumidity(climate.humidity)
      setSolarRadiation(climate.solarRadiation)
    }
  }, [])

  useEffect(() => {
        const savedRotation = localStorage.getItem('agroverseRotation')
    if (savedRotation) {
      const rotation = JSON.parse(savedRotation)
      setNextCrop(rotation.nextCrop)
      setFollowingCrop(rotation.followingCrop)
      setRotationSaved(true)
    }
  }, [])

  // Dropdown-এর বাইরে ক্লিক করলে মেনু বন্ধ করার ব্যবস্থা
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsProfileOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // 🟢 ৩. লগআউট করলে আবার হোম পেজে ফিরিয়ে নিয়ে যাওয়া
  const handleLogout = async () => {
    await signOut()
    setUser(null)
    setCurrentPage('home')
    setIsProfileOpen(false)
    setIsProfileModalOpen(false)
  }

  const askAdvisor = () => {
    setIsAdvisorLoading(true)
    if (!advisorQuestion.trim()) {
      setAdvisorAnswer({ kind: 'empty' })
      setIsAdvisorLoading(false)
      return
    }

    setAdvisorAnswer({ kind: 'ok', question: advisorQuestion })
    setIsAdvisorLoading(false)
  }

  const getClimateData = async () => {
    try {
      setClimateMessage({ kind: 'loading' })

      const endDate = new Date()
      endDate.setDate(endDate.getDate() - 5)

      const startDate = new Date(endDate)
      startDate.setMonth(startDate.getMonth() - 6)

      const formatDate = (date) =>
        date.toISOString().slice(0, 10).replaceAll('-', '')

      const url = `https://power.larc.nasa.gov/api/temporal/daily/point?parameters=T2M,PRECTOTCORR,RH2M,ALLSKY_SFC_SW_DWN&community=AG&longitude=${longitude}&latitude=${latitude}&start=${formatDate(startDate)}&end=${formatDate(endDate)}&format=JSON`

      const response = await fetch(url)

      if (!response.ok) {
        throw new Error('NASA API request failed')
      }

      const data = await response.json()
      const parameters = data.properties.parameter
      const dates = Object.keys(parameters.T2M)

      const monthlyData = {}

      dates.forEach((date) => {
        const month = date.slice(0, 6)

        if (!monthlyData[month]) {
          monthlyData[month] = {
            temperature: [],
            rainfall: [],
            humidity: [],
            solar: []
          }
        }

        const temp = parameters.T2M[date]
        const rain = parameters.PRECTOTCORR[date]
        const hum = parameters.RH2M[date]
        const sol = parameters.ALLSKY_SFC_SW_DWN[date]

        if (temp !== -999) monthlyData[month].temperature.push(temp)
        if (rain !== -999) monthlyData[month].rainfall.push(rain)
        if (hum !== -999) monthlyData[month].humidity.push(hum)
        if (sol !== -999) monthlyData[month].solar.push(sol)
      })

      const graphData = Object.entries(monthlyData).map(([month, values]) => ({
        month, // e.g. '202605' - formatted for display with formatMonth()
        temperature: values.temperature.length
          ? values.temperature.reduce((a, b) => a + b, 0) / values.temperature.length
          : 0,
        rainfall: values.rainfall.reduce((a, b) => a + b, 0),
        humidity: values.humidity.length
          ? values.humidity.reduce((a, b) => a + b, 0) / values.humidity.length
          : 0,
        solar: values.solar.length
          ? values.solar.reduce((a, b) => a + b, 0) / values.solar.length
          : 0
      }))

      setClimateGraphData(graphData)
      const dailyData = dates.map((date) => ({
        date,
        temperature: parameters.T2M[date],
        rainfall: parameters.PRECTOTCORR[date],
        humidity: parameters.RH2M[date],
        solar: parameters.ALLSKY_SFC_SW_DWN[date],
      }))

      setDailyClimateData(dailyData)
      const latestValue = (values) =>
        Object.values(values)
          .filter((value) => value !== -999)
          .at(-1)

      setTemperature(`${latestValue(parameters.T2M)} °C`)
      setHumidity(`${latestValue(parameters.RH2M)} %`)
      setSolarRadiation(
        `${latestValue(parameters.ALLSKY_SFC_SW_DWN)} kWh/m²/day`
      )

      const rainValues = Object.values(parameters.PRECTOTCORR)
        .filter((value) => value !== -999)
        .slice(-7)

      const totalRain = rainValues.reduce(
        (total, value) => total + value,
        0
      )

      setRainfall(`${totalRain.toFixed(1)} mm (7-day total)`)
      localStorage.setItem(
        'agroverseClimate',
        JSON.stringify({
          temperature: `${latestValue(parameters.T2M)} °C`,
          humidity: `${latestValue(parameters.RH2M)} %`,
          solarRadiation: `${latestValue(parameters.ALLSKY_SFC_SW_DWN)} kWh/m²/day`,
          rainfall: `${totalRain.toFixed(1)} mm (7-day total)`,
        }),
      )
      setClimateMessage({ kind: 'success', date: endDate })
    } catch (error) {
      setClimateMessage({ kind: 'error' })
    }
  }

  const handleCheckSoilPH = async () => {
    if (soilPH === "" || Number(soilPH) < 0 || Number(soilPH) > 14) {
      setSoilPHError("invalid");
      return;
    }

    setSoilPHLoading(true);
    setSoilPHError("");
    setSoilPHResult(null);

    try {
      const response = await fetch("http://localhost:8000/api/soil-ph", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          ph: Number(soilPH),
        }),
      });

      if (!response.ok) {
        throw new Error("Soil analysis failed.");
      }

      const data = await response.json();
      setSoilPHResult(data);
    } catch (error) {
      setSoilPHError("backend");
    } finally {
      setSoilPHLoading(false);
    }
  };

  return (
    <div className="app">
      {/* 🟢 ৪. পেজ সুইচিং লজিক */}
      {currentPage === 'home' && (
        <LandingPage 
          onGetStarted={() => setCurrentPage('signup')} 
          onLoginClick={() => setCurrentPage('login')} 
        />
      )}

      {currentPage === 'login' && (
        <Login
          onLogin={(loggedInUser) => {
            setUser(loggedInUser)
            setCurrentPage('dashboard')
          }}
          onSignupClick={() => setCurrentPage('signup')}
        />
      )}

      {currentPage === 'signup' && (
        <Signup
          onSignedUp={(newUser) => {
            setUser(newUser)
            setCurrentPage('dashboard')
          }}
          onLoginClick={() => setCurrentPage('login')}
        />
      )}

      {currentPage === 'dashboard' && user && (
        <>
          <aside className="sidebar">
            <h2>🌱 AGROVERSE AI</h2>
            <p>{t('sidebar.tagline')}</p>

            <nav>
              <a href="#dashboard" className="active">🏠 {t('nav.dashboard')}</a>
              <a
                href="#crop-recommendation"
                onClick={() => setActiveMenu('crop-recommendation')}
                className="active"
              >
                🌾 {t('nav.cropRecommendation')}
              </a>
              <a
                href="#crop-rotation"
                onClick={() => setActiveMenu('crop-rotation')}
                className="active"
              >
                🔄 {t('nav.cropRotation')}
              </a>
              <a
                href="#climate-insights"
                onClick={() => setActiveMenu('climate-insights')}
                className="active"
              >
                🌦️ {t('nav.climateInsights')}
              </a>
              <a href="#farm-map" className="active">
                📍 {t('nav.farmMap')}
              </a>
              <a href="#ai-advisor" className="active">
                🤖 {t('nav.aiAdvisor')}
              </a>
            </nav>

            <h3>{t('sidebar.growSmart1')}<br />{t('sidebar.growSmart2')}</h3>
          </aside> 

          <main className="dashboard">
            {/* Header / Profile Dropdown Section */}
            <header className="dashboard-header" style={{ display: 'flex', justifyContent: 'flex-end', position: 'relative', marginBottom: '20px' }}>
              <div style={{ display: 'flex', alignItems: 'center', marginRight: '12px' }}>
                <LanguageSwitcher />
              </div>
              <div className="profile-container" ref={dropdownRef} style={{ position: 'relative' }}>
                <button 
                  className="profile-icon-btn" 
                  onClick={() => setIsProfileOpen(!isProfileOpen)}
                  style={{
                    background: '#22c55e',
                    border: 'none',
                    borderRadius: '50%',
                    width: '45px',
                    height: '45px',
                    fontSize: '20px',
                    cursor: 'pointer',
                    color: '#fff',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    boxShadow: '0 2px 8px rgba(0,0,0,0.15)'
                  }}
                >
                  👨‍🌾
                </button>

                {isProfileOpen && (
                  <div 
                    className="profile-dropdown"
                    style={{
                      position: 'absolute',
                      right: 0,
                      top: '55px',
                      backgroundColor: '#ffffff',
                      border: '1px solid #e2e8f0',
                      borderRadius: '12px',
                      boxShadow: '0 10px 25px rgba(0,0,0,0.1)',
                      width: '220px',
                      zIndex: 1000,
                      padding: '12px',
                      color: '#1e293b'
                    }}
                  >
                    <div style={{ paddingBottom: '10px', borderBottom: '1px solid #f1f5f9' }}>
                      <p style={{ margin: 0, fontWeight: 'bold', fontSize: '15px' }}>
                        🌾 {t('profileMenu.myFarm')}
                      </p>
                      <small style={{ color: '#64748b' }}>
                        📍 {farmLocation || t('place.puruliaShort')}
                      </small>
                    </div>
                    <div style={{ paddingTop: '8px' }}>
                      <a 
                        href="#"
                        onClick={(e) => {
                          e.preventDefault()
                          setIsProfileOpen(false)
                          setIsProfileModalOpen(true)
                        }}
                        style={{
                          display: 'block',
                          padding: '8px 10px',
                          color: '#334155',
                          textDecoration: 'none',
                          borderRadius: '6px',
                          fontSize: '14px',
                          marginBottom: '4px',
                          transition: 'background 0.2s'
                        }}
                      >
                        🌱 {t('profileMenu.viewProfile')}
                      </a>
                      <button 
                        onClick={handleLogout}
                        style={{
                          width: '100%',
                          textAlign: 'left',
                          padding: '8px 10px',
                          background: '#ef4444',
                          color: '#ffffff',
                          border: 'none',
                          borderRadius: '6px',
                          cursor: 'pointer',
                          fontSize: '14px',
                          fontWeight: 'bold'
                        }}
                      >
                        🚪 {t('profileMenu.logout')}
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </header>

            <section className="welcome">
              <div className="welcome-text">
                <h1>🌱 {t('welcome.titleName', { name: user?.name })}</h1>
                <p>{t('welcome.subtitle')}</p>

                <div className="farm-location-badge">
                  📍 {t('place.purulia')}
                </div>
              </div>

              <div className="welcome-illustration">
                <img
                  src="https://cdn-icons-png.flaticon.com/512/2909/2909760.png"
                  alt={t('welcome.illustrationAlt')}
                />
              </div>
            </section>

            <section className="features">
              <div className="feature-card feature-card-link" {...goTo('crop-recommendation')}>
                <h3>🌾 {t('nav.cropRecommendation')}</h3>
                <p>{t('featureCards.cropRecText')}</p>
              </div>

              <div className="feature-card feature-card-link" {...goTo('climate-insights')}>
                <h3>🌦️ {t('nav.climateInsights')}</h3>
                <p>{t('featureCards.climateText')}</p>
              </div>

              <div className="feature-card feature-card-link" {...goTo('crop-rotation')}>
                <h3>🔄 {t('nav.cropRotation')}</h3>
                <p>{t('featureCards.rotationText')}</p>
              </div>

              <div className="feature-card feature-card-link" {...goTo('ai-advisor')}>
                <h3>🤖 {t('advisor.title')}</h3>
                <p>{t('featureCards.advisorText')}</p>
              </div>

              <h2 id="dashboard" className="overview-title">{t('dash.overviewTitle')}</h2>

              <div className="dashboard-grid">
                <div className="dashboard-card">
                  <div className="card-icon">🌱</div>
                  <h3>{t('dash.overviewTitle')}</h3>
                  <p>📍 {farmLocation || t('dash.locationNotSet')}</p>
                  <p>🌱 {farmSoil ? tSoil(farmSoil) : t('dash.soilNotSet')}</p>
                  <p>📏 {landArea ? t('dash.acres', { value: landArea }) : t('dash.areaNotSet')}</p>
                </div>

                <div className="dashboard-card">
                  <div className="card-icon">🌦️</div>
                  <h3>{t('dash.climateStatus')}</h3>
                  <p>🌡️ {t('climate.temperature')}: {showData(temperature)} °C</p>
                  <p>🌧️ {t('climate.rainfall')}: {showRain(rainfall)} mm/day</p>
                  <p>💧 {t('climate.humidity')}: {showData(humidity)} %</p>
                </div>

                <div className="dashboard-card">
                  <div className="card-icon">🔄</div>
                  <h3>{t('nav.cropRotation')}</h3>
                  <p>🌾 {t('dash.nextCrop')}: {nextCrop ? tCrop(nextCrop) : t('dash.notPlanned')}</p>
                  <p>🌱 {t('dash.followingCrop')}: {followingCrop ? tCrop(followingCrop) : t('dash.notPlanned')}</p>
                </div>

                <div className="dashboard-card">
                  <div className="card-icon">🤖</div>
                  <h3>{t('advisor.title')}</h3>
                  <p>
                    {advisorAnswer
                      ? t('dash.advisorAvailable')
                      : t('dash.advisorReady')}
                  </p>
                </div>
              </div>
            </section>

            <section className="soil-ph-section">
              <h2>{t('soil.title')}</h2>
              <p>{t('soil.subtitle')}</p>

              <div className="soil-ph-form">
                <input
                  type="number"
                  min="0"
                  max="14"
                  step="0.1"
                  placeholder={t('soil.placeholder')}
                  value={soilPH}
                  onChange={(e) => setSoilPH(e.target.value)}
                />

                <button
                  onClick={handleCheckSoilPH}
                  disabled={soilPHLoading || soilPH === ""}
                >
                  {soilPHLoading ? t('soil.checking') : t('soil.check')}
                </button>
              </div>

              {soilPHError && (
                <p className="soil-ph-error">{t('soil.error_' + soilPHError)}</p>
              )}

              {soilPHResult && (
                <div className="soil-ph-result">
                  <h3>{t('soil.resultTitle')}</h3>
                  <p>{t('soil.ph')}: {soilPHResult.ph}</p>
                  <p>{t('soil.condition')}: {soilPHResult.condition}</p>
                  <p>{t('soil.suitableCrops')}: {soilPHResult.suitableCrops}</p>
                  <p>{t('soil.improvement')}: {soilPHResult.improvementTips}</p>
                </div>
              )}
            </section>  

            <section className="farm-dashboard">
              <h2>{t('farmDash.title')}</h2>
              <p>{t('farmDash.subtitle')}</p>

              <div className="dashboard-stats">
                <div className="feature-card">
                  <h3>🌱 {t('farmDash.area')}</h3>
                  <h2>{landArea ? t('dash.acres', { value: landArea }) : t('farmDash.notSet')}</h2>
                  <p>{landArea ? `📍 ${farmLocation}` : t('farmDash.addDetails')}</p>
                </div>

                <div className="feature-card">
                  <h3>🌾 {t('farmDash.currentCrop')}</h3>
                  <h2>{currentCrop ? tCrop(currentCrop) : t('farmDash.notSelected')}</h2>
                  <p>{t('farmDash.chooseCrop')}</p>
                </div>

                <div className="feature-card">
                  <h3>🌱 {t('farmDash.soilType')}</h3>
                  <h2>{farmSoil ? tSoil(farmSoil) : t('farmDash.notSelected')}</h2>
                  <p>{t('farmDash.soilInfo')}</p>
                </div>

                <div className="feature-card">
                  <h3>🌦️ {t('dash.climateStatus')}</h3>
                  <h2>{showData(temperature)}</h2>
                  <p>{temperature === 'Awaiting Data' ? t('farmDash.loadingClimate') : t('farmDash.latestClimate')}</p>
                </div>

                <div className="feature-card">
                  <h3>🌧️ {t('climate.rainfall')}</h3>
                  <h2>{showRain(rainfall)}</h2>
                  <p>{t('farmDash.rain7')}</p>
                </div>

                <div className="feature-card">
                  <h3>💧 {t('climate.humidity')}</h3>
                  <h2>{showData(humidity)}</h2>
                  <p>{t('farmDash.relHumidity')}</p>
                </div>

                <div className="feature-card">
                  <h3>☀️ {t('climate.solar')}</h3>
                  <h2>{showData(solarRadiation)}</h2>
                  <p>{t('farmDash.dailySolar')}</p>
                </div>

                <div className="feature-card">
                  <h3>🔄 {t('farmDash.nextRotation')}</h3>
                  <h2>{nextCrop ? tCrop(nextCrop) : t('dash.notPlanned')}</h2>
                  <p>{t('dash.followingCrop')}: {followingCrop ? tCrop(followingCrop) : t('dash.notPlanned')}</p>
                </div>
              </div>
            </section>


            <CropRecommendation />

            <CropRotation />

            <section className="climate-insights">
              <h2 id="climate-insights">{t('climate.title')}</h2>
              <p>{t('climate.subtitle')}</p>

              <button onClick={getClimateData}>
                {t('climate.load')}
              </button>

              {climateMessage && (
                <p>
                  {climateMessage.kind === 'loading'
                    ? t('climate.loading')
                    : climateMessage.kind === 'success'
                      ? t('climate.loaded', { date: climateMessage.date.toLocaleDateString(dateLocale) })
                      : t('climate.error')}
                </p>
              )}

              <p className="last-updated">
                {t('climate.lastUpdated')}: {new Date().toLocaleDateString(dateLocale)}
              </p>

              <div className="dashboard-stats climate-graphs">
                {/* Temperature */}
                <div className="feature-card climate-chart">
                  <h3>🌡️ {t('climate.temperature')}</h3>
                  <ResponsiveContainer width="100%" height={250}>
                    <LineChart data={climateGraphData}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="month" tickFormatter={formatMonth} />
                      <YAxis />
                      <Tooltip labelFormatter={formatMonth} formatter={(value) => [`${value} °C`, t('climate.temperature')]} />
                      <Line type="monotone" dataKey="temperature" stroke="#16a34a" strokeWidth={3} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>

                {/* Rainfall */}
                <div className="feature-card climate-chart">
                  <h3>🌧️ {t('climate.rainfall')}</h3>
                  <ResponsiveContainer width="100%" height={250}>
                    <LineChart data={climateGraphData}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="month" tickFormatter={formatMonth} />
                      <YAxis />
                      <Tooltip labelFormatter={formatMonth} formatter={(value) => [`${value} mm`, t('climate.rainfall')]} />
                      <Line type="monotone" dataKey="rainfall" stroke="#0284c7" strokeWidth={3} dot={{ r: 4 }} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>

                {/* Humidity */}
                <div className="feature-card climate-chart">
                  <h3>💧 {t('climate.humidity')}</h3>
                  <ResponsiveContainer width="100%" height={250}>
                    <LineChart data={climateGraphData}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="month" tickFormatter={formatMonth} />
                      <YAxis />
                      <Tooltip labelFormatter={formatMonth} formatter={(value) => [`${value} %`, t('climate.humidity')]} />
                      <Line type="monotone" dataKey="humidity" stroke="#0ea5e9" strokeWidth={3} dot={{ r: 4 }} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>

                {/* Solar Radiation */}
                <div className="feature-card climate-chart">
                  <h3>☀️ {t('climate.solar')}</h3>
                  <ResponsiveContainer width="100%" height={250}>
                    <LineChart data={climateGraphData}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="month" tickFormatter={formatMonth} />
                      <YAxis />
                      <Tooltip labelFormatter={formatMonth} formatter={(value) => [`${value} kWh/m²/day`, t('climate.solar')]} />
                      <Line type="monotone" dataKey="solar" stroke="#f59e0b" strokeWidth={3} dot={{ r: 4 }} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </section>

            <section className="farm-map">
              <h2 id="farm-map">{t('map.title')}</h2>
              <p>{t('map.subtitle')}</p>

              <div className="farm-map-card">
                <div className="farm-map-header">
                  <div>
                    <h3>🌿 {t('map.cardTitle')}</h3>
                    <p>{t('map.view')}</p>
                  </div>
                  <span className="map-live-badge">● {t('map.live')}</span>
                </div>

                <MapContainer
                  center={FARM_MAP_VIEW.center}
                  zoom={FARM_MAP_VIEW.zoom}
                  scrollWheelZoom={true}
                  className="farm-leaflet-map"
                >
                  <TileLayer
                    attribution='Tiles © Esri'
                    url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
                  />
                  <FarmDraw />
                  <Marker position={FARM_MAP_VIEW.markerPosition}>
                    <Popup>
                      🌱 {t('map.popup')}
                    </Popup>
                  </Marker>

                  <Polygon
                    positions={FARM_MAP_VIEW.polygon}
                    pathOptions={{
                      color: '#22c55e',
                      fillColor: '#4ade80',
                      fillOpacity: 0.25,
                      weight: 3
                    }}
                  />
                </MapContainer>

                <div className="farm-map-footer">
                  <span>📍 {t('place.puruliaIndia')}</span>
                  <span>🛰️ {t('map.imagery')}</span>
                </div>
              </div>
            </section>

            <section className="farm-ai-insights">
              <h2>🤖 {t('insights.title')}</h2>
              <p className="farm-ai-subtitle">
                {t('insights.subtitle')}
              </p>

              <div className="farm-ai-grid">
                {/* NDVI */}
                <div className="farm-ai-card">
                  <span className="farm-ai-icon">🌱</span>
                  <h3>{t('insights.ndviTitle')}</h3>
                  <p>{t('insights.ndviText')}</p>

                  <div className="ndvi-visual">
                    <div className="ndvi-gradient"></div>
                    <div className="ndvi-labels">
                      <span>{t('insights.low')}</span>
                      <span>{t('insights.moderate')}</span>
                      <span>{t('insights.healthy')}</span>
                    </div>
                  </div>

                  <div className="analysis-status">
                    <span className="status-dot"></span>
                    {t('insights.waitingSat')}
                  </div>
                </div>

                {/* Crop Health */}
                <div className="farm-ai-card">
                  <span className="farm-ai-icon">🛰️</span>
                  <h3>{t('insights.healthTitle')}</h3>
                  <p>{t('insights.healthText')}</p>

                  <div className="crop-health-preview">
                    <div className="health-cell health-1"></div>
                    <div className="health-cell health-2"></div>
                    <div className="health-cell health-3"></div>
                    <div className="health-cell health-4"></div>
                    <div className="health-cell health-5"></div>
                    <div className="health-cell health-6"></div>
                    <div className="health-cell health-7"></div>
                    <div className="health-cell health-8"></div>
                    <div className="health-cell health-9"></div>
                  </div>

                  <div className="analysis-status">
                    <span className="status-dot"></span>
                    {t('insights.waitingHealth')}
                  </div>
                </div>

                {/* Water Stress */}
                <div className="farm-ai-card">
                  <span className="farm-ai-icon">💧</span>
                  <h3>{t('insights.waterTitle')}</h3>
                  <p>{t('insights.waterText')}</p>

                  <div className="water-stress-visual">
                    <div className="water-stress-bar">
                      <div className="water-stress-fill"></div>
                    </div>
                    <div className="water-stress-labels">
                      <span>{t('insights.low')}</span>
                      <span>{t('insights.moderate')}</span>
                      <span>{t('insights.high')}</span>
                    </div>
                  </div>

                  <div className="analysis-status">
                    <span className="status-dot"></span>
                    {t('insights.waitingWater')}
                  </div>
                </div>
              </div>
            </section> 

            <section className="ai-advisor">
              <h2 id="ai-advisor">{t('advisor.title')}</h2>
              <p>{t('advisor.subtitle')}</p>

              <div className="profile-card">
                <h3>🤖 {t('advisor.cardTitle')}</h3>

                <textarea
                  placeholder={t('advisor.placeholder')}
                  rows="4"
                  value={advisorQuestion}
                  onChange={(e) => setAdvisorQuestion(e.target.value)}
                />

                <button onClick={askAdvisor} disabled={isAdvisorLoading}>
                  {isAdvisorLoading ? t('advisor.thinking') : t('advisor.ask')}
                </button>

                {advisorAnswer && (
                  <p className={advisorAnswer.kind === 'empty' ? 'advisor-warning' : ''}>
                    {advisorAnswer.kind === 'empty'
                      ? `⚠️ ${t('advisor.empty')}`
                      : t('advisor.answer', { question: advisorAnswer.question })}
                  </p>
                )}
              </div>
            </section>
          </main>

          {isProfileModalOpen && (
            <ProfileModal
              user={user}
              onClose={() => setIsProfileModalOpen(false)}
              onSaved={(updatedUser) => setUser(updatedUser)}
            />
          )}
        </>
      )}
    </div>
  )
}

export default App