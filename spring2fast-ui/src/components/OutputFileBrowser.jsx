import { useState, useEffect, useCallback } from 'react';
import { useApi } from '../context/ApiContext';
import { Folder, FileCode, ChevronRight, ChevronDown, Loader2, Code2, Copy, CheckCircle2 } from 'lucide-react';

const OutputFileBrowser = ({ jobId }) => {
  const { get } = useApi();
  const [tree, setTree] = useState([]);
  const [totalFiles, setTotalFiles] = useState(0);
  const [loading, setLoading] = useState(true);
  const [selectedFile, setSelectedFile] = useState(null);
  const [fileContent, setFileContent] = useState('');
  const [fileLoading, setFileLoading] = useState(false);
  const [expanded, setExpanded] = useState({});
  const [copied, setCopied] = useState(false);

  const fetchTree = useCallback(async () => {
    try {
      const response = await get(`/api/v1/migrate/${jobId}/output-tree`);
      setTree(response.data.tree || []);
      setTotalFiles(response.data.total_files || 0);
    } catch {
      setTree([]);
    } finally {
      setLoading(false);
    }
  }, [get, jobId]);

  useEffect(() => {
    fetchTree();
  }, [fetchTree]);

  const toggleExpand = (path) => {
    setExpanded((prev) => ({ ...prev, [path]: !prev[path] }));
  };

  const handleFileClick = async (filePath) => {
    setSelectedFile(filePath);
    setFileLoading(true);
    try {
      const response = await get(`/api/v1/migrate/${jobId}/output-file`, {
        params: { path: filePath },
      });
      setFileContent(response.data.content || '');
    } catch {
      setFileContent('# Failed to load file content');
    } finally {
      setFileLoading(false);
    }
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(fileContent);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const renderNode = (node, depth = 0) => {
    const isDir = node.type === 'directory';
    const isExpanded = expanded[node.path];

    return (
      <div key={node.path}>
        <button
          className={`file-tree-item ${selectedFile === node.path ? 'selected' : ''}`}
          onClick={() => (isDir ? toggleExpand(node.path) : handleFileClick(node.path))}
          style={{ paddingLeft: 10 + depth * 18 }}
        >
          {isDir ? (
            isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />
          ) : null}
          {isDir ? (
            <Folder size={14} style={{ color: 'hsl(225, 75%, 60%)' }} />
          ) : (
            <FileCode size={14} style={{ color: getFileColor(node.extension) }} />
          )}
          <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {node.name}
          </span>
        </button>
        {isDir && isExpanded && node.children?.map((child) => renderNode(child, depth + 1))}
      </div>
    );
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 60, gap: 10 }}>
        <Loader2 size={20} className="animate-spin-slow" style={{ color: 'hsl(225, 80%, 65%)' }} />
        <span style={{ color: 'var(--text-muted)' }}>Loading output tree...</span>
      </div>
    );
  }

  if (tree.length === 0) {
    return (
      <div style={{ textAlign: 'center', padding: 60, color: 'var(--text-muted)' }}>
        <Code2 size={36} style={{ margin: '0 auto 12px', opacity: 0.5 }} />
        <p>No generated files yet.</p>
        <p style={{ fontSize: '0.8rem' }}>Generated FastAPI code will appear here after the migration completes.</p>
      </div>
    );
  }

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '320px 1fr', gap: 16, height: 560 }}>
      {/* File Tree Panel */}
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
          <span style={{ fontWeight: 600, fontSize: '0.85rem', color: 'var(--text-primary)' }}>
            Generated Files
          </span>
          <span className="badge badge-green">{totalFiles} files</span>
        </div>
        <div className="scrollbar-thin" style={{ flex: 1, overflow: 'auto', padding: '6px 4px' }}>
          {tree.map((node) => renderNode(node))}
        </div>
      </div>

      {/* Code Viewer Panel */}
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
            {selectedFile || 'Select a file to preview'}
          </span>
          {selectedFile && (
            <button
              onClick={handleCopy}
              className="btn-ghost"
              style={{ padding: '4px 12px', fontSize: '0.78rem', display: 'flex', alignItems: 'center', gap: 6 }}
            >
              {copied ? (
                <>
                  <CheckCircle2 size={12} style={{ color: 'hsl(155, 65%, 55%)' }} />
                  Copied
                </>
              ) : (
                <>
                  <Copy size={12} />
                  Copy
                </>
              )}
            </button>
          )}
        </div>
        <div className="scrollbar-thin" style={{ flex: 1, overflow: 'auto', padding: 16 }}>
          {fileLoading ? (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', gap: 10 }}>
              <Loader2 size={18} className="animate-spin-slow" style={{ color: 'hsl(225, 80%, 65%)' }} />
              <span style={{ color: 'var(--text-muted)' }}>Loading...</span>
            </div>
          ) : selectedFile ? (
            <pre className="code-block" style={{ margin: 0, border: 'none', background: 'transparent', padding: 0 }}>
              {fileContent}
            </pre>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-muted)' }}>
              <Code2 size={32} style={{ opacity: 0.3, marginBottom: 8 }} />
              <p style={{ fontSize: '0.85rem' }}>Select a generated file to preview its code</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

function getFileColor(ext) {
  const colors = {
    '.py': 'hsl(210, 70%, 60%)',
    '.txt': 'var(--text-muted)',
    '.toml': 'hsl(155, 55%, 50%)',
    '.cfg': 'hsl(40, 80%, 55%)',
    '.json': 'hsl(45, 85%, 55%)',
    '.yml': 'hsl(285, 60%, 60%)',
    '.yaml': 'hsl(285, 60%, 60%)',
    '.md': 'hsl(195, 70%, 55%)',
    '.env': 'hsl(40, 70%, 50%)',
    '.dockerfile': 'hsl(210, 70%, 55%)',
  };
  return colors[ext] || 'var(--text-muted)';
}

export default OutputFileBrowser;
