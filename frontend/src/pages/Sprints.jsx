import { useState } from "react";
import { api } from "../api";
import { LineChart, Legend } from "../components/Charts";
import Markdown from "../components/Markdown";
import { useProject } from "./ProjectLayout";

const today = () => new Date().toISOString().slice(0, 10);
const inDays = (n) => new Date(Date.now() + n * 864e5).toISOString().slice(0, 10);

export default function Sprints() {
  const { project, sprints, reload, canManage } = useProject();
  const [form, setForm] = useState(null);
  const [error, setError] = useState("");
  const [report, setReport] = useState(null);
  const [copied, setCopied] = useState(false);
  const [completing, setCompleting] = useState(null); // {sprint, target}

  async function run(fn) {
    setError("");
    try {
      await fn();
      await reload();
    } catch (err) {
      setError(err.message);
    }
  }

  const create = (e) => {
    e.preventDefault();
    run(async () => {
      await api("/sprints/", { method: "POST", body: { ...form, project: project.id } });
      setForm(null);
    });
  };

  const confirmComplete = (e) => {
    e.preventDefault();
    const { sprint, target } = completing;
    setCompleting(null);
    run(() =>
      api(`/sprints/${sprint.id}/complete/`, {
        method: "POST",
        body: { move_unfinished_to: target === "backlog" ? "backlog" : Number(target) },
      }),
    );
  };

  async function showReport(s) {
    setError("");
    setCopied(false);
    try {
      setReport(await api(`/sprints/${s.id}/report/`));
    } catch (err) {
      setError(err.message);
    }
  }

  async function copy() {
    await navigator.clipboard.writeText(report.markdown);
    setCopied(true);
  }

  return (
    <>
      <div className="row">
        <h3>Sprints</h3>
        <div className="spacer" />
        {canManage && (
          <button
            className="btn primary"
            onClick={() => setForm(form ? null : { name: `Sprint ${sprints.length + 1}`, goal: "", start_date: today(), end_date: inDays(13) })}
          >
            {form ? "Cancel" : "+ New sprint"}
          </button>
        )}
      </div>

      {form && (
        <form className="card form-grid" onSubmit={create}>
          <label>Name<input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required /></label>
          <label>Goal<input value={form.goal} onChange={(e) => setForm({ ...form, goal: e.target.value })} /></label>
          <label>Start<input type="date" value={form.start_date} onChange={(e) => setForm({ ...form, start_date: e.target.value })} required /></label>
          <label>End<input type="date" value={form.end_date} onChange={(e) => setForm({ ...form, end_date: e.target.value })} required /></label>
          <button className="btn primary">Create sprint</button>
        </form>
      )}
      {error && <div className="error">{error}</div>}
      {sprints.length === 0 && <p className="muted">No sprints yet.</p>}

      <div className="stack">
        {sprints.map((s) => (
          <div key={s.id} className="card">
            <div className="row">
              <strong>{s.name}</strong>
              <span className={`status s-${s.status}`}>{s.status}</span>
              <div className="spacer" />
              <span className="muted small">{s.start_date} → {s.end_date}</span>
            </div>
            {s.goal && <p className="muted">{s.goal}</p>}
            <div className="row small muted">
              <span>{s.task_count} tasks · {s.total_points ?? 0} pts</span>
              {s.status === "completed" && <span>· delivered {s.completed_points}/{s.committed_points} pts</span>}
              <div className="spacer" />
              <button className="btn" onClick={() => showReport(s)}>Report</button>
              {canManage && s.status === "planned" && (
                <button className="btn" onClick={() => run(() => api(`/sprints/${s.id}/start/`, { method: "POST" }))}>Start</button>
              )}
              {canManage && s.status === "active" && (
                <button className="btn primary" onClick={() => setCompleting({ sprint: s, target: "backlog" })}>Complete</button>
              )}
              {canManage && s.status !== "active" && (
                <button
                  className="btn ghost"
                  onClick={() => window.confirm(`Delete ${s.name}? Its tasks return to the backlog.`) && run(() => api(`/sprints/${s.id}/`, { method: "DELETE" }))}
                >
                  Delete
                </button>
              )}
            </div>
          </div>
        ))}
      </div>

      {completing && (
        <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && setCompleting(null)}>
          <form className="modal card" onSubmit={confirmComplete}>
            <h3>Complete {completing.sprint.name}</h3>
            <p className="muted">
              Finished tasks stay in this sprint's report. Where should unfinished tasks go?
            </p>
            <label>
              Move unfinished tasks to
              <select value={completing.target} onChange={(e) => setCompleting({ ...completing, target: e.target.value })}>
                <option value="backlog">Backlog</option>
                {sprints
                  .filter((o) => o.id !== completing.sprint.id && o.status !== "completed")
                  .map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
              </select>
            </label>
            <div className="row">
              <button className="btn primary">Complete sprint</button>
              <button type="button" className="btn ghost" onClick={() => setCompleting(null)}>Cancel</button>
            </div>
          </form>
        </div>
      )}

      {report && (
        <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && setReport(null)}>
          <div className="modal card wide-modal">
            <div className="row">
              <h3>{report.name}</h3>
              <div className="spacer" />
              <button className="btn" onClick={copy}>{copied ? "Copied ✓" : "Copy markdown"}</button>
              <button className="btn ghost" onClick={() => setReport(null)} aria-label="Close">✕</button>
            </div>
            <div className="tiles">
              <div className="tile"><b>{report.completion_pct}%</b><span>delivered</span></div>
              <div className="tile"><b>{report.completed_points}/{report.committed_points}</b><span>points</span></div>
              <div className="tile"><b>{report.tasks_done}</b><span>tasks done</span></div>
              <div className="tile"><b>{report.bugs_fixed}</b><span>bugs fixed</span></div>
            </div>
            <h4>Burndown</h4>
            <LineChart
              labels={report.burndown.points.map((p) => p.date.slice(5))}
              series={[
                { label: "Remaining", color: "var(--c1)", values: report.burndown.points.map((p) => p.remaining) },
                { label: "Ideal", color: "var(--c-muted)", values: report.burndown.points.map((p) => p.ideal) },
              ]}
              dashed={["Ideal"]}
            />
            <Legend items={[{ label: "Remaining", color: "var(--c1)" }, { label: "Ideal", color: "var(--c-muted)" }]} />
            <Markdown source={report.markdown} />
          </div>
        </div>
      )}
    </>
  );
}
