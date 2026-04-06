import { useState, useRef, useEffect } from 'react';
import { Search, Download, Copy, CheckCircle2, AlertCircle, Info } from 'lucide-react';

const LogsViewer = ({ logs = [] }) => {
  const [filter, setFilter] = useState('all');
  const [searchTerm, setSearchTerm] = useState('');
  const [copied, setCopied] = useState(false);
  const scrollRef = useRef(null);

  // Auto-scroll to bottom when new logs arrive
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs.length]);

  const getLogLevel = (log) => {
    const lower = log.toLowerCase();
    if (lower.includes('error') || lower.includes('failed') || lower.includes('exception')) return 'error';
    if (lower.includes('warning') || lower.includes('needs review') || lower.includes('skipped')) return 'warning';
    return 'info';
  };

  const filteredLogs = logs.filter((log) => {
    const level = getLogLevel(log);
    if (filter !== 'all' && level !== filter) return false;
    if (searchTerm && !log.toLowerCase().includes(searchTerm.toLowerCase())) return false;
    return true;
  });

  const copyLogs = () => {
    navigator.clipboard.writeText(filteredLogs.join('\n'));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const downloadLogs = () => {
    const blob = new Blob([filteredLogs.join('\n')], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'migration-logs.txt';
    a.click();
    URL.revokeObjectURL(url);
  };

  const levelColors = {
    error: { bg: 'hsla(0, 70%, 55%, 0.08)', border: 'hsla(0, 70%, 55%, 0.2)', color: 'hsl(0, 65%, 65%)' },
    warning: { bg: 'hsla(40, 85%, 50%, 0.08)', border: 'hsla(40, 85%, 50%, 0.2)', color: 'hsl(40, 80%, 60%)' },
    info: { bg: 'transparent', border: 'var(--border-subtle)', color: 'var(--text-secondary)' },
  };

  const filters = [
    { key: 'all', label: 'All', color: 'hsl(225, 80%, 65%)' },
    { key: 'error', label: 'Errors', color: 'hsl(0, 65%, 60%)' },
    { key: 'warning', label: 'Warnings', color: 'hsl(40, 80%, 55%)' },
    { key: 'info', label: 'Info', color: 'hsl(155, 65%, 55%)' },
  ];

  return (
    <div className="card" style={{ overflow: 'hidden' }}>
      {/* Toolbar */}
      <div
        style={{
          padding: '14px 16px',
          borderBottom: '1px solid var(--border-subtle)',
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          flexWrap: 'wrap',
        }}
      >
        {/* Filters */}
        <div style={{ display: 'flex', gap: 4 }}>
          {filters.map((f) => (
            <button
              key={f.key}
              onClick={() => setFilter(f.key)}
              style={{
                padding: '5px 12px',
                borderRadius: 8,
                border: 'none',
                fontSize: '0.78rem',
                fontWeight: 600,
                cursor: 'pointer',
                transition: 'all 0.15s ease',
                background: filter === f.key ? f.color : 'var(--surface-2)',
                color: filter === f.key ? 'white' : 'var(--text-muted)',
              }}
            >
              {f.label}
            </button>
          ))}
        </div>

        {/* Search */}
        <div style={{ flex: 1, position: 'relative', minWidth: 200 }}>
          <Search
            size={14}
            style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }}
          />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search logs..."
            className="input"
            style={{ paddingLeft: 34, padding: '8px 14px 8px 34px', fontSize: '0.82rem' }}
          />
        </div>

        {/* Actions */}
        <button onClick={copyLogs} className="btn-ghost" style={{ padding: '6px 10px' }}>
          {copied ? <CheckCircle2 size={14} style={{ color: 'hsl(155, 65%, 55%)' }} /> : <Copy size={14} />}
        </button>
        <button onClick={downloadLogs} className="btn-ghost" style={{ padding: '6px 10px' }}>
          <Download size={14} />
        </button>
      </div>

      {/* Log Entries */}
      <div
        ref={scrollRef}
        className="scrollbar-thin font-mono"
        style={{ maxHeight: 440, overflow: 'auto', padding: '10px 12px' }}
      >
        {filteredLogs.length === 0 ? (
          <div style={{ textAlign: 'center', padding: 40, color: 'var(--text-muted)', fontSize: '0.85rem' }}>
            {logs.length === 0 ? 'No logs yet — they will appear as the pipeline runs.' : 'No logs match your filter.'}
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {filteredLogs.map((log, index) => {
              const level = getLogLevel(log);
              const lc = levelColors[level];
              return (
                <div
                  key={index}
                  className="animate-slide-in"
                  style={{
                    display: 'flex',
                    alignItems: 'start',
                    gap: 10,
                    padding: '10px 12px',
                    borderRadius: 8,
                    border: `1px solid ${lc.border}`,
                    background: lc.bg,
                    fontSize: '0.82rem',
                    color: lc.color,
                    animationDelay: `${index * 0.02}s`,
                  }}
                >
                  <span style={{ color: 'var(--text-muted)', fontSize: '0.72rem', flexShrink: 0, minWidth: 24, textAlign: 'right' }}>
                    {index + 1}
                  </span>
                  <span style={{ flex: 1, wordBreak: 'break-word' }}>{log}</span>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};

export default LogsViewer;
