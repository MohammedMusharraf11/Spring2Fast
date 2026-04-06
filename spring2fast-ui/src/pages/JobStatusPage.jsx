import { useEffect, useState, useCallback, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useApi } from '../context/ApiContext';
import {
  CheckCircle2, XCircle, Loader2, Download, ArrowLeft, Clock,
  Activity, FileText, Terminal, Layers, Code2, FolderTree, Eye
} from 'lucide-react';
import PipelineVisualization from '../components/PipelineVisualization';
import ArtifactViewer from '../components/ArtifactViewer';
import LogsViewer from '../components/LogsViewer';
import StatsDashboard from '../components/StatsDashboard';
import SourceFileBrowser from '../components/SourceFileBrowser';
import OutputFileBrowser from '../components/OutputFileBrowser';

const POLL_INTERVAL = 2500;

const TABS = [
  { id: 'pipeline', label: 'Pipeline', icon: Activity },
  { id: 'source', label: 'Source Files', icon: FolderTree },
  { id: 'stats', label: 'Overview', icon: Eye },
  { id: 'output', label: 'Generated Code', icon: Code2 },
  { id: 'artifacts', label: 'Artifacts', icon: FileText },
  { id: 'logs', label: 'Logs', icon: Terminal },
];

const statusMeta = {
  pending:    { color: 'var(--text-muted)',       label: 'Pending',    icon: Clock },
  ingesting:  { color: 'hsl(225, 80%, 65%)',      label: 'Ingesting',  icon: Activity },
  analyzing:  { color: 'hsl(255, 70%, 65%)',      label: 'Analyzing',  icon: Activity },
  planning:   { color: 'hsl(195, 80%, 55%)',      label: 'Planning',   icon: Activity },
  migrating:  { color: 'hsl(40, 85%, 55%)',       label: 'Migrating',  icon: Activity },
  validating: { color: 'hsl(285, 70%, 60%)',      label: 'Validating', icon: Activity },
  completed:  { color: 'hsl(155, 65%, 55%)',      label: 'Completed',  icon: CheckCircle2 },
  failed:     { color: 'hsl(0, 65%, 60%)',        label: 'Failed',     icon: XCircle },
};

const isInProgress = (status) =>
  ['pending', 'ingesting', 'analyzing', 'planning', 'migrating', 'validating'].includes(status);

const JobStatusPage = () => {
  const { jobId } = useParams();
  const navigate = useNavigate();
  const { get, apiUrl } = useApi();
  const [state, setState] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState('pipeline');
  const [downloading, setDownloading] = useState(false);
  const pollRef = useRef(null);

  const fetchState = useCallback(async () => {
    try {
      const response = await get(`/api/v1/migrate/${jobId}/state`);
      setState(response.data);
      setLoading(false);
    } catch (err) {
      // Fallback to basic status endpoint
      try {
        const response = await get(`/api/v1/migrate/${jobId}/status`);
        setState(response.data);
        setLoading(false);
      } catch (err2) {
        setError(err2.response?.data?.detail || 'Failed to fetch job status');
        setLoading(false);
      }
    }
  }, [get, jobId]);

  useEffect(() => {
    fetchState();
    pollRef.current = setInterval(fetchState, POLL_INTERVAL);
    return () => clearInterval(pollRef.current);
  }, [fetchState]);

  // Stop polling when job is done
  useEffect(() => {
    if (state && !isInProgress(state.status)) {
      clearInterval(pollRef.current);
    }
  }, [state]);

  const handleDownload = async () => {
    setDownloading(true);
    try {
      const response = await get(`/api/v1/migrate/${jobId}/result`, { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `fastapi_project_${jobId.slice(0, 8)}.zip`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch {
      setError('Failed to download result');
    } finally {
      setDownloading(false);
    }
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', gap: 12 }}>
        <Loader2 size={24} className="animate-spin-slow" style={{ color: 'hsl(225, 80%, 65%)' }} />
        <span style={{ color: 'var(--text-secondary)' }}>Loading job state...</span>
      </div>
    );
  }

  if (error && !state) {
    return (
      <div style={{ maxWidth: 600, margin: '80px auto', padding: '0 32px' }}>
        <div className="alert-error">{error}</div>
      </div>
    );
  }

  const meta = statusMeta[state.status] || statusMeta.pending;
  const StatusIcon = meta.icon;
  const inProgress = isInProgress(state.status);

  return (
    <div style={{ maxWidth: 1200, margin: '0 auto', padding: '32px 32px 48px' }}>
      {/* Back Button */}
      <button
        onClick={() => navigate('/')}
        className="btn-ghost"
        style={{ marginBottom: 20, display: 'flex', alignItems: 'center', gap: 8, padding: '8px 14px', fontSize: '0.85rem' }}
      >
        <ArrowLeft size={16} />
        Back to Home
      </button>

      {/* ─── Header Card ─── */}
      <div className="card animate-fade-in" style={{ padding: '24px 28px', marginBottom: 20 }}>
        <div style={{ display: 'flex', alignItems: 'start', justifyContent: 'space-between', marginBottom: 18 }}>
          <div>
            <h1 style={{ fontSize: '1.5rem', fontWeight: 700, marginBottom: 4 }}>Migration Job</h1>
            <p className="font-mono" style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>{jobId}</p>
            {state.source_url && (
              <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: 6 }}>
                {state.source_url}
              </p>
            )}
          </div>
          <div
            className="badge"
            style={{
              background: `${meta.color}18`,
              color: meta.color,
              padding: '8px 14px',
              fontSize: '0.82rem',
            }}
          >
            <StatusIcon size={16} className={inProgress ? 'animate-spin-slow' : ''} />
            {meta.label}
          </div>
        </div>

        {/* Progress Bar */}
        <div style={{ marginBottom: 14 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
            <span style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
              {state.current_step || 'Initializing...'}
            </span>
            <span style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>
              {state.progress_pct}%
            </span>
          </div>
          <div className="progress-track">
            <div
              className={`progress-fill ${state.status === 'failed' ? 'error' : ''} ${state.status === 'completed' ? 'success' : ''}`}
              style={{ width: `${state.progress_pct}%` }}
            />
          </div>
        </div>

        {/* Timestamps */}
        <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
          {state.created_at && (
            <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
              <span style={{ color: 'var(--text-secondary)', fontWeight: 500 }}>Started: </span>
              {new Date(state.created_at).toLocaleString()}
            </div>
          )}
          {state.completed_at && (
            <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
              <span style={{ color: 'var(--text-secondary)', fontWeight: 500 }}>Completed: </span>
              {new Date(state.completed_at).toLocaleString()}
            </div>
          )}
        </div>
      </div>

      {/* Error Message */}
      {state.error_message && (
        <div className="alert-error animate-fade-in" style={{ marginBottom: 20, fontSize: '0.85rem' }}>
          <strong style={{ display: 'block', marginBottom: 4 }}>Error</strong>
          {state.error_message}
        </div>
      )}

      {/* Download Button */}
      {state.status === 'completed' && (
        <button
          id="download-result"
          onClick={handleDownload}
          disabled={downloading}
          className="btn-success animate-fade-in"
          style={{
            width: '100%',
            marginBottom: 20,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 10,
          }}
        >
          {downloading ? (
            <>
              <Loader2 size={18} className="animate-spin-slow" />
              Downloading...
            </>
          ) : (
            <>
              <Download size={18} />
              Download FastAPI Project
            </>
          )}
        </button>
      )}

      {/* ─── Tabs ─── */}
      <div className="tab-bar" style={{ marginBottom: 20, overflowX: 'auto' }}>
        {TABS.map((tab) => {
          const TabIcon = tab.icon;
          return (
            <button
              key={tab.id}
              id={`tab-${tab.id}`}
              onClick={() => setActiveTab(tab.id)}
              className={`tab-item ${activeTab === tab.id ? 'active' : ''}`}
            >
              <TabIcon size={14} />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* ─── Tab Content ─── */}
      <div className="animate-fade-in" key={activeTab}>
        {activeTab === 'pipeline' && <PipelineVisualization state={state} />}
        {activeTab === 'source' && <SourceFileBrowser jobId={jobId} />}
        {activeTab === 'stats' && <StatsDashboard state={state} />}
        {activeTab === 'output' && <OutputFileBrowser jobId={jobId} />}
        {activeTab === 'artifacts' && <ArtifactViewer jobId={jobId} />}
        {activeTab === 'logs' && <LogsViewer logs={state.logs || []} />}
      </div>

      {/* In Progress Indicator */}
      {inProgress && (
        <div
          className="alert-info animate-fade-in"
          style={{ marginTop: 20, display: 'flex', alignItems: 'center', gap: 12, fontSize: '0.85rem' }}
        >
          <Loader2 size={18} className="animate-spin-slow" />
          Migration in progress... Auto-refreshing every {POLL_INTERVAL / 1000}s.
        </div>
      )}
    </div>
  );
};

export default JobStatusPage;
