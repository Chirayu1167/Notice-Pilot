import { HashRouter, Routes, Route, Navigate } from "react-router-dom";
import { AppShell } from "./components/layout/AppShell";
import { DashboardPage } from "./pages/DashboardPage";
import { NoticesPage } from "./pages/NoticesPage";
import { NoticeDetailPage } from "./pages/NoticeDetailPage";
import { ReconciliationPage } from "./pages/ReconciliationPage";
import { EvidencePage } from "./pages/EvidencePage";
import { RepliesPage } from "./pages/RepliesPage";
import { SettingsPage } from "./pages/SettingsPage";

function AppRoutes() {
  return (
    <AppShell>
      <Routes>
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/notices" element={<NoticesPage />} />
        <Route path="/notices/:id" element={<NoticeDetailPage />} />
        <Route path="/reconciliation" element={<ReconciliationPage />} />
        <Route path="/evidence" element={<EvidencePage />} />
        <Route path="/replies" element={<RepliesPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </AppShell>
  );
}

export function App() {
  return (
    <HashRouter>
      <AppRoutes />
    </HashRouter>
  );
}
