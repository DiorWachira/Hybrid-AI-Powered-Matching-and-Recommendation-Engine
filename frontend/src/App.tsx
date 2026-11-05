import { lazy, Suspense, type ReactNode } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { getSessionRole } from "./lib/session";
import { HomePage } from "./pages/HomePage";

const named = <Name extends string>(load: () => Promise<Record<Name, () => ReactNode>>, name: Name) => lazy(async () => ({ default: (await load())[name] }));
const AuthPage = named(() => import("./pages/AuthPage"), "AuthPage");
const CandidatePage = named(() => import("./pages/CandidatePage"), "CandidatePage");
const MatchesPage = named(() => import("./pages/MatchesPage"), "MatchesPage");
const FilledRolesPage = named(() => import("./pages/FilledRolesPage"), "FilledRolesPage");
const NotFoundPage = named(() => import("./pages/NotFoundPage"), "NotFoundPage");
const RecruiterPage = named(() => import("./pages/RecruiterPage"), "RecruiterPage");
const AdminPage = named(() => import("./pages/AdminPage"), "AdminPage");
const SimulationPage = named(() => import("./pages/SimulationPage"), "SimulationPage");
const RecruiterOversightPage = named(() => import("./pages/RecruiterOversightPage"), "RecruiterOversightPage");
const SecurityPage = named(() => import("./pages/SecurityPage"), "SecurityPage");
const PublicInfoPage = lazy(async () => ({ default: (await import("./pages/PublicInfoPage")).PublicInfoPage }));

function WorkspaceRoute({ children, roles }: { children: ReactNode; roles: Array<"candidate" | "recruiter" | "admin"> }) {
  const role = getSessionRole();
  if (!role) return <Navigate to="/auth" replace />;
  if (!roles.includes(role)) return <Navigate to={role === "candidate" ? "/candidate" : role === "admin" ? "/admin" : "/recruiter"} replace />;
  return <AppShell><Suspense fallback={<RouteLoading />}>{children}</Suspense></AppShell>;
}

function RouteLoading() {
  return <div className="route-status" role="status" aria-label="Loading page"><span className="route-status-spinner" aria-hidden="true" /></div>;
}

export default function App() {
  return (
    <ErrorBoundary>
    <BrowserRouter>
      <Suspense fallback={<RouteLoading />}>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/privacy" element={<PublicInfoPage kind="privacy" />} />
        <Route path="/terms" element={<PublicInfoPage kind="terms" />} />
        <Route path="/auth" element={<AuthPage />} />
        <Route path="/recruiter" element={<WorkspaceRoute roles={["recruiter"]}><RecruiterPage /></WorkspaceRoute>} />
        <Route path="/candidate" element={<WorkspaceRoute roles={["candidate"]}><CandidatePage /></WorkspaceRoute>} />
        <Route path="/filled-roles" element={<WorkspaceRoute roles={["recruiter"]}><FilledRolesPage /></WorkspaceRoute>} />
        <Route path="/matches" element={<WorkspaceRoute roles={["recruiter", "admin"]}><MatchesPage /></WorkspaceRoute>} />
        <Route path="/admin" element={<WorkspaceRoute roles={["admin"]}><AdminPage /></WorkspaceRoute>} />
        <Route path="/admin/recruiters" element={<WorkspaceRoute roles={["admin"]}><RecruiterOversightPage /></WorkspaceRoute>} />
        <Route path="/admin/jobs" element={<Navigate to="/admin/recruiters" replace />} />
        <Route path="/admin/simulation" element={<WorkspaceRoute roles={["admin"]}><SimulationPage /></WorkspaceRoute>} />
        <Route path="/security" element={<WorkspaceRoute roles={["candidate", "recruiter", "admin"]}><SecurityPage /></WorkspaceRoute>} />
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
      </Suspense>
    </BrowserRouter>
    </ErrorBoundary>
  );
}
