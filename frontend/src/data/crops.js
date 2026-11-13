export const seasons = ["Kharif", "Rabi", "Zaid"];

export const seasonMeta = {
  Kharif: { emoji: "🌧️", label: "Kharif" },
  Rabi: { emoji: "❄️", label: "Rabi" },
  Zaid: { emoji: "☀️", label: "Zaid" }
};

export const cropOptions = [
  { en: "Rice", bn: "ধান" },
  { en: "Maize", bn: "ভুট্টা" },
  { en: "Ragi", bn: "রাগি" },
  { en: "Horse Gram", bn: "কুলথি" },
  { en: "Moth Bean", bn: "মটকি" },
  { en: "Peas / Beans", bn: "মটর / শিম" },
  { en: "Safflower", bn: "কুসুম" },
  { en: "Potato", bn: "আলু" },
  { en: "Tomato", bn: "টমেটো" },
  { en: "Brinjal", bn: "বেগুন" },
  { en: "Cucurbits", bn: "কুমড়াজাতীয়" },
  { en: "Cabbage", bn: "বাঁধাকপি" },
  { en: "Cauliflower", bn: "ফুলকপি" },
  { en: "Bhindi", bn: "ঢেঁড়স" },
  { en: "Onion", bn: "পেঁয়াজ" }
];

// Seasonal crop groups used by BOTH recommendation and rotation.
// A crop can belong to more than one season.
export const cropsBySeason = {
  Kharif: ["Rice", "Maize", "Ragi", "Horse Gram", "Moth Bean", "Peas / Beans", "Tomato", "Brinjal", "Cucurbits", "Bhindi", "Onion"],
  Rabi: ["Horse Gram", "Moth Bean", "Peas / Beans", "Safflower", "Potato", "Tomato", "Brinjal", "Cabbage", "Cauliflower", "Onion"],
  Zaid: ["Maize", "Ragi", "Peas / Beans", "Potato", "Tomato", "Brinjal", "Cucurbits", "Bhindi", "Onion"]
};

export const cropEmoji = {
  "Rice": "🍚", "Maize": "🌽", "Ragi": "🌾", "Horse Gram": "🫘",
  "Moth Bean": "🫘", "Peas / Beans": "🫛", "Safflower": "🌼", "Potato": "🥔",
  "Tomato": "🍅", "Brinjal": "🍆", "Cucurbits": "🥒", "Cabbage": "🥬",
  "Cauliflower": "🥦", "Bhindi": "🌿", "Onion": "🧅"
};

// Soil types used everywhere (profile, crop recommendation, crop rotation).
// Values stay in English, labels are translated.
export const soilTypeOptions = [
  "Sandy Clay Loam",
  "Clay",
  "Sandy Loam",
  "Loam",
  "Loamy Sand",
  "Clay Loam",
  "Don't know"
];

export const soilEmoji = {
  "Sandy Clay Loam": "🟫",
  "Clay": "🧱",
  "Sandy Loam": "🏖️",
  "Loam": "🌱",
  "Loamy Sand": "🏜️",
  "Clay Loam": "🪴",
  "Don't know": "❓"
};
