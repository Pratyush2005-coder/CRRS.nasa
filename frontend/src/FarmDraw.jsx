import { useEffect } from 'react'
import { useMap } from 'react-leaflet'
import L from 'leaflet'

export default function FarmDraw() {
  const map = useMap()

  useEffect(() => {
    const drawnItems = new L.FeatureGroup()
    map.addLayer(drawnItems)

    const drawControl = new L.Control.Draw({
      position: 'topleft',
      draw: {
        polygon: true,
        rectangle: false,
        polyline: false,
        circle: false,
        circlemarker: false,
        marker: false
      },
      edit: {
        featureGroup: drawnItems,
        remove: true
      }
    })

    map.addControl(drawControl)

    map.on(L.Draw.Event.CREATED, (event) => {
        drawnItems.addLayer(event.layer)

        const coordinates = event.layer
        .getLatLngs()[0]
        .map(point => ({
        lat: point.lat,
        lng: point.lng
    }))

    console.log('Farm Boundary Coordinates:', coordinates)
    })

    return () => {
      map.removeControl(drawControl)
      map.removeLayer(drawnItems)
    }
  }, [map])

  return null
}