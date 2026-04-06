import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Github, FolderOpen, Upload, ArrowRight, Sparkles } from 'lucide-react';
import GitHubForm from '../components/GitHubForm';
import LocalFolderForm from '../components/LocalFolderForm';
import UploadForm from '../components/UploadForm';

const methods = [
  {
    id: 'github',
    icon: Github,
    title: 'GitHub Repository',
    description: 'Clone from a public or private repo URL',
    accentH: 225,
  },
  {
    id: 'folder',
    icon: FolderOpen,
    title: 'Local Folder',
    description: 'Select a Spring Boot project folder',
    accentH: 270,
  },
  {
    id: 'upload',
    icon: Upload,
    title: 'Upload ZIP',
    description: 'Upload a ZIP archive of your project',
    accentH: 155,
  },
];

const pipelineSteps = [
  { label: 'Ingest source code', color: 'hsl(225, 80%, 60%)' },
  { label: 'Discover technologies & components', color: 'hsl(255, 75%, 60%)' },
  { label: 'Extract business rules', color: 'hsl(285, 70%, 60%)' },
  { label: 'Research Python equivalents', color: 'hsl(195, 80%, 55%)' },
  { label: 'Generate FastAPI scaffold', color: 'hsl(155, 70%, 50%)' },
  { label: 'Validate & assemble output', color: 'hsl(45, 85%, 55%)' },
];

const HomePage = () => {
  const [selectedMethod, setSelectedMethod] = useState('github');
  const navigate = useNavigate();

  const handleJobCreated = (jobId) => {
    navigate(`/job/${jobId}`);
  };

  return (
    <div style={{ maxWidth: 960, margin: '0 auto', padding: '48px 32px' }}>
      {/* Hero */}
      <div className="animate-fade-in" style={{ textAlign: 'center', marginBottom: 48 }}>
        <div
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 8,
            padding: '6px 16px',
            borderRadius: 99,
            fontSize: '0.8rem',
            fontWeight: 600,
            marginBottom: 20,
            background: 'hsla(225, 80%, 60%, 0.1)',
            color: 'hsl(225, 80%, 70%)',
            border: '1px solid hsla(225, 80%, 60%, 0.2)',
          }}
        >
          <Sparkles size={14} />
          AI-Powered Migration
        </div>
        <h1
          className="gradient-text"
          style={{ fontSize: '2.75rem', fontWeight: 800, lineHeight: 1.15, marginBottom: 12 }}
        >
          Start New Migration
        </h1>
        <p style={{ color: 'var(--text-secondary)', fontSize: '1.1rem', maxWidth: 500, margin: '0 auto' }}>
          Transform your Java Spring Boot backend into a modern Python FastAPI project
        </p>
      </div>

      {/* Method Selection */}
      <div
        className="animate-fade-in"
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(3, 1fr)',
          gap: 16,
          marginBottom: 28,
          animationDelay: '0.1s',
        }}
      >
        {methods.map((method) => {
          const Icon = method.icon;
          const isSelected = selectedMethod === method.id;
          return (
            <button
              key={method.id}
              id={`method-${method.id}`}
              onClick={() => setSelectedMethod(method.id)}
              className={isSelected ? 'animate-pulse-glow' : ''}
              style={{
                padding: '28px 20px',
                borderRadius: 16,
                border: `1px solid ${isSelected ? `hsla(${method.accentH}, 70%, 55%, 0.4)` : 'var(--border-subtle)'}`,
                background: isSelected
                  ? `hsla(${method.accentH}, 70%, 55%, 0.08)`
                  : 'var(--surface-1)',
                cursor: 'pointer',
                transition: 'all 0.25s ease',
                textAlign: 'center',
              }}
            >
              <div
                style={{
                  width: 52,
                  height: 52,
                  borderRadius: 14,
                  background: `linear-gradient(135deg, hsl(${method.accentH}, 75%, 55%), hsl(${method.accentH + 30}, 70%, 55%))`,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  margin: '0 auto 14px',
                }}
              >
                <Icon size={24} color="white" />
              </div>
              <h3 style={{ fontWeight: 600, fontSize: '1rem', marginBottom: 4, color: 'var(--text-primary)' }}>
                {method.title}
              </h3>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', margin: 0 }}>
                {method.description}
              </p>
            </button>
          );
        })}
      </div>

      {/* Form Area */}
      <div
        className="glass animate-fade-in"
        style={{ borderRadius: 16, padding: 32, marginBottom: 28, animationDelay: '0.2s' }}
      >
        {selectedMethod === 'github' && <GitHubForm onJobCreated={handleJobCreated} />}
        {selectedMethod === 'folder' && <LocalFolderForm onJobCreated={handleJobCreated} />}
        {selectedMethod === 'upload' && <UploadForm onJobCreated={handleJobCreated} />}
      </div>

      {/* Pipeline Preview */}
      <div
        className="animate-fade-in"
        style={{
          borderRadius: 16,
          padding: '24px 28px',
          background: 'var(--surface-1)',
          border: '1px solid var(--border-subtle)',
          animationDelay: '0.3s',
        }}
      >
        <h4 style={{ fontWeight: 600, color: 'var(--text-primary)', marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
          <ArrowRight size={16} style={{ color: 'hsl(225, 80%, 65%)' }} />
          Migration Pipeline
        </h4>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
          {pipelineSteps.map((step, i) => (
            <div
              key={i}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                padding: '8px 14px',
                borderRadius: 10,
                background: 'var(--surface-2)',
                fontSize: '0.8rem',
                color: 'var(--text-secondary)',
              }}
            >
              <div style={{ width: 6, height: 6, borderRadius: '50%', background: step.color, flexShrink: 0 }} />
              {step.label}
              {i < pipelineSteps.length - 1 && (
                <ArrowRight size={12} style={{ color: 'var(--text-muted)', marginLeft: 2 }} />
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default HomePage;
