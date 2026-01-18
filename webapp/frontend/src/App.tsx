import { useCallback, useEffect, useMemo, useState } from 'react';
import Header from './components/Header';
import HeatMap from './components/HeatMap';
import UploadModal from './components/UploadModal';
import { API_BASE, MapBounds, useHeatmapData } from './hooks/useHeatmapData';

export default function App() {
  const [modalOpen, setModalOpen] = useState(false);
  const [availableDates, setAvailableDates] = useState<string[]>([]);
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [datesError, setDatesError] = useState<string | null>(null);
  const [lastBounds, setLastBounds] = useState<MapBounds | null>(null);
  const { points, loading, error, fetchPoints } = useHeatmapData();

  const handleBoundsChange = useCallback(
    (bounds: MapBounds) => {
      setLastBounds(bounds);
      fetchPoints(bounds, selectedDate);
    },
    [fetchPoints, selectedDate]
  );

  useEffect(() => {
    async function loadDates() {
      try {
        setDatesError(null);
        const response = await fetch(`${API_BASE}/api/condition-dates?limit=120`);
        if (!response.ok) {
          throw new Error(`Failed to fetch available dates (${response.status})`);
        }
        const payload = (await response.json()) as string[];
        setAvailableDates(payload);
        setSelectedDate((prev) => prev ?? payload[0] ?? null);
      } catch (err) {
        setDatesError(err instanceof Error ? err.message : 'Unable to load date options');
      }
    }

    loadDates();
  }, []);

  useEffect(() => {
    if (lastBounds) {
      fetchPoints(lastBounds, selectedDate);
    }
  }, [selectedDate, lastBounds, fetchPoints]);

  const formattedDate = useMemo(() => {
    if (!selectedDate) {
      return 'Select a date to visualize conditions';
    }
    // Parse as a local date to avoid off-by-one day shifts from UTC parsing
    const parsed = new Date(`${selectedDate}T00:00:00`);
    return parsed.toLocaleDateString(undefined, {
      weekday: 'long',
      month: 'short',
      day: 'numeric',
    });
  }, [selectedDate]);

  return (
    <div className="app-shell">
      <Header onUpload={() => setModalOpen(true)} />

      <section className="summary-card">
        <h3>About</h3>
        <p>
          SnowAngel UAV is a proof-of-concept tool for monitoring ice safety along Ottawa&apos;s Rideau Canal. Flight crews
          upload raw UAV sensor data, which the backend cleans, scores for confidence, and stores in PostgreSQL. The web
          app visualizes that data as a heatmap and clustered hover points, letting residents and operators quickly see
          where the ice is strong, thin, or needs a closer look.
        </p>
      </section>

      <HeatMap
        points={points}
        onBoundsChange={handleBoundsChange}
        availableDates={availableDates}
        selectedDate={selectedDate}
        onDateChange={setSelectedDate}
        formattedDate={formattedDate}
      />

      <section className="status-row">
        <div>
          <strong>Live status:</strong>
          <span className={loading ? 'badge warning' : 'badge success'}>
            {loading ? 'Updating map…' : 'Fresh data loaded'}
          </span>
        </div>
        {error && <p className="error">{error}</p>}
        {datesError && <p className="error">{datesError}</p>}
      </section>

      <UploadModal open={modalOpen} onClose={() => setModalOpen(false)} />
    </div>
  );
}
