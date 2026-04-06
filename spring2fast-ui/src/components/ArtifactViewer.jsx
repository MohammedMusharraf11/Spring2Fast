import { useState, useEffect, useCallback } from 'react';
import { FileText, Download, Loader2, ChevronRight } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useApi } from '../context/ApiContext';

// Simple custom styles for the markdown renderer so that it fits the dark glassmorphism theme perfectly
const MarkdownComponents = {
  h1: ({node, ...props}) => <h1 style={{fontSize: '1.75em', fontWeight: 700, borderBottom: '1px solid var(--border-subtle)', paddingBottom: '0.3em', marginBottom: '0.8em', marginTop: '1.2em', color: 'var(--text-primary)'}} {...props} />,
  h2: ({node, ...props}) => <h2 style={{fontSize: '1.4em', fontWeight: 600, borderBottom: '1px solid var(--border-subtle)', paddingBottom: '0.3em', marginBottom: '0.8em', marginTop: '1.2em', color: 'var(--text-primary)'}} {...props} />,
  h3: ({node, ...props}) => <h3 style={{fontSize: '1.15em', fontWeight: 600, marginBottom: '0.6em', marginTop: '1em', color: 'var(--text-primary)'}} {...props} />,
  p: ({node, ...props}) => <p style={{lineHeight: 1.6, marginBottom: '1em', color: 'var(--text-secondary)'}} {...props} />,
  ul: ({node, ...props}) => <ul style={{listStyleType: 'disc', paddingLeft: '2em', marginBottom: '1em', color: 'var(--text-secondary)', display: 'flex', flexDirection: 'column', gap: '0.25em'}} {...props} />,
  ol: ({node, ...props}) => <ol style={{listStyleType: 'decimal', paddingLeft: '2em', marginBottom: '1em', color: 'var(--text-secondary)', display: 'flex', flexDirection: 'column', gap: '0.25em'}} {...props} />,
  li: ({node, ...props}) => <li style={{lineHeight: 1.5}} {...props} />,
  a: ({node, ...props}) => <a style={{color: 'hsl(195, 70%, 65%)', textDecoration: 'none'}} {...props} />,
  blockquote: ({node, ...props}) => <blockquote style={{borderLeft: '4px solid hsl(225, 80%, 65%)', paddingLeft: '1em', margin: '0 0 1em 0', color: 'var(--text-muted)'}} {...props} />,
  code: ({node, inline, ...props}) => 
    inline 
      ? <code style={{background: 'var(--surface-0)', padding: '0.2em 0.4em', borderRadius: '4px', fontSize: '0.85em', fontFamily: 'JetBrains Mono, monospace', color: 'hsl(195, 70%, 75%)'}} {...props} />
      : <code style={{display: 'block', background: 'var(--surface-0)', padding: '1em', borderRadius: '8px', overflowX: 'auto', fontSize: '0.85em', fontFamily: 'JetBrains Mono, monospace', marginBottom: '1em', border: '1px solid var(--border-subtle)'}} {...props} />,
  table: ({node, ...props}) => <div style={{overflowX: 'auto', marginBottom: '1em'}}><table style={{width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.9em'}} {...props} /></div>,
  th: ({node, ...props}) => <th style={{borderBottom: '2px solid var(--border-subtle)', padding: '0.75em 1em', fontWeight: 600, color: 'var(--text-primary)', background: 'var(--surface-0)'}} {...props} />,
  td: ({node, ...props}) => <td style={{borderBottom: '1px solid var(--border-subtle)', padding: '0.75em 1em', color: 'var(--text-secondary)'}} {...props} />
};

const ArtifactViewer = ({ jobId }) => {
  const { get } = useApi();
  const [artifactList, setArtifactList] = useState([]);
  const [selectedArtifact, setSelectedArtifact] = useState(null);
  const [content, setContent] = useState('');
  const [loading, setLoading] = useState(true);
  const [contentLoading, setContentLoading] = useState(false);

  // Fetch list of artifacts from backend — fully dynamic
  const fetchArtifactList = useCallback(async () => {
    try {
      const response = await get(`/api/v1/migrate/${jobId}/artifacts`);
      const artifacts = response.data.artifacts || [];
      setArtifactList(artifacts);
      // Auto-select the first artifact
      if (artifacts.length > 0 && !selectedArtifact) {
        setSelectedArtifact(artifacts[0]);
      }
    } catch {
      setArtifactList([]);
    } finally {
      setLoading(false);
    }
  }, [get, jobId, selectedArtifact]);

  useEffect(() => {
    fetchArtifactList();
    // Re-poll every 5s so new artifacts appear as they're generated
    const interval = setInterval(fetchArtifactList, 5000);
    return () => clearInterval(interval);
  }, [fetchArtifactList]);

  // Fetch content when artifact is selected
  useEffect(() => {
    if (!selectedArtifact) return;
    setContentLoading(true);
    get(`/api/v1/migrate/${jobId}/artifact/${selectedArtifact.filename}`)
      .then((response) => {
        setContent(response.data.content || response.data || '');
      })
      .catch(() => {
        setContent('Failed to load artifact content.');
      })
      .finally(() => {
        setContentLoading(false);
      });
  }, [selectedArtifact, get, jobId]);

  const downloadArtifact = () => {
    if (!selectedArtifact || !content) return;
    const blob = new Blob([content], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = selectedArtifact.filename;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 60, gap: 10 }}>
        <Loader2 size={20} className="animate-spin-slow" style={{ color: 'hsl(225, 80%, 65%)' }} />
        <span style={{ color: 'var(--text-muted)' }}>Loading artifacts...</span>
      </div>
    );
  }

  if (artifactList.length === 0) {
    return (
      <div style={{ textAlign: 'center', padding: 60, color: 'var(--text-muted)' }}>
        <FileText size={36} style={{ margin: '0 auto 12px', opacity: 0.5 }} />
        <p>No artifacts generated yet.</p>
        <p style={{ fontSize: '0.8rem' }}>Artifacts will stream in as each pipeline stage completes.</p>
      </div>
    );
  }

  // Check if we are viewing a markdown file (true for basically all artifacts currently)
  const isMarkdown = selectedArtifact?.filename?.endsWith('.md') !== false;

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '280px 1fr', gap: 16, height: 520 }}>
      {/* Artifact List */}
      <div className="card" style={{ overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
        <div
          style={{
            padding: '12px 16px',
            borderBottom: '1px solid var(--border-subtle)',
            fontWeight: 600,
            fontSize: '0.85rem',
          }}
        >
          Artifacts ({artifactList.length})
        </div>
        <div className="scrollbar-thin" style={{ flex: 1, overflow: 'auto', padding: '6px 4px' }}>
          {artifactList.map((artifact) => (
            <button
              key={artifact.filename}
              className={`file-tree-item ${selectedArtifact?.filename === artifact.filename ? 'selected' : ''}`}
              onClick={() => setSelectedArtifact(artifact)}
            >
              <FileText size={14} style={{ color: 'hsl(195, 70%, 55%)', flexShrink: 0 }} />
              <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {artifact.filename}
              </span>
              <ChevronRight size={12} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
            </button>
          ))}
        </div>
      </div>

      {/* Artifact Content */}
      <div className="card" style={{ overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
        <div
          style={{
            padding: '12px 16px',
            borderBottom: '1px solid var(--border-subtle)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <span className="font-mono" style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
            {selectedArtifact?.filename || 'No artifact selected'}
          </span>
          {selectedArtifact && (
            <button
              onClick={downloadArtifact}
              className="btn-ghost"
              style={{ padding: '4px 12px', fontSize: '0.78rem', display: 'flex', alignItems: 'center', gap: 6 }}
            >
              <Download size={12} />
              Download
            </button>
          )}
        </div>
        <div className="scrollbar-thin" style={{ flex: 1, overflow: 'auto', padding: '24px 32px' }}>
          {contentLoading ? (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', gap: 10 }}>
              <Loader2 size={18} className="animate-spin-slow" style={{ color: 'hsl(225, 80%, 65%)' }} />
              <span style={{ color: 'var(--text-muted)' }}>Loading...</span>
            </div>
          ) : isMarkdown ? (
            <div className="animate-fade-in" style={{ fontSize: '0.9rem', maxWidth: '800px' }}>
              <ReactMarkdown remarkPlugins={[remarkGfm]} components={MarkdownComponents}>
                {content}
              </ReactMarkdown>
            </div>
          ) : (
            <pre className="code-block animate-fade-in" style={{ margin: 0, border: 'none', background: 'transparent', padding: 0 }}>
              {content}
            </pre>
          )}
        </div>
      </div>
    </div>
  );
};

export default ArtifactViewer;
