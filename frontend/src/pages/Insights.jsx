import { useEffect, useState } from "react";
import { api } from "../api";
import { BarChart, Legend, LineChart } from "../components/Charts";
import Markdown from "../components/Markdown";
import { useProject } from "./ProjectLayout";

const HEALTH = { green: "On track", amber: "Needs attention", red: "At risk" };

export default function Insights() {
  const { project, sprints } = useProject();
  const [data, setData] = useState(null);
  const [summary, setSummary] = useState(null);
  const [burndown, setBurndown] = useState(null);
  const [activity, setActivity] = useState([]);
  const [commits, setCommits] = useState([]);
  const [days, setDays] = useState(7);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);
  const activeSprint = sprints.find((s) => s.status === "active");

  useEffect(() => {
    const id = project.id;
    Promise.all([
      api(`/projects/${id}/analytics/`).then(setData),
      api("/activity/", { params: { project: id } }).then(setActivity),
      api(`/integrations/projects/${id}/commits/`).then(setCommits),
      activeSprint
        ? api(`/sprints/${activeSprint.id}/report/`).then((r) => setBurndown(r.burndown))
        : setBurndown(null),
    ]).catch((e) => setError(e.message));
  }, [project.id, activeSprint?.id]);

  useEffect(() => {
    setCopied(false);
    api(`/projects/${project.id}/summary/`, { params: { days } }).then(setSummary).catch((e) => setError(e.message));
  }, [project.id, days]);

  if (error) return <div className="error">{error}</div>;
  if (!data || !summary) return <p className="muted">Loading…</p>;

  const { overview: ov, timeline, contributors, velocity } = data;
  const weekly = [];
  for (let i = 0; i < timeline.length; i += 7) {
    const chunk = timeline.slice(i, i + 7);
    weekly.push({
      label: chunk[0].date.slice(5),
      values: [
        chunk.reduce((n, d) => n + d.created, 0),
        chunk.reduce((n, d) => n + d.completed, 0),
        chunk.reduce((n, d) => n + d.commits, 0),
      ],
    });
  }

  return (
    <>
      <div className="tiles">
        <div className="tile"><b>{ov.completion_pct}%</b><span>complete</span></div>
        <div className="tile"><b>{ov.total_tasks - ov.done_tasks}</b><span>open tasks</span></div>
        <div className={`tile ${ov.open_bugs ? "warn" : ""}`}><b>{ov.open_bugs}</b><span>open bugs</span></div>
        <div className={`tile ${ov.overdue ? "bad" : ""}`}><b>{ov.overdue}</b><span>overdue</span></div>
        <div className="tile"><b>{ov.unassigned}</b><span>unassigned</span></div>
      </div>

      <div className="card">
        <div className="row">
          <h3>Project summary</h3>
          <span className={`health h-${summary.health}`}>{HEALTH[summary.health]}</span>
          <div className="spacer" />
          <select value={days} onChange={(e) => setDays(Number(e.target.value))} aria-label="Period">
            <option value={7}>Last 7 days</option>
            <option value={14}>Last 14 days</option>
            <option value={30}>Last 30 days</option>
          </select>
          <button
            className="btn"
            onClick={async () => {
              await navigator.clipboard.writeText(summary.markdown);
              setCopied(true);
            }}
          >
            {copied ? "Copied ✓" : "Copy"}
          </button>
        </div>
        <Markdown source={summary.markdown} />
      </div>

      <div className="two-col">
        <div className="card">
          <h4>Weekly activity</h4>
          <BarChart groups={weekly} colors={["var(--c2)", "var(--c1)", "var(--c3)"]} />
          <Legend items={[
            { label: "Created", color: "var(--c2)" },
            { label: "Completed", color: "var(--c1)" },
            { label: "Commits", color: "var(--c3)" },
          ]} />
        </div>
        <div className="card">
          <h4>Velocity (points per sprint)</h4>
          {velocity.length ? (
            <>
              <BarChart groups={velocity.map((v) => ({ label: v.sprint, values: [v.committed, v.completed] }))} colors={["var(--c-muted)", "var(--c1)"]} />
              <Legend items={[{ label: "Committed", color: "var(--c-muted)" }, { label: "Completed", color: "var(--c1)" }]} />
            </>
          ) : (
            <p className="muted">Complete a sprint to see velocity.</p>
          )}
        </div>
      </div>

      <div className="two-col">
        {burndown && (
          <div className="card">
            <h4>Burndown · {activeSprint.name}</h4>
            <LineChart
              labels={burndown.points.map((p) => p.date.slice(5))}
              series={[
                { label: "Remaining", color: "var(--c1)", values: burndown.points.map((p) => p.remaining) },
                { label: "Ideal", color: "var(--c-muted)", values: burndown.points.map((p) => p.ideal) },
              ]}
              dashed={["Ideal"]}
            />
            <Legend items={[{ label: "Remaining", color: "var(--c1)" }, { label: "Ideal", color: "var(--c-muted)" }]} />
          </div>
        )}
        <div className="card">
          <h4>Contributors</h4>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Who</th><th>Done</th><th>Pts</th><th>Open</th><th>Commits</th></tr></thead>
              <tbody>
                {contributors.map((c) => (
                  <tr key={c.user}>
                    <td>{c.user} <span className="muted small">{c.role}</span></td>
                    <td>{c.completed_tasks}</td><td>{c.completed_points}</td><td>{c.open_tasks}</td><td>{c.commits}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <div className="two-col">
        <div className="card">
          <h4>Recent commits</h4>
          {commits.length === 0 && <p className="muted">No commits yet. Link a GitHub repo in Settings.</p>}
          <ul className="feed">
            {commits.slice(0, 8).map((c) => (
              <li key={c.sha}>
                <a href={c.url} target="_blank" rel="noreferrer"><code>{c.sha.slice(0, 7)}</code></a> {c.message}
                <span className="muted small"> · {c.author}</span>
              </li>
            ))}
          </ul>
        </div>
        <div className="card">
          <h4>Activity</h4>
          <ul className="feed">
            {activity.map((a) => (
              <li key={a.id}>
                <strong>{a.actor?.username ?? "GitHub"}</strong> {a.verb}
                {a.task_key && <> <code>{a.task_key}</code></>}
                {a.detail && <span className="muted"> · {a.detail}</span>}
                <span className="muted small"> · {new Date(a.created_at).toLocaleString()}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </>
  );
}
