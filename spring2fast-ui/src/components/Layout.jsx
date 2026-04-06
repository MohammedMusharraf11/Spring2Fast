import { Link, useLocation } from 'react-router-dom';
import { Home, History, Settings, Zap, Wifi, WifiOff } from 'lucide-react';
import { useApi } from '../context/ApiContext';

const Layout = ({ children }) => {
  const location = useLocation();
  const { connected, checking } = useApi();

  const navItems = [
    { path: '/', icon: Home, label: 'New Migration' },
    { path: '/history', icon: History, label: 'History' },
    { path: '/settings', icon: Settings, label: 'Settings' },
  ];

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
      {/* ─── Sidebar ─── */}
      <aside
        style={{
          width: 260,
          flexShrink: 0,
          display: 'flex',
          flexDirection: 'column',
          background: 'var(--surface-1)',
          borderRight: '1px solid var(--border-subtle)',
        }}
      >
        {/* Brand */}
        <div style={{ padding: '24px 20px', borderBottom: '1px solid var(--border-subtle)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div
              style={{
                width: 40,
                height: 40,
                borderRadius: 10,
                background: 'var(--gradient-brand)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                boxShadow: 'var(--glow-brand)',
              }}
            >
              <Zap size={20} color="white" />
            </div>
            <div>
              <h1 className="gradient-text" style={{ fontSize: '1.15rem', fontWeight: 700, lineHeight: 1.2 }}>
                Spring2Fast
              </h1>
              <p style={{ fontSize: '0.7rem', color: 'var(--text-muted)', letterSpacing: '0.04em' }}>
                Java → FastAPI
              </p>
            </div>
          </div>
        </div>

        {/* Navigation */}
        <nav style={{ flex: 1, padding: '12px 10px' }}>
          <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 4 }}>
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = location.pathname === item.path;
              return (
                <li key={item.path}>
                  <Link
                    to={item.path}
                    id={`nav-${item.path.replace('/', '') || 'home'}`}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 12,
                      padding: '10px 14px',
                      borderRadius: 10,
                      textDecoration: 'none',
                      fontWeight: 500,
                      fontSize: '0.9rem',
                      transition: 'all 0.2s ease',
                      background: isActive ? 'var(--gradient-brand)' : 'transparent',
                      color: isActive ? 'white' : 'var(--text-secondary)',
                      boxShadow: isActive ? 'var(--glow-brand)' : 'none',
                    }}
                  >
                    <Icon size={18} />
                    <span>{item.label}</span>
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>

        {/* Footer: Connection Status */}
        <div
          style={{
            padding: '14px 16px',
            borderTop: '1px solid var(--border-subtle)',
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            fontSize: '0.75rem',
          }}
        >
          {checking ? (
            <>
              <div
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: '50%',
                  background: 'var(--text-muted)',
                }}
                className="animate-pulse-glow"
              />
              <span style={{ color: 'var(--text-muted)' }}>Checking...</span>
            </>
          ) : connected ? (
            <>
              <Wifi size={14} style={{ color: 'hsl(155, 65%, 55%)' }} />
              <span style={{ color: 'hsl(155, 65%, 55%)' }}>Backend connected</span>
            </>
          ) : (
            <>
              <WifiOff size={14} style={{ color: 'hsl(0, 65%, 60%)' }} />
              <span style={{ color: 'hsl(0, 65%, 60%)' }}>Backend offline</span>
            </>
          )}
        </div>
      </aside>

      {/* ─── Main Content ─── */}
      <main
        className="scrollbar-thin"
        style={{ flex: 1, overflow: 'auto', background: 'var(--surface-0)' }}
      >
        {children}
      </main>
    </div>
  );
};

export default Layout;
