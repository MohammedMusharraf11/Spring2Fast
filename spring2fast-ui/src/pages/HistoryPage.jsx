import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApi } from '../context/ApiContext';
import {
  Clock, CheckCircle2, XCircle, Loader2, ExternalLink, RefreshCw, History
} from 'lucide-react';

const statusMeta = {
  pending:    { color: 'var(--text-muted)',  icon: Clock },
  ingesting:  { color: 'hsl(225, 80%, 65%)', icon: Loader2 },
  analyzing:  { color: 'hsl(255, 70%, 65%)', icon: Loader2 },
  planning:   { color: 'hsl(195, 80%, 55%)', icon: Loader2 },
  migrating:  { color: 'hsl(40, 85%, 55%)',  icon: Loader2 },
  validating: { color: 'hsl(285, 70%, 60%)', icon: Loader2 },
  completed:  { color: 'hsl(155, 65%, 55%)', icon: CheckCircle2 },
  failed:     { color: 'hsl(0, 65%, 60%)',   icon: XCircle },
};

const HistoryPage = () => {
  const navigate = useNavigate();
  const { get, connected } = useApi();
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchJobs = useCallback(async () => {
    try {
      const response = await get('/api/v1/migrate/jobs/list');
      setJobs(response.data.jobs || []);
    } catch {
      setJobs([]);
    } finally {
      setLoading(false);
    }
  }, [get]);

  useEffect(() => {
    if (connected) fetchJobs();
    else setLoading(false);
  }, [connected, fetchJobs]);

  if (loading) {
    return (
      <div style={{ maxWidth: 880, margin: '0 auto', padding: '48px 32px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 80, gap: 10 }}>
          <Loader2 size={22} className="animate-spin-slow" style={{ color: 'hsl(225, 80%, 65%)' }} />
          <span style={{ color: 'var(--text-muted)' }}>Loading history...</span>
        </div>
      </div>
    );
  }

  return (
    <div style={{ maxWidth: 880, margin: '0 auto', padding: '48px 32px' }}>
      {/* Header */}
      <div className="animate-fade-in" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 28 }}>
        <h1 style={{ fontSize: '1.75rem', fontWeight: 700 }}>
          <span className="gradient-text">Migration History</span>
        </h1>
        <button
          onClick={fetchJobs}
          className="btn-ghost"
          style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.85rem' }}
        >
          <RefreshCw size={14} />
          Refresh
        </button>
      </div>

      {!connected && (
        <div className="alert-error animate-fade-in" style={{ marginBottom: 20, fontSize: '0.85rem' }}>
          Backend is offline — cannot load history. Check your connection in Settings.
        </div>
      )}

      {jobs.length === 0 ? (
        <div
          className="card animate-fade-in"
          style={{ textAlign: 'center', padding: 60 }}
        >
          <History size={40} style={{ color: 'var(--text-muted)', margin: '0 auto 16px', opacity: 0.5 }} />
          <h3 style={{ fontWeight: 600, fontSize: '1.1rem', marginBottom: 6 }}>No migrations yet</h3>
          <p style={{ color: 'var(--text-muted)', marginBottom: 20, fontSize: '0.9rem' }}>
            Your migration jobs will appear here after you start one.
          </p>
          <button onClick={() => navigate('/')} className="btn-primary" style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
            Start Migration
          </button>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {jobs.map((job, i) => {
            const meta = statusMeta[job.status] || statusMeta.pending;
            const StatusIcon = meta.icon;
            const isRunning = ['ingesting', 'analyzing', 'planning', 'migrating', 'validating'].includes(job.status);

            return (
              <div
                key={job.job_id}
                className="card card-interactive animate-fade-in"
                onClick={() => navigate(`/job/${job.job_id}`)}
                style={{ padding: '18px 22px', cursor: 'pointer', animationDelay: `${i * 0.05}s` }}
              >
                <div style={{ display: 'flex', alignItems: 'start', justifyContent: 'space-between' }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    {/* Source URL */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
                      <span
                        style={{
                          fontWeight: 600,
                          fontSize: '0.95rem',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {job.source_url || 'Unknown source'}
                      </span>
                      <span
                        className="badge"
                        style={{ background: `${meta.color}18`, color: meta.color }}
                      >
                        <StatusIcon size={12} className={isRunning ? 'animate-spin-slow' : ''} />
                        {job.status}
                      </span>
                    </div>

                    {/* Meta */}
                    <div style={{ display: 'flex', gap: 16, fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                      <span className="font-mono">{job.job_id.slice(0, 8)}...</span>
                      <span>{job.source_type}</span>
                      {job.created_at && <span>{new Date(job.created_at).toLocaleString()}</span>}
                    </div>

                    {/* Progress */}
                    {isRunning && job.progress_pct > 0 && (
                      <div style={{ marginTop: 10 }}>
                        <div className="progress-track" style={{ height: 4 }}>
                          <div className="progress-fill" style={{ width: `${job.progress_pct}%` }} />
                        </div>
                      </div>
                    )}
                  </div>

                  <ExternalLink size={16} style={{ color: 'var(--text-muted)', flexShrink: 0, marginLeft: 12 }} />
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default HistoryPage;
