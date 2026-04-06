import { useState } from 'react';
import { useApi } from '../context/ApiContext';
import { Server, Save, CheckCircle, Wifi, WifiOff, RefreshCw, Loader2 } from 'lucide-react';

const SettingsPage = () => {
  const { apiUrl, updateApiUrl, connected, checking, checkConnection } = useApi();
  const [url, setUrl] = useState(apiUrl);
  const [saved, setSaved] = useState(false);

  const handleSave = () => {
    updateApiUrl(url);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <div style={{ maxWidth: 640, margin: '0 auto', padding: '48px 32px' }}>
      <h1
        className="gradient-text animate-fade-in"
        style={{ fontSize: '1.75rem', fontWeight: 700, marginBottom: 32 }}
      >
        Settings
      </h1>

      {/* API Configuration */}
      <div className="card animate-fade-in" style={{ padding: 28, marginBottom: 20, animationDelay: '0.1s' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 20 }}>
          <Server size={18} style={{ color: 'hsl(225, 80%, 65%)' }} />
          <h2 style={{ fontWeight: 600, fontSize: '1.05rem' }}>API Configuration</h2>
        </div>

        <div style={{ marginBottom: 20 }}>
          <label
            htmlFor="api-url"
            style={{ display: 'block', fontSize: '0.85rem', fontWeight: 500, color: 'var(--text-secondary)', marginBottom: 8 }}
          >
            Backend API URL
          </label>
          <input
            id="api-url"
            type="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="http://localhost:8000"
            className="input"
          />
          <p style={{ marginTop: 6, fontSize: '0.78rem', color: 'var(--text-muted)' }}>
            The URL where your Spring2Fast backend is running
          </p>
        </div>

        {/* Connection Status */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '12px 16px',
            borderRadius: 10,
            background: 'var(--surface-2)',
            marginBottom: 20,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            {checking ? (
              <>
                <Loader2 size={16} className="animate-spin-slow" style={{ color: 'var(--text-muted)' }} />
                <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>Checking connection...</span>
              </>
            ) : connected ? (
              <>
                <Wifi size={16} style={{ color: 'hsl(155, 65%, 55%)' }} />
                <span style={{ fontSize: '0.85rem', color: 'hsl(155, 65%, 55%)' }}>Connected</span>
              </>
            ) : (
              <>
                <WifiOff size={16} style={{ color: 'hsl(0, 65%, 60%)' }} />
                <span style={{ fontSize: '0.85rem', color: 'hsl(0, 65%, 60%)' }}>Disconnected</span>
              </>
            )}
          </div>
          <button
            onClick={checkConnection}
            className="btn-ghost"
            style={{ padding: '4px 12px', fontSize: '0.78rem', display: 'flex', alignItems: 'center', gap: 6 }}
          >
            <RefreshCw size={12} />
            Test
          </button>
        </div>

        <button
          id="save-settings"
          onClick={handleSave}
          className="btn-primary"
          style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10 }}
        >
          {saved ? (
            <>
              <CheckCircle size={18} />
              Saved!
            </>
          ) : (
            <>
              <Save size={18} />
              Save Settings
            </>
          )}
        </button>
      </div>

      {/* About */}
      <div className="card animate-fade-in" style={{ padding: 28, animationDelay: '0.2s' }}>
        <h3 style={{ fontWeight: 600, fontSize: '0.95rem', marginBottom: 12 }}>About</h3>
        <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', display: 'flex', flexDirection: 'column', gap: 6 }}>
          <p style={{ margin: 0 }}>
            <span style={{ color: 'var(--text-secondary)' }}>Spring2Fast Desktop</span> — v0.1.0
          </p>
          <p style={{ margin: 0 }}>
            AI-powered Java Spring Boot → Python FastAPI migration tool
          </p>
        </div>
      </div>
    </div>
  );
};

export default SettingsPage;
