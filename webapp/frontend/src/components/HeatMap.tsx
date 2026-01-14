import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
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
const CLUSTER_RADIUS_METERS = 200;

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

function haversineDistanceMeters(a: { lat: number; lng: number }, b: { lat: number; lng: number }) {
  const R = 6371000;
  const dLat = ((b.lat - a.lat) * Math.PI) / 180;
  const dLng = ((b.lng - a.lng) * Math.PI) / 180;
  const lat1 = (a.lat * Math.PI) / 180;
  const lat2 = (b.lat * Math.PI) / 180;

  const sinDLat = Math.sin(dLat / 2);
  const sinDLng = Math.sin(dLng / 2);
  const h = sinDLat * sinDLat + Math.cos(lat1) * Math.cos(lat2) * sinDLng * sinDLng;
  return 2 * R * Math.asin(Math.sqrt(h));
}

const estimateTemperature = (confidenceScore: number, measuredAt?: string) => {
  const measuredHour = measuredAt ? new Date(measuredAt).getHours() : 12;
  const chillFromConfidence = (1 - confidenceScore) * 6;
  const diurnalSwing = measuredHour > 13 ? 2 : 0;
  const estimate = -9 - chillFromConfidence + diurnalSwing;
  return Math.round(estimate * 10) / 10;
};

type Cluster = {
  id: string;
  lat: number;
  lng: number;
  averageThickness: number;
  averageConfidence: number;
  count: number;
  notes: Set<string>;
};

const clusterPoints = (points: HeatPoint[], thresholdMeters: number): Cluster[] => {
  // Bin points into a coarse grid to drastically reduce marker count before distance-averaging
  const grid = new Map<string, HeatPoint[]>();
  const cellSizeDeg = 0.0012; // ~130 m near Ottawa

  points.forEach((point) => {
    const key = `${Math.round(point.lat / cellSizeDeg)}-${Math.round(point.lng / cellSizeDeg)}`;
    const bucket = grid.get(key);
    if (bucket) {
      bucket.push(point);
    } else {
      grid.set(key, [point]);
    }
  });

  const clusters: Cluster[] = [];
  let idx = 0;

  grid.forEach((bucket) => {
    let latSum = 0;
    let lngSum = 0;
    let thicknessSum = 0;
    let confidenceSum = 0;
    const notes = new Set<string>();

    bucket.forEach((p) => {
      latSum += p.lat;
      lngSum += p.lng;
      thicknessSum += p.thickness_cm;
      confidenceSum += p.confidence_score;
      if (p.notes) notes.add(p.notes);
    });

    const centroid = {
      lat: latSum / bucket.length,
      lng: lngSum / bucket.length,
    };

    // Final pass to merge any centroids that are still close after grid binning
    let merged = false;
    for (const existing of clusters) {
      const distance = haversineDistanceMeters({ lat: existing.lat, lng: existing.lng }, centroid);
      if (distance <= thresholdMeters) {
        const newCount = existing.count + bucket.length;
        existing.lat = (existing.lat * existing.count + centroid.lat * bucket.length) / newCount;
        existing.lng = (existing.lng * existing.count + centroid.lng * bucket.length) / newCount;
        existing.averageThickness = (existing.averageThickness * existing.count + thicknessSum) / newCount;
        existing.averageConfidence = (existing.averageConfidence * existing.count + confidenceSum) / newCount;
        notes.forEach((note) => existing.notes.add(note));
        existing.count = newCount;
        merged = true;
        break;
      }
    }

    if (!merged) {
      clusters.push({
        id: `cluster-${idx++}`,
        lat: centroid.lat,
        lng: centroid.lng,
        averageThickness: thicknessSum / bucket.length,
        averageConfidence: confidenceSum / bucket.length,
        count: bucket.length,
        notes,
      });
    }
  });

  return clusters;
};

const HeatLayer = ({ points }: { points: HeatPoint[] }) => {
  const map = useMap();

  useEffect(() => {
    const heat = (L as any).heatLayer(
      points.map((point) => [point.lat, point.lng, point.confidence_score]),
      {
        radius: 24,
        blur: 28,
        maxZoom: 18,
        minOpacity: 0.35,
        gradient: {
          0.1: '#1d70b8',
          0.4: '#3dd598',
          0.6: '#f7b733',
          0.8: '#fc4a1a',
          1: '#b40000',
        },
      }
    );

    heat.addTo(map);
    return () => {
      map.removeLayer(heat);
    };
  }, [map, points]);

  return null;
};

const ClusterMarkers = ({
  clusters,
  selectedId,
  setSelectedId,
}: {
  clusters: Cluster[];
  selectedId: string | null;
  setSelectedId: (id: string | null) => void;
}) => {
  if (!clusters.length) return null;

  return (
    <>
      {clusters.map((cluster) => (
        <CircleMarker
          key={cluster.id}
          center={[cluster.lat, cluster.lng]}
          radius={Math.min(12, 6 + cluster.count * 0.6)}
          color="rgba(37, 99, 235, 0.75)"
          weight={1.25}
          opacity={0.85}
          fillColor="rgba(37, 99, 235, 0.15)"
          fillOpacity={0.25}
          eventHandlers={{
            click: () => setSelectedId(cluster.id),
          }}
        >
          <Tooltip direction="top" offset={[0, -6]} className="point-tooltip">
            <div className="tooltip-content">
              <strong>{cluster.averageThickness.toFixed(1)} cm avg</strong>
              <div>Area count: {cluster.count}</div>
              <div>Confidence: {(cluster.averageConfidence * 100).toFixed(0)}%</div>
              <div>Est. temp: {estimateTemperature(cluster.averageConfidence).toFixed(1)}°C</div>
              {cluster.notes.size > 0 && <em>{Array.from(cluster.notes).slice(0, 2).join(' · ')}</em>}
            </div>
          </Tooltip>
          {selectedId === cluster.id && (
            <Popup
              position={[cluster.lat, cluster.lng]}
              closeOnEscapeKey
              autoPan
              eventHandlers={{ remove: () => setSelectedId(null) }}
            >
              <div className="popup-grid">
                <strong>Cluster details</strong>
                <span>Points: {cluster.count}</span>
                <span>Avg thickness: {cluster.averageThickness.toFixed(1)} cm</span>
                <span>Confidence: {(cluster.averageConfidence * 100).toFixed(0)}%</span>
                <span>Est. temperature: {estimateTemperature(cluster.averageConfidence).toFixed(1)}°C</span>
                {cluster.notes.size > 0 && <em>{Array.from(cluster.notes).slice(0, 3).join(' · ')}</em>}
              </div>
            </Popup>
          )}
        </CircleMarker>
      ))}
    </>
  );
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

const MapInitializer = () => {
  const map = useMap();

  useEffect(() => {
    const timer = setTimeout(() => {
      map.invalidateSize();
      map.fitBounds(L.latLngBounds(CANAL_BOUNDS).pad(0.003), { maxZoom: 16 });
    }, 200);
    return () => clearTimeout(timer);
  }, [map]);

  return null;
};

const DataFocus = ({ points, selectedDate }: { points: HeatPoint[]; selectedDate: string | null }) => {
  const map = useMap();
  const focusedDate = useRef<string | null>(null);

  useEffect(() => {
    focusedDate.current = null;
  }, [selectedDate]);

  useEffect(() => {
    if (!points.length) {
      return;
    }
    if (focusedDate.current === (selectedDate ?? 'all')) {
      return;
    }
    const bounds = L.latLngBounds(points.map((point) => [point.lat, point.lng] as [number, number]));
    map.fitBounds(bounds.pad(0.01), { maxZoom: 16 });
    focusedDate.current = selectedDate ?? 'all';
  }, [map, points, selectedDate]);

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
  const [selectedClusterId, setSelectedClusterId] = useState<string | null>(null);

  const dateRange = useMemo(() => {
    if (!availableDates.length) return null;
    return {
      latest: availableDates[0],
      earliest: availableDates[availableDates.length - 1],
    };
  }, [availableDates]);

  const clusters = useMemo(() => clusterPoints(points, CLUSTER_RADIUS_METERS), [points]);

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
        bounds={CANAL_BOUNDS}
        maxBounds={CANAL_BOUNDS}
        maxBoundsViscosity={0.9}
      >
        <TileLayer
          attribution="&copy; <a href='https://www.openstreetmap.org/'>OpenStreetMap</a> contributors"
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          noWrap
        />
        <MapInitializer />
        <BoundsWatcher onBoundsChange={memoizedChange} />
        <DataFocus points={points} selectedDate={selectedDate} />
        <HeatLayer points={points} />
        <ClusterMarkers clusters={clusters} selectedId={selectedClusterId} setSelectedId={setSelectedClusterId} />
      </MapContainer>
      <div className="legend">
        <strong>Legend</strong>
        <div className="legend-scale">
          <span>Not ready</span>
          <div className="scale-bar" />
          <span>Great to skate</span>
        </div>
        <small>Confidence levels generated from dummy telemetry</small>
      </div>
    </div>
  );
}
