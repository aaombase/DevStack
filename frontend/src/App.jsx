import { Link, Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth";
import Login from "./pages/Login";
import Projects from "./pages/Projects";
import ProjectLayout from "./pages/ProjectLayout";
import Board from "./pages/Board";
import Backlog from "./pages/Backlog";
import Sprints from "./pages/Sprints";
import Insights from "./pages/Insights";
import Settings from "./pages/Settings";

function Protected({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="center muted">Loading…</div>;
  return user ? children : <Navigate to="/login" replace />;
}

function Shell({ children }) {
  const { user, logout } = useAuth();
  return (
    <>
      <header className="topbar">
        <Link to="/" className="brand">
          <span className="logo">▦</span> DevTrack
        </Link>
        <div className="spacer" />
        <span className="muted">{user.username}</span>
        <button className="btn ghost" onClick={logout}>
          Log out
        </button>
      </header>
      <main className="page">{children}</main>
    </>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Login register />} />
      <Route
        path="/"
        element={
          <Protected>
            <Shell>
              <Projects />
            </Shell>
          </Protected>
        }
      />
      <Route
        path="/p/:projectId"
        element={
          <Protected>
            <Shell>
              <ProjectLayout />
            </Shell>
          </Protected>
        }
      >
        <Route index element={<Board />} />
        <Route path="backlog" element={<Backlog />} />
        <Route path="sprints" element={<Sprints />} />
        <Route path="insights" element={<Insights />} />
        <Route path="settings" element={<Settings />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
