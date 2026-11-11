import './App.css'
import { useState } from 'react'
import { useEffect } from 'react'
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

const cropCategories = [
  {
    name: "🌾 Cereals / দানাশস্য",
    crops: [
      { en: "Rice", bn: "ধান" },
      { en: "Wheat", bn: "গম" },
      { en: "Maize", bn: "ভুট্টা" },
      { en: "Millet", bn: "বাজরা" },
      { en: "Barley", bn: "যব" },
      { en: "Sorghum", bn: "জোয়ার" }
    ]
  },
  {
    name: "🫘 Pulses / ডাল",
    crops: [
      { en: "Lentil", bn: "মসুর" },
      { en: "Chickpea", bn: "ছোলা" },
      { en: "Green Gram", bn: "মুগ" },
      { en: "Black Gram", bn: "উড়দ" },
      { en: "Pea", bn: "মটর" }
    ]
  },
  {
    name: "🛢️ Oilseeds / তৈলবীজ",
    crops: [
      { en: "Mustard", bn: "সরিষা" },
      { en: "Groundnut", bn: "চিনাবাদাম" },
      { en: "Sesame", bn: "তিল" },
      { en: "Sunflower", bn: "সূর্যমুখী" },
      { en: "Soybean", bn: "সয়াবিন" }
    ]
  },
  {
    name: "🥬 Vegetables / সবজি",
    crops: [
      { en: "Potato", bn: "আলু" },
      { en: "Onion", bn: "পেঁয়াজ" },
      { en: "Tomato", bn: "টমেটো" },
      { en: "Brinjal", bn: "বেগুন" },
      { en: "Cucumber", bn: "শসা" },
      { en: "Pointed Gourd", bn: "পটল" },
      { en: "Cauliflower", bn: "ফুলকপি" },
      { en: "Chili", bn: "লঙ্কা" },
      { en: "Carrot", bn: "গাজর" },
      { en: "Cabbage", bn: "বাঁধাকপি" },
      { en: "Okra", bn: "ঢেঁড়স" },
      { en: "Radish", bn: "মুলা" },
      { en: "Spinach", bn: "পালং" },
      { en: "Pumpkin", bn: "কুমড়ো" },
      { en: "Watermelon", bn: "তরমুজ" }
    ]
  },
  {
    name: "🍎 Fruits / ফল",
    crops: [
      { en: "Mango", bn: "আম" },
      { en: "Banana", bn: "কলা" },
      { en: "Papaya", bn: "পেঁপে" },
      { en: "Guava", bn: "পেয়ারা" },
      { en: "Pineapple", bn: "আনারস" }
    ]
  },
  {
    name: "🧵 Fiber Crops / আঁশ ফসল",
    crops: [
      { en: "Jute", bn: "পাট" },
      { en: "Cotton", bn: "তুলা" }
    ]
  }
];

function App() {
  // 🟢 ১. লগইন স্ট্যাটাস চেক করার জন্য নতুন স্টেট
  const [isLoggedIn, setIsLoggedIn] = useState(false)

  const [activeMenu, setActiveMenu] = useState('dashboard')
  const [profileMessage, setProfileMessage] = useState('')
  const [soil, setSoil] = useState('')
  const [water, setWater] = useState('')
  const [recommendation, setRecommendation] = useState('')
  const [rotationSaved, setRotationSaved] = useState(false)
  const [isLoadingRecommendation, setIsLoadingRecommendation] = useState(false)
  const [advisorQuestion, setAdvisorQuestion] = useState('')
  const [advisorAnswer, setAdvisorAnswer] = useState('')
  const [isAdvisorLoading, setIsAdvisorLoading] = useState(false)
  const [farmName, setFarmName] = useState('')
  const [farmLocation, setFarmLocation] = useState('')
  const [landArea, setLandArea] = useState('')
  const [farmSoil, setFarmSoil] = useState('')
  const [currentCrop, setCurrentCrop] = useState('')
  const [nextCrop, setNextCrop] = useState('Pulses')
  const [followingCrop, setFollowingCrop] = useState('Vegetables')
  const [selectedCrops, setSelectedCrops] = useState([]);
  const [rotationResult, setRotationResult] = useState(null);
  const [soilPH, setSoilPH] = useState("");
  const [soilPHResult, setSoilPHResult] = useState(null);
  const [soilPHLoading, setSoilPHLoading] = useState(false);
  const [soilPHError, setSoilPHError] = useState("");
  const [temperature, setTemperature] = useState('Awaiting Data')

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

  const [rainfall, setRainfall] = useState('Awaiting Data')
  const [humidity, setHumidity] = useState('Awaiting Data')
  const [solarRadiation, setSolarRadiation] = useState('Awaiting Data')
  const [climateMessage, setClimateMessage] = useState('')
  const latitude = 23.3316
  const longitude = 86.3759

  useEffect(() => {
    const savedFarm = localStorage.getItem('agroverseFarm')

    if (savedFarm) {
      const farm = JSON.parse(savedFarm)

      setFarmName(farm.farmName || '')
      setFarmLocation(farm.farmLocation || '')
      setLandArea(farm.landArea || '')
      setFarmSoil(farm.farmSoil || '')
      setCurrentCrop(farm.currentCrop || '')
      setNextCrop(farm.nextCrop || 'Pulses')
      setFollowingCrop(farm.followingCrop || 'Vegetables')
    }
    const savedRotation = localStorage.getItem('agroverseRotation')

    if (savedRotation) {
      const rotation = JSON.parse(savedRotation)
      setNextCrop(rotation.nextCrop)
      setFollowingCrop(rotation.followingCrop)
      setRotationSaved(true)
    }
  }, [])

  const askAdvisor = () => {
    setIsAdvisorLoading(true)
    if (!advisorQuestion.trim()) {
      setAdvisorAnswer('⚠️ Please write your farming question first.')
      setIsAdvisorLoading(false)
      return
    }

    setAdvisorAnswer(
      'Your question: ' +
        advisorQuestion +
        ' — AI Advisor connection will be added soon!'
    )
    setIsAdvisorLoading(false)
  }

  const [climateGraphData, setClimateGraphData] = useState([])
  const [selectedMonth, setSelectedMonth] = useState('all')
  const [dailyClimateData, setDailyClimateData] = useState([])

  const getClimateData = async () => {
    try {
      setClimateMessage('Loading NASA climate data...')

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
        month: new Date(
          Number(month.slice(0, 4)),
          Number(month.slice(4, 6)) - 1
        ).toLocaleDateString('en-US', {
          month: 'short',
          year: 'numeric'
        }),
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
      localStorage.setItem(
        'agroverseClimate',
        JSON.stringify({
          temperature: `${latestValue(parameters.T2M)} °C`,
          humidity: `${latestValue(parameters.RH2M)} %`,
          solarRadiation: `${latestValue(parameters.ALLSKY_SFC_SW_DWN)} kWh/m²/day`,
        }),
      )
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
      setClimateMessage(
        `NASA climate data loaded successfully! Date: ${endDate.toLocaleDateString('en-GB')}`
      )
     
    } catch (error) {
      setClimateMessage('Unable to load climate data. Please try again.')
    }
  }

  const getRecommendation = async () => {
    setIsLoadingRecommendation(true)
    await new Promise(resolve => setTimeout(resolve, 1500))
    if (!soil || !water) {
      setRecommendation('⚠️ Please select both Soil Type and Water Availability before getting recommendations.')
      setIsLoadingRecommendation(false)
      return
    }

    if (soil === 'Loamy Soil' && water === 'High') {
      setRecommendation('Rice, Maize and Vegetables may be suitable.')
    } else if (soil === 'Sandy Soil' && water === 'Low') {
      setRecommendation('Millet and Pulses may be suitable.')
    } else if (soil === 'Clay Soil') {
      setRecommendation('Rice and Wheat may be suitable.')
    } else {
      setRecommendation('Maize, Pulses and suitable seasonal crops may be considered.')
    }
    setIsLoadingRecommendation(false)
  }

  const handleCheckSoilPH = async () => {
    if (soilPH === "" || Number(soilPH) < 0 || Number(soilPH) > 14) {
      setSoilPHError("Enter a valid pH between 0 and 14.");
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
      setSoilPHError(
        "Unable to analyze soil. Backend connection is not available."
      );
    } finally {
      setSoilPHLoading(false);
    }
  };

  return (
    <div className="app">
      {/* 🟢 ২. যদি লগইন না করা থাকে (!isLoggedIn), তবে শুধু Login পেজ দেখাবে। 
          লগইন বাটনে চাপ দিলে `onLogin` প্রপসের মাধ্যমে `isLoggedIn` true হয়ে যাবে এবং ড্যাশবোর্ড স্ক্রিন খুলবে। */}
      {!isLoggedIn ? (
        <Login onLogin={() => setIsLoggedIn(true)} />
      ) : (
        <>
          <aside className="sidebar">
            <h2>🌱 AGROVERSE AI</h2>
            <p>Smart Farming, Better Tomorrow.</p>

            <nav>
              <a href="#dashboard" className="active">🏠 Dashboard</a>
              <a href="#farm-profile" className="active">🌱 Farm Profile</a>
              <a
                href="#crop-recommendation"
                onClick={() => setActiveMenu('crop-recommendation')}
                className="active"
              >
                🌾 Crop Recommendation
              </a>
              <a
                href="#climate-insights"
                onClick={() => setActiveMenu('climate-insights')}
                className="active"
              >
                🌦️ Climate Insights
              </a>
              <a
                href="#crop-rotation"
                onClick={() => setActiveMenu('crop-rotation')}
                className="active"
              >
                🔄 Crop Rotation
              </a>
              <a href="#farm-map" className="active">
                📍 Farm Map
              </a>
              <a href="#ai-advisor" className="active">
                🤖 AI Advisor
              </a>
            </nav>

            <h3>Grow Smart<br />Grow Green</h3>
          </aside> 

          <main className="dashboard">
            <section className="welcome">
              <div className="welcome-text">
                <h1>🌱 Welcome back, Farmer!</h1>
                <p>Let's grow a greener future together 🌱</p>

                <div className="farm-location-badge">
                  📍 Purulia, West Bengal
                </div>
              </div>

              <div className="welcome-illustration">
                <img
                  src="https://cdn-icons-png.flaticon.com/512/2909/2909760.png"
                  alt="Farm illustration"
                />
              </div>
            </section>

            <section className="features">
              <div className="feature-card">
                <h3>🌾 Crop Recommendation</h3>
                <p>Discover suitable crops for your farm.</p>
              </div>

              <div className="feature-card">
                <h3>🌦️ Climate Insights</h3>
                <p>Understand weather and climate patterns.</p>
              </div>

              <div className="feature-card">
                <h3>🔄 Crop Rotation</h3>
                <p>Plan smarter seasonal crop rotations.</p>
              </div>

              <div className="feature-card">
                <h3>🤖 AI Farming Advisor</h3>
                <p>Get intelligent farming guidance.</p>
              </div>

              <h2 id="dashboard" className="overview-title">Farm Overview</h2>

              <div className="dashboard-grid">
                <div className="dashboard-card">
                  <div className="card-icon">🌱</div>
                  <h3>Farm Overview</h3>
                  <p>📍 {farmLocation || 'Location not set'}</p>
                  <p>🌱 {farmSoil || 'Soil not set'}</p>
                  <p>📏 {landArea ? `${landArea} acres` : 'Area not set'}</p>
                </div>

                <div className="dashboard-card">
                  <div className="card-icon">🌦️</div>
                  <h3>Climate Status</h3>
                  <p>🌡️ Temperature: {temperature} °C</p>
                  <p>🌧️ Rainfall: {rainfall} mm/day</p>
                  <p>💧 Humidity: {humidity} %</p>
                </div>

                <div className="dashboard-card">
                  <div className="card-icon">🔄</div>
                  <h3>Crop Rotation</h3>
                  <p>🌾 Next Crop: {nextCrop || 'Not planned'}</p>
                  <p>🌱 Following Crop: {followingCrop || 'Not planned'}</p>
                </div>

                <div className="dashboard-card">
                  <div className="card-icon">🤖</div>
                  <h3>AI Farming Advisor</h3>
                  <p>
                    {advisorAnswer
                      ? '✅ Advisor Response Available'
                      : '🤖 Ready to assist with farming questions.'}
                  </p>
                </div>
              </div>
            </section>

            <section className="soil-ph-section">
              <h2>Soil pH Checking</h2>
              <p>Enter your soil pH value to analyze soil condition.</p>

              <div className="soil-ph-form">
                <input
                  type="number"
                  min="0"
                  max="14"
                  step="0.1"
                  placeholder="Enter soil pH (0–14)"
                  value={soilPH}
                  onChange={(e) => setSoilPH(e.target.value)}
                />

                <button
                  onClick={handleCheckSoilPH}
                  disabled={soilPHLoading || soilPH === ""}
                >
                  {soilPHLoading ? "Checking..." : "Check Soil pH"}
                </button>
              </div>

              {soilPHError && (
                <p className="soil-ph-error">{soilPHError}</p>
              )}

              {soilPHResult && (
                <div className="soil-ph-result">
                  <h3>Soil Analysis Result</h3>
                  <p>pH: {soilPHResult.ph}</p>
                  <p>Condition: {soilPHResult.condition}</p>
                  <p>Suitable Crops: {soilPHResult.suitableCrops}</p>
                  <p>Soil Improvement: {soilPHResult.improvementTips}</p>
                </div>
              )}
            </section>  

            <section className="farm-dashboard">
              <h2>Farm Dashboard</h2>
              <p>Your agricultural overview at a glance.</p>

              <div className="dashboard-stats">
                <div className="feature-card">
                  <h3>🌱 Farm Area</h3>
                  <h2>{farmName || 'Not set'}</h2>
                  <p>{landArea ? `${landArea} acres` : 'Add your farm details'}</p>
                </div>

                <div className="feature-card">
                  <h3>🌾 Current Crop</h3>
                  <h2>{currentCrop || 'Not selected'}</h2>
                  <p>Choose your crop</p>
                </div>

                <div className="feature-card">
                  <h3>🌱 Soil Type</h3>
                  <h2>{farmSoil || 'Not selected'}</h2>
                  <p>Your farm soil information</p>
                </div>

                <div className="feature-card">
                  <h3>🌦️ Climate Status</h3>
                  <h2>{temperature}</h2>
                  <p>{temperature === 'Awaiting Data' ? 'Loading climate data...' : 'Latest climate data available'}</p>
                </div>

                <div className="feature-card">
                  <h3>🌧️ Rainfall</h3>
                  <h2>{rainfall}</h2>
                  <p>7-day rainfall total</p>
                </div>

                <div className="feature-card">
                  <h3>💧 Humidity</h3>
                  <h2>{humidity}</h2>
                  <p>Relative humidity</p>
                </div>

                <div className="feature-card">
                  <h3>☀️ Solar Radiation</h3>
                  <h2>{solarRadiation}</h2>
                  <p>Daily solar radiation</p>
                </div>

                <div className="feature-card">
                  <h3>🔄 Next Rotation</h3>
                  <h2>{nextCrop || 'Not planned'}</h2>
                  <p>Following Crop: {followingCrop || 'Not planned'}</p>
                </div>
              </div>
            </section>

            <section className="farm-profile">
              <h2 id="farm-profile">Farm Profile</h2>
              <p>Keep your farm information organized.</p>

              <div className="profile-card">
                <h3>🌱 Your Farm Information</h3>

                <label>Farm Name</label>
                <input
                  type="text"
                  placeholder="Enter farm name"
                  value={farmName}
                  onChange={(e) => setFarmName(e.target.value)}
                />

                <label>Farm Location</label>
                <input
                  type="text"
                  placeholder="Enter farm location"
                  value={farmLocation}
                  onChange={(e) => setFarmLocation(e.target.value)}
                />

                <label>Land Area (in acres)</label>
                <input
                  type="number"
                  placeholder="Enter land area"
                  value={landArea}
                  onChange={(e) => setLandArea(e.target.value)}
                />

                <label>Soil Type</label>
                <select
                  value={farmSoil}
                  onChange={(e) => setFarmSoil(e.target.value)}
                >
                  <option value="">Select Soil Type</option>
                  <option value="Clay Soil">Clay Soil</option>
                  <option value="Sandy Soil">Sandy Soil</option>
                  <option value="Loamy Soil">Loamy Soil</option>
                  <option value="Silty Soil">Silty Soil</option>
                </select>

                <label>Current Crop</label>
                <select
                  value={currentCrop}
                  onChange={(e) => setCurrentCrop(e.target.value)}
                >
                  <option value="">Select Current Crop</option>
                  <option value="Rice">Rice</option>
                  <option value="Wheat">Wheat</option>
                  <option value="Maize">Maize</option>
                  <option value="Millet">Millet</option>
                  <option value="Pulses">Pulses</option>
                  <option value="Vegetables">Vegetables</option>
                </select>

                <button
                  onClick={() => {
                    localStorage.setItem(
                      'agroverseFarm',
                      JSON.stringify({
                        farmName,
                        farmLocation,
                        landArea,
                        farmSoil,
                        currentCrop,
                        nextCrop,
                        followingCrop,
                      })
                    )
                    setProfileMessage('✅ Farm Profile Saved Successfully!')
                  }}
                >
                  Save Farm Profile
                </button>

                {profileMessage && <p>{profileMessage}</p>}
              </div>
            </section>

            <section className="crop-recommendation">
              <h2 id="crop-recommendation">Crop Recommendation</h2>
              <p>Discover crops suitable for your farm.</p>

              <div className="profile-card">
                <h3>🌾 Find the Right Crop</h3>

                <label>Soil Type</label>
                <select value={soil} onChange={(e) => setSoil(e.target.value)}>
                  <option value="">Select Soil Type</option>
                  <option>Clay Soil</option>
                  <option>Sandy Soil</option>
                  <option>Loamy Soil</option>
                  <option>Silty Soil</option>
                </select>

                <label>Water Availability</label>
                <select value={water} onChange={(e) => setWater(e.target.value)}>
                  <option value="">Select Water Availability</option>
                  <option>Low</option>
                  <option>Medium</option>
                  <option>High</option>
                </select>

                <button onClick={getRecommendation} disabled={isLoadingRecommendation}>
                  {isLoadingRecommendation ? 'Loading...' : 'Get Crop Recommendation'}
                </button>

                {recommendation && (
                  <div className={`recommendation-result ${recommendation.startsWith('⚠️') ? 'recommendation-warning' : ''}`}>
                    <h3>🌱 Recommended Crops</h3>
                    <p>{recommendation}</p>
                  </div>
                )}
              </div>
            </section>

            <section className="crop-rotation">
              <h2 id="crop-rotation">🌱 AI Crop Rotation Planner</h2>
              <p>Choose 3 or more crops and get a smart rotation plan.</p>

              <div className="profile-card">
                <h3>🌾 Select Crops (English + বাংলা)</h3>

                {cropCategories.map((category) => (
                  <div key={category.name} className="crop-category">
                    <h4>{category.name}</h4>

                    <div className="crop-grid">
                      {category.crops.map((crop) => (
                        <button
                          key={crop.en}
                          type="button"
                          className={
                            selectedCrops.includes(crop.en)
                              ? "crop-option selected"
                              : "crop-option"
                          }
                          onClick={() =>
                            setSelectedCrops((prev) =>
                              prev.includes(crop.en)
                                ? prev.filter((c) => c !== crop.en)
                                : [...prev, crop.en]
                            )
                          }
                        >
                          {selectedCrops.includes(crop.en) ? "✅ " : "🌱 "}
                          {crop.en} ({crop.bn})
                        </button>
                      ))}
                    </div>
                  </div>
                ))}

                <p>
                  Selected Crops: <strong>{selectedCrops.length}</strong>
                </p>

                <button
                  type="button"
                  onClick={() => {
                    if (selectedCrops.length < 3) {
                      alert("Please select at least 3 crops!");
                      return;
                    }

                    setRotationResult(
                      "Selected crops: " + selectedCrops.join(" → ")
                    );
                  }}
                >
                  🤖 Generate Rotation Plan
                </button>

                {rotationResult && (
                  <div className="rotation-result">
                    <h3>🌿 Your Selected Rotation</h3>
                    <p>{rotationResult}</p>
                  </div>
                )}
              </div>
            </section>

            <section className="climate-insights">
              <h2 id="climate-insights">NASA Climate Insights</h2>
              <p>Explore climate information for smarter farming decisions.</p>

              <button onClick={getClimateData}>
                Load Climate Data
              </button>

              {climateMessage && <p>{climateMessage}</p>}

              <p className="last-updated">
                Last Updated: {new Date().toLocaleDateString('en-GB')}
              </p>

              <div className="dashboard-stats climate-graphs">
                {/* Temperature */}
                <div className="feature-card climate-chart">
                  <h3>🌡️ Temperature</h3>
                  <ResponsiveContainer width="100%" height={250}>
                    <LineChart data={climateGraphData}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="month" />
                      <YAxis />
                      <Tooltip formatter={(value) => [`${value} °C`, 'Temperature']} />
                      <Line type="monotone" dataKey="temperature" stroke="#16a34a" strokeWidth={3} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>

                {/* Rainfall */}
                <div className="feature-card climate-chart">
                  <h3>🌧️ Rainfall</h3>
                  <ResponsiveContainer width="100%" height={250}>
                    <LineChart data={climateGraphData}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="month" />
                      <YAxis />
                      <Tooltip formatter={(value) => [`${value} mm`, 'Rainfall']} />
                      <Line type="monotone" dataKey="rainfall" stroke="#0284c7" strokeWidth={3} dot={{ r: 4 }} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>

                {/* Humidity */}
                <div className="feature-card climate-chart">
                  <h3>💧 Humidity</h3>
                  <ResponsiveContainer width="100%" height={250}>
                    <LineChart data={climateGraphData}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="month" />
                      <YAxis />
                      <Tooltip formatter={(value) => [`${value} %`, 'Humidity']} />
                      <Line type="monotone" dataKey="humidity" stroke="#0ea5e9" strokeWidth={3} dot={{ r: 4 }} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>

                {/* Solar Radiation */}
                <div className="feature-card climate-chart">
                  <h3>☀️ Solar Radiation</h3>
                  <ResponsiveContainer width="100%" height={250}>
                    <LineChart data={climateGraphData}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="month" />
                      <YAxis />
                      <Tooltip formatter={(value) => [`${value} kWh/m²/day`, 'Solar Radiation']} />
                      <Line type="monotone" dataKey="solar" stroke="#f59e0b" strokeWidth={3} dot={{ r: 4 }} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </section>

            <section className="farm-map">
              <h2 id="farm-map">Farm Map</h2>
              <p>Explore your farmland across West Bengal.</p>

              <div className="farm-map-card">
                <div className="farm-map-header">
                  <div>
                    <h3>🌿 Purulia Farmland</h3>
                    <p>Satellite Agricultural View</p>
                  </div>
                  <span className="map-live-badge">● LIVE MAP</span>
                </div>

                <MapContainer
                  center={[23.332, 86.365]}
                  zoom={13}
                  scrollWheelZoom={true}
                  className="farm-leaflet-map"
                >
                  <TileLayer
                    attribution='Tiles © Esri'
                    url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
                  />
                  <FarmDraw />
                  <Marker position={[23.332, 86.365]}>
                    <Popup>
                      🌱 Purulia Farm Location
                    </Popup>
                  </Marker>

                  <Polygon
                    positions={[
                      [23.334, 86.363],
                      [23.335, 86.367],
                      [23.331, 86.369],
                      [23.329, 86.365]
                    ]}
                    pathOptions={{
                      color: '#22c55e',
                      fillColor: '#4ade80',
                      fillOpacity: 0.25,
                      weight: 3
                    }}
                  />
                </MapContainer>

                <div className="farm-map-footer">
                  <span>📍 Purulia, West Bengal, India</span>
                  <span>🛰️ Satellite Imagery</span>
                </div>
              </div>
            </section>

            <section className="farm-ai-insights">
              <h2>🤖 AI Farm Map Insights</h2>
              <p className="farm-ai-subtitle">
                Satellite-powered farmland monitoring
              </p>

              <div className="farm-ai-grid">
                {/* NDVI */}
                <div className="farm-ai-card">
                  <span className="farm-ai-icon">🌱</span>
                  <h3>Vegetation Health (NDVI)</h3>
                  <p>Satellite vegetation index for your selected farmland.</p>

                  <div className="ndvi-visual">
                    <div className="ndvi-gradient"></div>
                    <div className="ndvi-labels">
                      <span>Low</span>
                      <span>Moderate</span>
                      <span>Healthy</span>
                    </div>
                  </div>

                  <div className="analysis-status">
                    <span className="status-dot"></span>
                    Waiting for satellite analysis
                  </div>
                </div>

                {/* Crop Health */}
                <div className="farm-ai-card">
                  <span className="farm-ai-icon">🛰️</span>
                  <h3>Crop Health Visualization</h3>
                  <p>Spatial crop health information across your field.</p>

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
                    Waiting for crop health data
                  </div>
                </div>

                {/* Water Stress */}
                <div className="farm-ai-card">
                  <span className="farm-ai-icon">💧</span>
                  <h3>Water Stress Detection</h3>
                  <p>Satellite-based indication of possible water stress.</p>

                  <div className="water-stress-visual">
                    <div className="water-stress-bar">
                      <div className="water-stress-fill"></div>
                    </div>
                    <div className="water-stress-labels">
                      <span>Low</span>
                      <span>Moderate</span>
                      <span>High</span>
                    </div>
                  </div>

                  <div className="analysis-status">
                    <span className="status-dot"></span>
                    Waiting for water stress analysis
                  </div>
                </div>
              </div>
            </section> 

            <section className="ai-advisor">
              <h2 id="ai-advisor">AI Farming Advisor</h2>
              <p>Get helpful guidance for your farming decisions.</p>

              <div className="profile-card">
                <h3>🤖 Ask Your Farming Advisor</h3>

                <textarea
                  placeholder="Write your farming question here..."
                  rows="4"
                  value={advisorQuestion}
                  onChange={(e) => setAdvisorQuestion(e.target.value)}
                />

                <button onClick={askAdvisor} disabled={isAdvisorLoading}>
                  {isAdvisorLoading ? 'Thinking...' : 'Ask Advisor'}
                </button>

                {advisorAnswer && (
                  <p className={advisorAnswer.startsWith('⚠️') ? 'advisor-warning' : ''}>
                    {advisorAnswer}
                  </p>
                )}
              </div>
            </section>
          </main>
        </>
      )}
    </div>
  )
}

export default App