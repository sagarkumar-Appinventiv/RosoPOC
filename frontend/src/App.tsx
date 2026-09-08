import { useState } from 'react';
import { Sidebar } from './components/Sidebar';
import { Header } from './components/Header';
import { DashboardPage } from './pages/DashboardPage';
import { ContentGenerationPage } from './pages/ContentGenerationPage';
import { HistoryPage } from './pages/HistoryPage';
import { ModelComparisonPage } from './pages/ModelComparisonPage';
import { SettingsPage } from './pages/SettingsPage';
import { OpenRouterKeyPage } from './pages/OpenRouterKeyPage';
import { TranslationPage } from './pages/TranslationPage';
import { RunDetailDrawer } from './components/RunDetailDrawer';
import { ActiveGenerationProvider } from './context/ActiveGenerationContext';

export function App() {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(() => {
    return !!sessionStorage.getItem('roso_session_token');
  });
  const [activeTab, setActiveTab] = useState<string>('dashboard');
  const [activeRunDetailId, setActiveRunDetailId] = useState<string | null>(null);

  if (!isAuthenticated) {
    return <OpenRouterKeyPage onSuccess={() => setIsAuthenticated(true)} />;
  }

  const pageTitles: Record<string, string> = {
    dashboard: 'Dashboard Overview',
    generate: 'Content Generation Interface',
    history: 'History Runs & Audit Trail',
    translation: 'Content Translation',
    comparison: 'Side-by-Side Model Comparison',
    settings: 'AI / Prompt Settings Configuration'
  };

  return (
    <ActiveGenerationProvider>
      <div className="app-container">
      <Sidebar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
      />

      <div className="main-content">
        <Header title={pageTitles[activeTab] || 'RosoTravel AI POC'} />

        <main className="content-body">
          {activeTab === 'dashboard' && (
            <DashboardPage onNavigateToHistory={() => setActiveTab('history')} />
          )}

          {activeTab === 'generate' && <ContentGenerationPage />}

          {activeTab === 'history' && <HistoryPage />}

          {activeTab === 'translation' && <TranslationPage />}

          {activeTab === 'comparison' && <ModelComparisonPage />}

          {activeTab === 'settings' && <SettingsPage />}
        </main>
      </div>

      {activeRunDetailId && (
        <RunDetailDrawer
          runId={activeRunDetailId}
          onClose={() => setActiveRunDetailId(null)}
        />
      )}
      </div>
    </ActiveGenerationProvider>
  );
}

export default App;
