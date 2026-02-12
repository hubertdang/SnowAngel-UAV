import { useState } from 'react';
import { API_BASE } from '../hooks/useHeatmapData';

interface UploadModalProps {
  open: boolean;
  onClose: () => void;
  onUploadComplete: () => void;
}

export default function UploadModal({ open, onClose, onUploadComplete }: UploadModalProps) {
  const [fileName, setFileName] = useState<string>('');
  const [file, setFile] = useState<File | null>(null);
  const [replaceExisting, setReplaceExisting] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');

  if (!open) {
    return null;
  }

  const handleUpload = async () => {
    if (!file) return;
    if (username !== 'admin' || password !== 'admin') {
      setError('Invalid username or password');
      return;
    }
    setUploading(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append('file', file);
      const response = await fetch(`${API_BASE}/api/uploads?replace=${replaceExisting}`, {
        method: 'POST',
        body: formData,
      });
      if (!response.ok) {
        const message = await response.text();
        throw new Error(message || `Upload failed with status ${response.status}`);
      }
      onUploadComplete();
      onClose();
      setFile(null);
      setFileName('');
      setUsername('');
      setPassword('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true">
      <div className="modal">
        <h2>Upload Data CSV</h2>
        <p>Raw or converted CSVs accepted. Raw format: timestamp, lat, lng, temp, samples...</p>
        <label className="file-input">
          <input
            type="file"
            accept=".csv"
            onChange={(event) => {
              const selected = event.target.files?.[0] ?? null;
              setFile(selected);
              setFileName(selected?.name ?? '');
            }}
          />
          <span>{fileName || 'Choose a .csv file'}</span>
        </label>
        <label className="text-input">
          <span>Username</span>
          <input
            type="text"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
          />
        </label>
        <label className="text-input">
          <span>Password</span>
          <input
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </label>
        <label className="checkbox-row">
          <input
            type="checkbox"
            checked={replaceExisting}
            onChange={(event) => setReplaceExisting(event.target.checked)}
          />
          Replace existing measurements
        </label>
        {error && <p className="error">{error}</p>}
        <div className="modal-actions">
          <button type="button" className="secondary" onClick={onClose}>
            Cancel
          </button>
          <button type="button" className="primary" disabled={!fileName || uploading} onClick={handleUpload}>
            {uploading ? 'Uploading…' : 'Upload'}
          </button>
        </div>
      </div>
    </div>
  );
}
