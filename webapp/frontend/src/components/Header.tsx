interface HeaderProps {
  onUpload: () => void;
}

export default function Header({ onUpload }: HeaderProps) {
  return (
    <header className="hero">
      <h1>Ice Thickness Visualizer</h1>
      <p>Explore Rideau Canal ice conditions powered by the SnowAngel UAV.</p>
      <div className="cta-row">
        <button type="button" className="primary" onClick={onUpload}>
          Upload CSV
        </button>
        <button type="button" className="secondary" disabled>
          Submit
        </button>
      </div>
    </header>
  );
}
