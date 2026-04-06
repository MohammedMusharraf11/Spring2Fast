import { FileCode, Package, Layers, CheckCircle, AlertTriangle, BookOpen, Zap, XCircle } from 'lucide-react';

const StatsDashboard = ({ state }) => {
  // Read from top-level state fields (not metadata sub-keys)
  const technologies = state?.discovered_technologies || [];
  const businessRules = state?.business_rules || [];
  const validationErrors = state?.validation_errors || [];
  const generatedFiles = state?.generated_files || [];
  const componentInventory = state?.component_inventory || {};
  const completedConversions = state?.completed_conversions || [];
  const failedConversions = state?.failed_conversions || [];

  // Count components across all categories
  const totalComponents = Object.values(componentInventory).reduce(
    (sum, items) => sum + (Array.isArray(items) ? items.length : 0),
    0
  );

  // Conversion stats
  const totalConverted = completedConversions.length + failedConversions.length;
  const passedCount = completedConversions.filter(c => c.passed).length;

  const stats = [
    {
      label: 'Technologies Detected',
      value: technologies.length,
      icon: Package,
      color: 'hsl(270, 70%, 65%)',
      bg: 'hsla(270, 70%, 65%, 0.1)',
    },
    {
      label: 'Components Found',
      value: totalComponents,
      icon: Layers,
      color: 'hsl(155, 65%, 55%)',
      bg: 'hsla(155, 65%, 55%, 0.1)',
    },
    {
      label: 'Business Rules',
      value: businessRules.length,
      icon: CheckCircle,
      color: 'hsl(40, 80%, 55%)',
      bg: 'hsla(40, 80%, 55%, 0.1)',
    },
    {
      label: 'Components Converted',
      value: totalConverted > 0 ? `${passedCount}/${totalConverted}` : '0',
      icon: Zap,
      color: 'hsl(195, 75%, 55%)',
      bg: 'hsla(195, 75%, 55%, 0.1)',
    },
    {
      label: 'Files Generated',
      value: generatedFiles.length,
      icon: FileCode,
      color: 'hsl(225, 80%, 65%)',
      bg: 'hsla(225, 80%, 65%, 0.1)',
    },
    {
      label: 'Validation Errors',
      value: validationErrors.length,
      icon: validationErrors.length > 0 ? AlertTriangle : CheckCircle,
      color: validationErrors.length > 0 ? 'hsl(0, 65%, 60%)' : 'hsl(155, 65%, 55%)',
      bg: validationErrors.length > 0 ? 'hsla(0, 65%, 60%, 0.1)' : 'hsla(155, 65%, 55%, 0.1)',
    },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Stats Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
        {stats.map((stat, index) => {
          const Icon = stat.icon;
          return (
            <div
              key={index}
              className="card"
              style={{ padding: '20px 18px' }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
                <div
                  style={{
                    width: 34,
                    height: 34,
                    borderRadius: 9,
                    background: stat.bg,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  <Icon size={16} style={{ color: stat.color }} />
                </div>
              </div>
              <div style={{ fontSize: '1.75rem', fontWeight: 700, color: 'var(--text-primary)', marginBottom: 2 }}>
                {stat.value}
              </div>
              <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{stat.label}</div>
            </div>
          );
        })}
      </div>

      {/* Conversion Results */}
      {completedConversions.length > 0 && (
        <div className="card" style={{ padding: '18px 20px' }}>
          <h3 style={{ fontWeight: 600, fontSize: '0.9rem', marginBottom: 12, color: 'var(--text-primary)' }}>
            Conversion Results
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {completedConversions.map((conv, i) => (
              <div
                key={i}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: 10,
                  padding: '8px 12px',
                  borderRadius: 8,
                  background: 'var(--surface-2)',
                  fontSize: '0.82rem',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  {conv.passed ? (
                    <CheckCircle size={14} style={{ color: 'hsl(155, 65%, 55%)', flexShrink: 0 }} />
                  ) : (
                    <XCircle size={14} style={{ color: 'hsl(0, 65%, 60%)', flexShrink: 0 }} />
                  )}
                  <span style={{ color: 'var(--text-primary)', fontWeight: 500 }}>{conv.component_name}</span>
                  <span className="badge" style={{
                    fontSize: '0.7rem',
                    padding: '2px 8px',
                    background: 'var(--surface-3)',
                    color: 'var(--text-muted)',
                  }}>
                    {conv.component_type}
                  </span>
                </div>
                <span className="badge" style={{
                  fontSize: '0.7rem',
                  padding: '2px 8px',
                  background: conv.tier_used === 'deterministic' ? 'hsla(155, 65%, 55%, 0.15)' : 'hsla(225, 80%, 65%, 0.15)',
                  color: conv.tier_used === 'deterministic' ? 'hsl(155, 65%, 55%)' : 'hsl(225, 80%, 65%)',
                }}>
                  {conv.tier_used} · {conv.attempts} attempt{conv.attempts !== 1 ? 's' : ''}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Failed Conversions */}
      {failedConversions.length > 0 && (
        <div className="card" style={{ padding: '18px 20px' }}>
          <h3 style={{ fontWeight: 600, fontSize: '0.9rem', marginBottom: 12, color: 'hsl(0, 65%, 65%)' }}>
            <AlertTriangle size={14} style={{ marginRight: 6 }} />
            Failed Conversions ({failedConversions.length})
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {failedConversions.map((conv, i) => (
              <div
                key={i}
                style={{
                  padding: '8px 12px',
                  borderRadius: 8,
                  background: 'hsla(0, 70%, 55%, 0.06)',
                  border: '1px solid hsla(0, 70%, 55%, 0.15)',
                  fontSize: '0.82rem',
                  color: 'hsl(0, 65%, 65%)',
                }}
              >
                <strong>{conv.component_name}</strong>: {conv.error}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Technologies Detected */}
      {technologies.length > 0 && (
        <div className="card" style={{ padding: '18px 20px' }}>
          <h3 style={{ fontWeight: 600, fontSize: '0.9rem', marginBottom: 12, color: 'var(--text-primary)' }}>
            Discovered Technologies
          </h3>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {technologies.map((tech, i) => (
              <span key={i} className="badge badge-purple">
                {tech}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Business Rules Summary */}
      {businessRules.length > 0 && (
        <div className="card" style={{ padding: '18px 20px' }}>
          <h3 style={{ fontWeight: 600, fontSize: '0.9rem', marginBottom: 12, color: 'var(--text-primary)' }}>
            Business Rules ({businessRules.length})
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {businessRules.slice(0, 10).map((rule, i) => (
              <div
                key={i}
                style={{
                  display: 'flex',
                  alignItems: 'start',
                  gap: 10,
                  padding: '8px 12px',
                  borderRadius: 8,
                  background: 'var(--surface-2)',
                  fontSize: '0.82rem',
                  color: 'var(--text-secondary)',
                }}
              >
                <CheckCircle size={14} style={{ color: 'hsl(155, 65%, 55%)', flexShrink: 0, marginTop: 2 }} />
                <span>{rule}</span>
              </div>
            ))}
            {businessRules.length > 10 && (
              <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', textAlign: 'center', padding: 8 }}>
                +{businessRules.length - 10} more rules
              </div>
            )}
          </div>
        </div>
      )}

      {/* Validation Errors */}
      {validationErrors.length > 0 && (
        <div className="card" style={{ padding: '18px 20px' }}>
          <h3 style={{ fontWeight: 600, fontSize: '0.9rem', marginBottom: 12, color: 'hsl(0, 65%, 65%)' }}>
            <AlertTriangle size={14} style={{ marginRight: 6 }} />
            Validation Errors ({validationErrors.length})
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {validationErrors.map((err, i) => (
              <div
                key={i}
                style={{
                  padding: '8px 12px',
                  borderRadius: 8,
                  background: 'hsla(0, 70%, 55%, 0.06)',
                  border: '1px solid hsla(0, 70%, 55%, 0.15)',
                  fontSize: '0.82rem',
                  color: 'hsl(0, 65%, 65%)',
                }}
              >
                {err}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Empty State */}
      {technologies.length === 0 && businessRules.length === 0 && stats.every((s) => s.value === 0 || s.value === '0') && (
        <div style={{ textAlign: 'center', padding: 40, color: 'var(--text-muted)' }}>
          <Package size={36} style={{ margin: '0 auto 12px', opacity: 0.5 }} />
          <p>No data yet — statistics will populate as the pipeline runs.</p>
        </div>
      )}
    </div>
  );
};

export default StatsDashboard;
