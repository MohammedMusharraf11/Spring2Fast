import { useState, useEffect, useCallback } from 'react';
import { useApi } from '../context/ApiContext';
import { Folder, FileCode, ChevronRight, ChevronDown, Loader2, FolderOpen } from 'lucide-react';

const SourceFileBrowser = ({ jobId }) => {
  const { get } = useApi();
  const [tree, setTree] = useState([]);
  const [totalFiles, setTotalFiles] = useState(0);
  const [loading, setLoading] = useState(true);
  const [selectedFile, setSelectedFile] = useState(null);
  const [fileContent, setFileContent] = useState('');
  const [fileLoading, setFileLoading] = useState(false);
  const [expanded, setExpanded] = useState({});

  const fetchTree = useCallback(async () => {
    try {
      const response = await get(`/api/v1/migrate/${jobId}/source-tree`);
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
      const response = await get(`/api/v1/migrate/${jobId}/source-file`, {
        params: { path: filePath },
      });
      setFileContent(response.data.content || '');
    } catch {
      setFileContent('// Failed to load file content');
    } finally {
      setFileLoading(false);
    }
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
            <Folder size={14} style={{ color: 'hsl(40, 80%, 55%)' }} />
          ) : (
            <FileCode size={14} style={{ color: getFileColor(node.extension) }} />
          )}
          <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {node.name}
          </span>
          {!isDir && node.size != null && (
            <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', flexShrink: 0 }}>
              {formatSize(node.size)}
            </span>
          )}
        </button>
        {isDir && isExpanded && node.children?.map((child) => renderNode(child, depth + 1))}
      </div>
    );
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 60, gap: 10 }}>
        <Loader2 size={20} className="animate-spin-slow" style={{ color: 'hsl(225, 80%, 65%)' }} />
        <span style={{ color: 'var(--text-muted)' }}>Loading source tree...</span>
      </div>
    );
  }

  if (tree.length === 0) {
    return (
      <div style={{ textAlign: 'center', padding: 60, color: 'var(--text-muted)' }}>
        <FolderOpen size={36} style={{ margin: '0 auto 12px', opacity: 0.5 }} />
        <p>No source files available yet.</p>
        <p style={{ fontSize: '0.8rem' }}>Files will appear here once the project is ingested.</p>
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
            Source Files
          </span>
          <span className="badge badge-blue">{totalFiles} files</span>
        </div>
        <div className="scrollbar-thin" style={{ flex: 1, overflow: 'auto', padding: '6px 4px' }}>
          {tree.map((node) => renderNode(node))}
        </div>
      </div>

      {/* File Content Panel */}
      <div className="card" style={{ overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
        <div
          style={{
            padding: '12px 16px',
            borderBottom: '1px solid var(--border-subtle)',
            display: 'flex',
            alignItems: 'center',
            gap: 8,
          }}
        >
          <FileCode size={14} style={{ color: 'var(--text-muted)' }} />
          <span className="font-mono" style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
            {selectedFile || 'Select a file to view'}
          </span>
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
              <FileCode size={32} style={{ opacity: 0.3, marginBottom: 8 }} />
              <p style={{ fontSize: '0.85rem' }}>Select a file from the tree to preview</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

function getFileColor(ext) {
  const colors = {
    '.java': 'hsl(20, 85%, 55%)',
    '.xml': 'hsl(0, 65%, 60%)',
    '.yml': 'hsl(285, 60%, 60%)',
    '.yaml': 'hsl(285, 60%, 60%)',
    '.properties': 'hsl(40, 80%, 55%)',
    '.gradle': 'hsl(155, 60%, 50%)',
    '.kt': 'hsl(270, 70%, 60%)',
    '.json': 'hsl(45, 85%, 55%)',
    '.md': 'hsl(195, 70%, 55%)',
    '.py': 'hsl(210, 70%, 60%)',
  };
  return colors[ext] || 'var(--text-muted)';
}

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes}B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)}MB`;
}

export default SourceFileBrowser;
