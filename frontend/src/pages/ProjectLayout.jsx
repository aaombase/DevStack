import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { NavLink, Outlet, useParams } from "react-router-dom";
import { api, canEdit, canManage } from "../api";

const ProjectContext = createContext(null);
export const useProject = () => useContext(ProjectContext);

export default function ProjectLayout() {
  const { projectId } = useParams();
  const [state, setState] = useState({ project: null, members: [], sprints: [], error: "" });

  const reload = useCallback(async () => {
    try {
      const [project, members, sprints] = await Promise.all([
        api(`/projects/${projectId}/`),
        api(`/projects/${projectId}/members/`),
        api("/sprints/", { params: { project: projectId } }),
      ]);
      setState({ project, members, sprints, error: "" });
    } catch (err) {
      setState((s) => ({ ...s, error: err.status === 404 ? "Project not found." : err.message }));
    }
  }, [projectId]);

  useEffect(() => {
    setState({ project: null, members: [], sprints: [], error: "" });
    reload();
  }, [reload]);

  if (state.error) return <div className="error">{state.error}</div>;
  if (!state.project) return <p className="muted">Loading…</p>;

  const { project } = state;
  const value = {
    ...state,
    reload,
    role: project.my_role,
    canEdit: canEdit(project.my_role),
    canManage: canManage(project.my_role),
  };

  return (
    <ProjectContext.Provider value={value}>
      <div className="row">
        <h2>{project.name}</h2>
        <span className="chip">{project.key}</span>
        <div className="spacer" />
        <span className="muted small">you are {project.my_role}</span>
      </div>
      <nav className="tabs">
        <NavLink end to="">Board</NavLink>
        <NavLink to="backlog">Backlog</NavLink>
        <NavLink to="sprints">Sprints</NavLink>
        <NavLink to="insights">Insights</NavLink>
        <NavLink to="settings">Settings</NavLink>
      </nav>
      <Outlet />
    </ProjectContext.Provider>
  );
}
