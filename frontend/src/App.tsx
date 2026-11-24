import React, { useEffect, useState } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { apiFetch } from "./api/client";
import { Layout } from "./components/Layout";
import { CorpusPage } from "./pages/CorpusPage";
import { DashboardPage } from "./pages/DashboardPage";
import { DocumentsPage } from "./pages/DocumentsPage";
import { HistoryPage } from "./pages/HistoryPage";
import { NewCheckPage } from "./pages/NewCheckPage";
import { ReportDetailPage } from "./pages/ReportDetailPage";
import { ReportsListPage } from "./pages/ReportsListPage";
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
          <Route path="/documents" element={<DocumentsPage />} />
          <Route path="/corpus" element={<CorpusPage />} />
          <Route path="/reports" element={<ReportsListPage />} />
          <Route path="/reports/:checkId" element={<ReportDetailPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
};

export default App;
