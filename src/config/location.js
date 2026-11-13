// The farm location is fixed to Purulia for now. Farmers cannot change it.
// Later this can come from the farmer's profile - every place in the app reads it from here.
export const FARM_LOCATION = {
  name: 'Purulia, West Bengal',
  lat: 23.3316,
  lng: 86.3759,
}

// Values used by the Farm Map section (same view the site had before).
export const FARM_MAP_VIEW = {
  center: [23.332, 86.365],
  zoom: 13,
  markerPosition: [23.332, 86.365],
  polygon: [
    [23.334, 86.363],
    [23.335, 86.367],
    [23.331, 86.369],
    [23.329, 86.365],
  ],
}
