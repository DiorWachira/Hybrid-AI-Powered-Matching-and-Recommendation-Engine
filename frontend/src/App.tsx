import { type ReactNode } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { AuthPage } from "./pages/AuthPage";
import { CandidatePage } from "./pages/CandidatePage";
import { MatchesPage } from "./pages/MatchesPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { RecruiterPage } from "./pages/RecruiterPage";
import { AdminPage } from "./pages/AdminPage";
import { getSessionRole } from "./lib/session";

function WorkspaceRoute({ children, roles }: { children: ReactNode; roles: Array<"candidate" | "recruiter" | "admin"> }) {
  const role = getSessionRole();
  if (!role) return <Navigate to="/auth" replace />;
  if (!roles.includes(role)) return <Navigate to={role === "candidate" ? "/candidate" : role === "admin" ? "/admin" : "/recruiter"} replace />;
  return <AppShell>{children}</AppShell>;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to="/recruiter" replace />} />
        <Route path="/auth" element={<AuthPage />} />
        <Route path="/recruiter" element={<WorkspaceRoute roles={["recruiter", "admin"]}><RecruiterPage /></WorkspaceRoute>} />
        <Route path="/candidate" element={<WorkspaceRoute roles={["candidate"]}><CandidatePage /></WorkspaceRoute>} />
        <Route path="/matches" element={<WorkspaceRoute roles={["recruiter", "admin"]}><MatchesPage /></WorkspaceRoute>} />
        <Route path="/admin" element={<WorkspaceRoute roles={["admin"]}><AdminPage /></WorkspaceRoute>} />
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </BrowserRouter>
  );
}
