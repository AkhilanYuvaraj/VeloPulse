import { useLocation } from 'react-router-dom';
import { Signal, Clock } from 'lucide-react';
import { formatUptime } from '../../utils/formatters';

const pageTitles = {
  '/': 'Dashboard',
  '/diagnostics': 'Diagnostics',
  '/hardware': 'Hardware Control',
  '/fleet': 'Fleet Management',
};

const pageBreadcrumbs = {
  '/': 'Real-time Vehicle Monitoring',
  '/diagnostics': 'ML Predictions & SHAP Analysis',
  '/hardware': 'Sensor Configuration & Fault Injection',
  '/fleet': 'Multi-Vehicle Fleet Overview',
};

export default function Header({ mode, uptime, framesReceived }) {
  const location = useLocation();
  const title = pageTitles[location.pathname] || 'VeloPulseAI';
  const breadcrumb = pageBreadcrumbs[location.pathname] || '';

  return (
    <header className="header">
      <div className="header-left">
        <div>
          <h2>{title}</h2>
          <span className="header-breadcrumb">{breadcrumb}</span>
        </div>
      </div>

      <div className="header-right">
        <div className="header-stat">
          <Signal size={14} />
          <span className="stat-value">{mode || '--'}</span>
        </div>

        <div className="header-stat">
          <Clock size={14} />
          Uptime: <span className="stat-value">{formatUptime(uptime)}</span>
        </div>

        <div className="header-stat">
          Frames: <span className="stat-value">{framesReceived || 0}</span>
        </div>
      </div>
    </header>
  );
}
