import { NavLink, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  Stethoscope,
  Cpu,
  Truck,
  Activity,
} from 'lucide-react';

const navItems = [
  { path: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { path: '/diagnostics', icon: Stethoscope, label: 'Diagnostics' },
  { path: '/hardware', icon: Cpu, label: 'Hardware Control' },
  { path: '/fleet', icon: Truck, label: 'Fleet Management' },
];

export default function Sidebar({ backendStatus }) {
  const location = useLocation();

  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <div className="logo-icon">
          <Activity size={22} />
        </div>
        <div>
          <h1>VeloPulse</h1>
          <span className="logo-badge">AI</span>
        </div>
      </div>

      <nav className="sidebar-nav">
        <span className="nav-section-label">Main Menu</span>
        {navItems.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            className={({ isActive }) =>
              `nav-item${isActive ? ' active' : ''}`
            }
            end={item.path === '/'}
          >
            <item.icon className="nav-icon" size={20} />
            {item.label}
          </NavLink>
        ))}
      </nav>

      <div className="sidebar-footer">
        <div className="sidebar-status">
          <span
            className={`status-dot${
              backendStatus === 'online' ? '' : ' offline'
            }`}
          />
          <span>
            Backend {backendStatus === 'online' ? 'Connected' : 'Offline'}
          </span>
        </div>
      </div>
    </aside>
  );
}
