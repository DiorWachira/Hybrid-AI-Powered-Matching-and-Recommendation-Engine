import { type ReactNode } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { AuthPage } from "./pages/AuthPage";
import { CandidatePage } from "./pages/CandidatePage";
import { MatchesPage } from "./pages/MatchesPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { RecruiterPage } from "./pages/RecruiterPage";

function WorkspaceRoute({ children }: { children: ReactNode }) {
  return <AppShell>{children}</AppShell>;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to="/recruiter" replace />} />
        <Route path="/auth" element={<AuthPage />} />
        <Route path="/recruiter" element={<WorkspaceRoute><RecruiterPage /></WorkspaceRoute>} />
        <Route path="/candidate" element={<WorkspaceRoute><CandidatePage /></WorkspaceRoute>} />
        <Route path="/matches" element={<WorkspaceRoute><MatchesPage /></WorkspaceRoute>} />
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </BrowserRouter>
  );
}
