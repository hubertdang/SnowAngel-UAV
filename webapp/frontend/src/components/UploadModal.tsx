import { useState } from 'react';

interface UploadModalProps {
  open: boolean;
  onClose: () => void;
}

export default function UploadModal({ open, onClose }: UploadModalProps) {
  const [fileName, setFileName] = useState<string>('');

  if (!open) {
    return null;
  }

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true">
      <div className="modal">
        <h2>Upload Data CSV</h2>
        <p></p>
        <label className="file-input">
          <input
            type="file"
            accept=".csv"
            onChange={(event) => setFileName(event.target.files?.[0]?.name ?? '')}
          />
          <span>{fileName || 'Choose a .csv file'}</span>
        </label>
        <div className="modal-actions">
          <button type="button" className="secondary" onClick={onClose}>
            Cancel
          </button>
          <button type="button" className="primary" disabled={!fileName}>
            Upload
          </button>
        </div>
      </div>
    </div>
  );
}
