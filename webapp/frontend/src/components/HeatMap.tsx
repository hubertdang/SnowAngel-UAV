import { Fragment, useCallback, useEffect, useMemo, useRef } from 'react';
import { CircleMarker, MapContainer, Popup, TileLayer, Tooltip, useMap, useMapEvents } from 'react-leaflet';
import L, { LatLngBoundsExpression } from 'leaflet';
import 'leaflet/dist/leaflet.css';
import 'leaflet.heat';

import type { HeatPoint, MapBounds } from '../hooks/useHeatmapData';

const DEFAULT_POSITION: [number, number] = [45.4055, -75.692];
const DEFAULT_ZOOM = 15.25;
const CANAL_BOUNDS: LatLngBoundsExpression = [
  [45.383, -75.7115],
  [45.432, -75.6805],
];

interface HeatMapProps {
  points: HeatPoint[];
  onBoundsChange: (bounds: MapBounds) => void;
  availableDates: string[];
  selectedDate: string | null;
  formattedDate: string;
  onDateChange: (date: string | null) => void;
}

function extractBounds(map: L.Map): MapBounds {
  const bounds = map.getBounds();
  return {
    north: bounds.getNorth(),
    south: bounds.getSouth(),
    east: bounds.getEast(),
    west: bounds.getWest(),
  };
}

const formatTemperature = (value?: number | null) => {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return 'n/a';
  }
  return `${value.toFixed(1)}°C`;
};

const HeatLayer = ({ points }: { points: HeatPoint[] }) => {
  const map = useMap();

  useEffect(() => {
    if (!points.length) {
      return;
    }

    const minThickness = 20;
    const maxThickness = 45;
    const latlngs: Array<[number, number, number]> = points.map((point) => {
      const normalized = Math.max(
        0,
        Math.min(1, (point.thickness_cm - minThickness) / (maxThickness - minThickness))
      );
      return [point.lat, point.lng, 0.35 + normalized * 0.65];
    });

    const heatLayer = (L as typeof L & {
      heatLayer: (data: Array<[number, number, number]>, options?: Record<string, unknown>) => L.Layer;
    }).heatLayer(latlngs, {
      radius: 30,
      blur: 26,
      maxZoom: 17,
      gradient: {
        0.0: '#C62828',
        0.55: '#F9A825',
        1.0: '#2E7D32',
      },
    });

    heatLayer.addTo(map);
    return () => {
      map.removeLayer(heatLayer);
    };
  }, [map, points]);

  return null;
};

const BoundsWatcher = ({ onBoundsChange }: { onBoundsChange: (bounds: MapBounds) => void }) => {
  const map = useMapEvents({
    moveend: () => onBoundsChange(extractBounds(map)),
    zoomend: () => onBoundsChange(extractBounds(map)),
  });

  useEffect(() => {
    onBoundsChange(extractBounds(map));
  }, [map, onBoundsChange]);

  return null;
};

const MapInitializer = ({ points }: { points: HeatPoint[] }) => {
  const map = useMap();
  const hasCentered = useRef(false);

  useEffect(() => {
    const timer = setTimeout(() => {
      map.invalidateSize();
      if (!points.length || hasCentered.current) {
        if (!hasCentered.current) {
          map.fitBounds(L.latLngBounds(CANAL_BOUNDS).pad(0.003), { maxZoom: 16 });
        }
        return;
      }

      const bounds = L.latLngBounds(points.map((point) => [point.lat, point.lng] as [number, number]));
      const center = bounds.getCenter();
      const latSpan = Math.abs(bounds.getNorth() - bounds.getSouth());
      const lngSpan = Math.abs(bounds.getEast() - bounds.getWest());

      if (latSpan < 0.0003 && lngSpan < 0.0003) {
        map.setView(center, 17);
      } else {
        map.fitBounds(bounds.pad(0.01), { maxZoom: 17 });
      }
      hasCentered.current = true;
    }, 200);
    return () => clearTimeout(timer);
  }, [map, points]);

  return null;
};

const DataFocus = ({ points }: { points: HeatPoint[] }) => {
  const map = useMap();
  const focusedKey = useRef<string | null>(null);

  useEffect(() => {
    focusedKey.current = null;
  }, [points]);

  useEffect(() => {
    if (!points.length) {
      return;
    }
    const key = `${points[0]?.measured_at ?? 'none'}-${points.length}`;
    if (focusedKey.current === key) {
      return;
    }
    const bounds = L.latLngBounds(points.map((point) => [point.lat, point.lng] as [number, number]));
    map.fitBounds(bounds.pad(0.01), { maxZoom: 16 });
    focusedKey.current = key;
  }, [map, points]);

  return null;
};

export default function HeatMap({
  points,
  onBoundsChange,
  availableDates,
  selectedDate,
  formattedDate,
  onDateChange,
}: HeatMapProps) {
  const dateRange = useMemo(() => {
    if (!availableDates.length) return null;
    return {
      latest: availableDates[0],
      earliest: availableDates[availableDates.length - 1],
    };
  }, [availableDates]);

  const memoizedChange = useCallback(
    (bounds: MapBounds) => {
      onBoundsChange(bounds);
    },
    [onBoundsChange]
  );

  return (
    <div className="map-panel">
      <div className="panel-header">
        <div>
          <h2>Heat Map</h2>
          <p>{formattedDate}</p>
        </div>
        <div className="date-control">
          <label htmlFor="date-select">Date</label>
          <input
            id="date-select"
            className="date-input"
            type="date"
            value={selectedDate ?? ''}
            onChange={(event) => onDateChange(event.target.value || null)}
            min={dateRange?.earliest}
            max={dateRange?.latest}
            disabled={!availableDates.length}
          />
          {selectedDate && !availableDates.includes(selectedDate) && (
            <small className="helper-text">No saved readings for this day — showing empty layer.</small>
          )}
        </div>
      </div>
      <MapContainer
        center={DEFAULT_POSITION}
        zoom={DEFAULT_ZOOM}
        minZoom={14}
        className="map-shell"
        scrollWheelZoom
      >
        <TileLayer
          attribution="&copy; <a href='https://www.openstreetmap.org/'>OpenStreetMap</a> contributors"
          url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
          noWrap
        />
        <MapInitializer points={points} />
        <BoundsWatcher onBoundsChange={memoizedChange} />
        <DataFocus points={points} />
        <HeatLayer points={points} />
        {points.map((point) => {
          const coreRadius = point.thickness_cm >= 30 ? 11 : point.thickness_cm >= 25 ? 9 : 7;
          return (
            <Fragment key={`point-${point.id}`}>
              <CircleMarker
                key={`point-ring-${point.id}`}
                center={[point.lat, point.lng]}
                radius={coreRadius}
                stroke={false}
                opacity={0}
                fillOpacity={0}
              >
                <Tooltip direction="top" offset={[0, -6]} className="point-tooltip">
                  <div className="tooltip-content">
                    <strong>Thickness: {point.thickness_cm.toFixed(1)} cm</strong>
                    <div>Temperature: {formatTemperature(point.temperature_c)}</div>
                    <div>Timestamp: {new Date(point.measured_at).toLocaleString()}</div>
                    <div>
                      Location: ({point.lat.toFixed(6)}, {point.lng.toFixed(6)})
                    </div>
                  </div>
                </Tooltip>
                <Popup>
                  <div className="popup-grid">
                    <strong>Measurement details</strong>
                    <span>Thickness: {point.thickness_cm.toFixed(1)} cm</span>
                    <span>Temperature: {formatTemperature(point.temperature_c)}</span>
                    <span>Timestamp: {new Date(point.measured_at).toLocaleString()}</span>
                    <span>
                      Location: ({point.lat.toFixed(6)}, {point.lng.toFixed(6)})
                    </span>
                  </div>
                </Popup>
              </CircleMarker>
            </Fragment>
          );
        })}
      </MapContainer>
      <div className="legend">
        <strong>Legend</strong>
        <div className="legend-bands">
          <div className="legend-item">
            <span className="legend-swatch red" />
            <span>&lt; 25 cm · Do NOT skate</span>
          </div>
          <div className="legend-item">
            <span className="legend-swatch yellow" />
            <span>25–30 cm · Caution</span>
          </div>
          <div className="legend-item">
            <span className="legend-swatch green" />
            <span>&ge; 30 cm · Safe to skate</span>
          </div>
        </div>
        <small>Interpolated surface — ice thickness can vary locally.</small>
      </div>
    </div>
  );
}
