import React, { useState, useEffect } from 'react';
import { ConfigProvider, Layout, theme } from 'antd';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import MainLayout from './components/layout/MainLayout';
import DashboardPage from './pages/DashboardPage';
import LoginPage from './pages/LoginPage';
import CommandBuilderPage from './pages/CommandBuilderPage';
import HistoryPage from './pages/HistoryPage';
import { AuthProvider } from './hooks/useAuth';
import { WebSocketProvider } from './hooks/useWebSocket';
import { useTranslation } from 'react-i18next';
import { useRTL } from './hooks/useRTL';

const App: React.FC = () => {
  const [isDarkMode, setIsDarkMode] = useState(false);
  const { i18n } = useTranslation();
  const isRTL = useRTL();

  useEffect(() => {
    const savedTheme = localStorage.getItem('theme');
    setIsDarkMode(savedTheme === 'dark');
  }, []);

  const toggleTheme = () => {
    const newTheme = !isDarkMode;
    setIsDarkMode(newTheme);
    localStorage.setItem('theme', newTheme ? 'dark' : 'light');
  };

  return (
    <ConfigProvider
      direction={isRTL ? 'rtl' : 'ltr'}
      theme={{
        algorithm: isDarkMode ? theme.darkAlgorithm : theme.defaultAlgorithm,
        token: {
          colorPrimary: '#1890ff',
        },
      }}
    >
      <AuthProvider>
        <WebSocketProvider>
          <Router>
            <Routes>
              <Route path="/login" element={<LoginPage />} />
              <Route path="/" element={<MainLayout isDarkMode={isDarkMode} toggleTheme={toggleTheme} />}>
                <Route index element={<DashboardPage />} />
                <Route path="command-builder" element={<CommandBuilderPage />} />
                <Route path="history" element={<HistoryPage />} />
              </Route>
            </Routes>
          </Router>
        </WebSocketProvider>
      </AuthProvider>
    </ConfigProvider>
  );
};

export default App;