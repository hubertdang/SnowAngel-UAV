import { useCallback, useState } from 'react';

export interface HeatPoint {
  id: number;
  lat: number;
  lng: number;
  thickness_cm: number;
  confidence_score: number;
  measured_at: string;
  notes?: string | null;
}

export interface MapBounds {
  north: number;
  south: number;
  east: number;
  west: number;
}

const runtimeBase =
  typeof window !== 'undefined'
    ? (() => {
        const hostname = window.location.hostname === '0.0.0.0' ? 'localhost' : window.location.hostname;
        return `${window.location.protocol}//${hostname}:8000`;
      })()
    : undefined;
export const API_BASE = runtimeBase ?? import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

export function useHeatmapData() {
  const [points, setPoints] = useState<HeatPoint[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchPoints = useCallback(async (bounds: MapBounds, day?: string | null) => {
    setLoading(true);
    setError(null);

    try {
      const url = new URL('/api/conditions', API_BASE);
      url.searchParams.set('north', bounds.north.toString());
      url.searchParams.set('south', bounds.south.toString());
      url.searchParams.set('east', bounds.east.toString());
      url.searchParams.set('west', bounds.west.toString());
      url.searchParams.set('limit', '800');
      if (day) {
        url.searchParams.set('day', day);
      }

      const response = await fetch(url);
      if (!response.ok) {
        throw new Error(`Backend responded with ${response.status}`);
      }
      const payload = (await response.json()) as HeatPoint[];
      setPoints(payload);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }, []);

  return {
    points,
    loading,
    error,
    fetchPoints,
  };
}
