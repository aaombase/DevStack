import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api";

export default function Projects() {
  const navigate = useNavigate();
  const [projects, setProjects] = useState(null);
  const [form, setForm] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api("/projects/").then(setProjects).catch((e) => setError(e.message));
  }, []);

  async function create(e) {
    e.preventDefault();
    setError("");
    try {
      const p = await api("/projects/", { method: "POST", body: form });
      navigate(`/p/${p.id}`);
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <>
      <div className="row">
        <h2>Projects</h2>
        <div className="spacer" />
        <button className="btn primary" onClick={() => setForm(form ? null : { name: "", key: "", description: "" })}>
          {form ? "Cancel" : "+ New project"}
        </button>
      </div>

      {form && (
        <form className="card form-grid" onSubmit={create}>
          <label>
            Name
            <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required autoFocus />
          </label>
          <label>
            <span>Key <span className="small">(task prefix, e.g. DEV)</span></span>
            <input
              value={form.key}
              maxLength={10}
              onChange={(e) => setForm({ ...form, key: e.target.value.toUpperCase() })}
              required
            />
          </label>
          <label className="wide">
            Description
            <input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
          </label>
          <button className="btn primary">Create project</button>
        </form>
      )}
      {error && <div className="error">{error}</div>}

      {projects === null && !error && <p className="muted">Loading…</p>}
      {projects?.length === 0 && <p className="muted">No projects yet. Create one to get started.</p>}
      <div className="grid">
        {projects?.map((p) => {
          const pct = p.total_tasks ? Math.round((100 * p.done_tasks) / p.total_tasks) : 0;
          return (
            <Link key={p.id} to={`/p/${p.id}`} className="card project-card">
              <div className="row">
                <strong>{p.name}</strong>
                <span className="chip">{p.key}</span>
              </div>
              <p className="muted small clamp">{p.description || "No description"}</p>
              <div className="progress">
                <div style={{ width: `${pct}%` }} />
              </div>
              <div className="row small muted">
                <span>
                  {p.open_tasks} open · {p.done_tasks} done
                </span>
                <div className="spacer" />
                <span>{p.my_role}</span>
              </div>
            </Link>
          );
        })}
      </div>
    </>
  );
}
