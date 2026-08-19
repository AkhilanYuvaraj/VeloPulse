import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';
import Header from './Header';

export default function AppLayout({ backendStatus, telemetry }) {
  return (
    <div className="app-layout">
      <Sidebar backendStatus={backendStatus} />
      <Header
        mode={telemetry?.mode}
        uptime={telemetry?.uptime}
        framesReceived={telemetry?.framesReceived}
      />
      <main className="main-content">
        <Outlet />
      </main>
    </div>
  );
}
