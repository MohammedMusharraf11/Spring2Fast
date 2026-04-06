import { useState } from 'react';
import { Github, Loader2 } from 'lucide-react';
import { useApi } from '../context/ApiContext';

const GitHubForm = ({ onJobCreated }) => {
  const { post } = useApi();
  const [githubUrl, setGithubUrl] = useState('');
  const [branch, setBranch] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const response = await post('/api/v1/migrate/github', {
        github_url: githubUrl,
        branch: branch || null,
      });
      onJobCreated(response.data.job_id);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to start migration');
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div>
        <label
          htmlFor="github-url"
          style={{ display: 'block', fontSize: '0.85rem', fontWeight: 500, color: 'var(--text-secondary)', marginBottom: 8 }}
        >
          GitHub Repository URL
        </label>
        <input
          id="github-url"
          type="url"
          value={githubUrl}
          onChange={(e) => setGithubUrl(e.target.value)}
          placeholder="https://github.com/username/spring-boot-project"
          required
          className="input"
        />
      </div>

      <div>
        <label
          htmlFor="github-branch"
          style={{ display: 'block', fontSize: '0.85rem', fontWeight: 500, color: 'var(--text-secondary)', marginBottom: 8 }}
        >
          Branch <span style={{ color: 'var(--text-muted)', fontWeight: 400 }}>(optional)</span>
        </label>
        <input
          id="github-branch"
          type="text"
          value={branch}
          onChange={(e) => setBranch(e.target.value)}
          placeholder="main"
          className="input"
        />
        <p style={{ marginTop: 6, fontSize: '0.78rem', color: 'var(--text-muted)' }}>
          Leave empty to use the default branch
        </p>
      </div>

      {error && (
        <div className="alert-error" style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: '0.85rem' }}>
          {error}
        </div>
      )}

      <button
        id="start-github-migration"
        type="submit"
        disabled={loading}
        className="btn-primary"
        style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10 }}
      >
        {loading ? (
          <>
            <Loader2 size={18} className="animate-spin-slow" />
            Starting Migration...
          </>
        ) : (
          <>
            <Github size={18} />
            Start Migration
          </>
        )}
      </button>
    </form>
  );
};

export default GitHubForm;
