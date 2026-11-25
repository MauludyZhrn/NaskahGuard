import React, { useEffect, useState } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { apiFetch } from "./api/client";
import { Layout } from "./components/Layout";
import { AnalyticsOverviewPage } from "./pages/AnalyticsOverviewPage";
import { CorpusPage } from "./pages/CorpusPage";
import { DashboardPage } from "./pages/DashboardPage";
import { DiscoveryMonitorPage } from "./pages/DiscoveryMonitorPage";
import { DocumentsPage } from "./pages/DocumentsPage";
import { HistoryPage } from "./pages/HistoryPage";
import { ModelManagementPage } from "./pages/ModelManagementPage";
import { NewCheckPage } from "./pages/NewCheckPage";
import { ReportDetailPage } from "./pages/ReportDetailPage";
import { RepositoriesPage } from "./pages/RepositoriesPage";
import { RepositoryDetailPage } from "./pages/RepositoryDetailPage";
import { SettingsPage } from "./pages/SettingsPage";
import { AppConfig } from "./types";

export const App: React.FC = () => {
  const [config, setConfig] = useState<AppConfig | null>(null);

  useEffect(() => {
    apiFetch<AppConfig>("/config")
      .then(setConfig)
      .catch(() => undefined);
  }, []);

  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout config={config} />}>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/new-check" element={<NewCheckPage />} />
          <Route path="/history" element={<HistoryPage />} />
          <Route path="/plagiarism-checks" element={<HistoryPage lockedMode="PLAGIARISM_ONLY" />} />
          <Route path="/ai-checks" element={<HistoryPage lockedMode="AI_ONLY" />} />
          <Route path="/combined-reports" element={<HistoryPage lockedMode="COMBINED" />} />
          <Route path="/reports" element={<HistoryPage />} />
          <Route path="/reports/:checkId" element={<ReportDetailPage />} />
          <Route path="/documents" element={<DocumentsPage />} />
          <Route path="/corpus" element={<CorpusPage />} />
          <Route path="/discovery-monitor" element={<DiscoveryMonitorPage />} />
          <Route path="/repositories" element={<RepositoriesPage />} />
          <Route path="/repositories/:repoId" element={<RepositoryDetailPage />} />
          <Route path="/analytics" element={<AnalyticsOverviewPage focusMode="plagiarism" />} />
          <Route path="/analytics/ai" element={<AnalyticsOverviewPage focusMode="ai" />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/models" element={<ModelManagementPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
};

export default App;
