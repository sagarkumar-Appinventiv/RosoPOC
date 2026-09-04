import React from 'react';
import { RefreshCw } from 'lucide-react';

interface HeaderProps {
  title: string;
  onReset?: () => void;
}

export const Header: React.FC<HeaderProps> = ({ title, onReset }) => {
  return (
    <header className="top-navbar">
      <div className="workspace-container" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <h2 className="page-title">{title}</h2>
        <div style={{ display: 'flex', gap: '12px' }}>
          {onReset && (
            <button className="btn-secondary" onClick={onReset} style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <RefreshCw size={14} />
              <span>Reset All</span>
            </button>
          )}
          <button 
            className="btn-secondary" 
            onClick={() => {
              sessionStorage.removeItem('roso_session_token');
              window.location.reload();
            }} 
            style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#DC2626', borderColor: '#FECACA', backgroundColor: '#FEF2F2' }}
          >
            <span>Logout</span>
          </button>
        </div>
      </div>
    </header>
  );
};
