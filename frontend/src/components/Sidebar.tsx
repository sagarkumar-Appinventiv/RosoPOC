import React from 'react';
import { LayoutDashboard, Sparkles, History, GitCompare, Settings } from 'lucide-react';

interface SidebarProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ activeTab, setActiveTab }) => {
  const navItems = [
    { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { id: 'generate', label: 'Content Generation', icon: Sparkles },
    { id: 'history', label: 'History', icon: History },
    { id: 'comparison', label: 'Model Comparison', icon: GitCompare },
    { id: 'settings', label: 'AI / Prompt Settings', icon: Settings },
  ];

  return (
    <aside className="sidebar">
      <div>
        <div 
          className="sidebar-header" 
          onClick={() => setActiveTab('dashboard')} 
          style={{ cursor: 'pointer' }}
        >
          <div className="sidebar-logo">R</div>
          <div className="sidebar-title">
            <h1>RosoTravel</h1>
            <p>AI POC Platform</p>
          </div>
        </div>

        <nav className="sidebar-nav">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <button
                key={item.id}
                className={`nav-item ${activeTab === item.id ? 'active' : ''}`}
                onClick={() => setActiveTab(item.id)}
              >
                <Icon size={18} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>
      </div>

      <div className="sidebar-footer">
        <div className="environment-badge">
          <span>Environment</span>
          <span style={{ color: '#10B981', fontWeight: 600 }}>POC Mode</span>
        </div>
      </div>
    </aside>
  );
};
