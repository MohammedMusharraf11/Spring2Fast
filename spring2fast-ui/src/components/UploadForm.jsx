import { useState } from 'react';
import { Upload, Loader2, FileArchive, X } from 'lucide-react';
import { useApi } from '../context/ApiContext';
import axios from 'axios';

const UploadForm = ({ onJobCreated }) => {
  const { apiUrl } = useApi();
  const [selectedFile, setSelectedFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [error, setError] = useState('');

  const handleFileSelect = (e) => {
    const file = e.target.files[0];
    if (file) {
      if (!file.name.endsWith('.zip')) {
        setError('Please select a ZIP file');
        return;
      }
      setSelectedFile(file);
      setError('');
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file) {
      if (!file.name.endsWith('.zip')) {
        setError('Please select a ZIP file');
        return;
      }
      setSelectedFile(file);
      setError('');
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!selectedFile) return;

    setError('');
    setLoading(true);

    try {
      const formData = new FormData();
      formData.append('file', selectedFile);

      const response = await axios.post(`${apiUrl}/api/v1/migrate/upload`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: (progressEvent) => {
          const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          setUploadProgress(percent);
        },
      });

      onJobCreated(response.data.job_id);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to upload file');
    } finally {
      setLoading(false);
      setUploadProgress(0);
    }
  };

  return (
    <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div
        onDrop={handleDrop}
        onDragOver={(e) => e.preventDefault()}
        style={{
          border: '2px dashed var(--border-default)',
          borderRadius: 14,
          padding: 40,
          textAlign: 'center',
          cursor: 'pointer',
          transition: 'all 0.2s ease',
          background: 'var(--surface-2)',
        }}
      >
        {selectedFile ? (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 12 }}>
            <FileArchive size={28} style={{ color: 'hsl(155, 65%, 55%)' }} />
            <div style={{ textAlign: 'left' }}>
              <p style={{ fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>{selectedFile.name}</p>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', margin: 0 }}>
                {(selectedFile.size / 1024 / 1024).toFixed(2)} MB
              </p>
            </div>
            <button
              type="button"
              onClick={() => setSelectedFile(null)}
              style={{
                marginLeft: 12,
                padding: 6,
                borderRadius: 8,
                border: 'none',
                background: 'var(--surface-3)',
                cursor: 'pointer',
                color: 'var(--text-muted)',
              }}
            >
              <X size={16} />
            </button>
          </div>
        ) : (
          <>
            <Upload size={36} style={{ color: 'var(--text-muted)', margin: '0 auto 12px' }} />
            <p style={{ color: 'var(--text-secondary)', marginBottom: 12 }}>
              Drag and drop your ZIP file here, or
            </p>
            <label className="btn-success" style={{ display: 'inline-flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
              Browse Files
              <input type="file" accept=".zip" onChange={handleFileSelect} style={{ display: 'none' }} />
            </label>
          </>
        )}
      </div>

      {loading && (
        <div className="alert-info" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <Loader2 size={16} className="animate-spin-slow" />
            <span style={{ fontSize: '0.85rem', fontWeight: 500 }}>Uploading... {uploadProgress}%</span>
          </div>
          <div className="progress-track">
            <div className="progress-fill" style={{ width: `${uploadProgress}%` }} />
          </div>
        </div>
      )}

      {error && (
        <div className="alert-error" style={{ fontSize: '0.85rem' }}>{error}</div>
      )}

      <button
        id="start-upload-migration"
        type="submit"
        disabled={loading || !selectedFile}
        className="btn-primary"
        style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10 }}
      >
        {loading ? (
          <>
            <Loader2 size={18} className="animate-spin-slow" />
            Uploading...
          </>
        ) : (
          <>
            <Upload size={18} />
            Start Migration
          </>
        )}
      </button>
    </form>
  );
};

export default UploadForm;
