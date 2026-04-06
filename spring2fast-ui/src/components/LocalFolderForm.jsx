import { useState } from 'react';
import { FolderOpen, Loader2, Package } from 'lucide-react';
import { useApi } from '../context/ApiContext';
import axios from 'axios';

const LocalFolderForm = ({ onJobCreated }) => {
  const { apiUrl } = useApi();
  const [selectedFolder, setSelectedFolder] = useState('');
  const [loading, setLoading] = useState(false);
  const [zipping, setZipping] = useState(false);
  const [zipProgress, setZipProgress] = useState(0);
  const [error, setError] = useState('');

  const handleSelectFolder = async () => {
    if (!window.electronAPI) {
      setError('Folder selection is only available in the desktop app');
      return;
    }

    const result = await window.electronAPI.selectFolder();
    if (!result.canceled) {
      setSelectedFolder(result.folderPath);
      setError('');
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    setZipping(true);

    try {
      window.electronAPI.onZipProgress((percent) => {
        setZipProgress(percent);
      });

      const zipResult = await window.electronAPI.zipFolder(selectedFolder);
      setZipping(false);

      if (!zipResult.success) {
        throw new Error('Failed to zip folder');
      }

      const formData = new FormData();
      const zipBlob = await fetch(`file://${zipResult.zipPath}`).then((r) => r.blob());
      formData.append('file', zipBlob, 'project.zip');

      const response = await axios.post(`${apiUrl}/api/v1/migrate/upload`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });

      onJobCreated(response.data.job_id);
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to start migration');
    } finally {
      setLoading(false);
      setZipping(false);
      setZipProgress(0);
    }
  };

  return (
    <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div>
        <label
          htmlFor="folder-path"
          style={{ display: 'block', fontSize: '0.85rem', fontWeight: 500, color: 'var(--text-secondary)', marginBottom: 8 }}
        >
          Project Folder
        </label>
        <div style={{ display: 'flex', gap: 10 }}>
          <input
            id="folder-path"
            type="text"
            value={selectedFolder}
            readOnly
            placeholder="No folder selected"
            className="input"
            style={{ flex: 1, cursor: 'default' }}
          />
          <button
            type="button"
            onClick={handleSelectFolder}
            className="btn-ghost"
            style={{ display: 'flex', alignItems: 'center', gap: 8, whiteSpace: 'nowrap' }}
          >
            <FolderOpen size={16} />
            Browse
          </button>
        </div>
      </div>

      {zipping && (
        <div className="alert-info" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <Package size={16} className="animate-spin-slow" />
            <span style={{ fontSize: '0.85rem', fontWeight: 500 }}>Zipping folder... {zipProgress}%</span>
          </div>
          <div className="progress-track">
            <div className="progress-fill" style={{ width: `${zipProgress}%` }} />
          </div>
        </div>
      )}

      {error && (
        <div className="alert-error" style={{ fontSize: '0.85rem' }}>{error}</div>
      )}

      <button
        id="start-folder-migration"
        type="submit"
        disabled={loading || !selectedFolder}
        className="btn-primary"
        style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10 }}
      >
        {loading ? (
          <>
            <Loader2 size={18} className="animate-spin-slow" />
            {zipping ? 'Zipping Folder...' : 'Starting Migration...'}
          </>
        ) : (
          <>
            <FolderOpen size={18} />
            Start Migration
          </>
        )}
      </button>
    </form>
  );
};

export default LocalFolderForm;
