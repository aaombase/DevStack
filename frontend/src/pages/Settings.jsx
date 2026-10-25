import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import Avatar from "../components/Avatar";
import { useProject } from "./ProjectLayout";

export default function Settings() {
  const { project, members, reload, canManage, role } = useProject();
  const navigate = useNavigate();
  const [details, setDetails] = useState({
    name: project.name,
    description: project.description,
    github_repo: project.github_repo,
  });
  const [newMember, setNewMember] = useState({ username: "", role: "developer" });
  const [msg, setMsg] = useState({ type: "", text: "" });
  const [syncing, setSyncing] = useState(false);

  const say = (text, type = "ok") => setMsg({ type, text });

  async function attempt(fn, okText) {
    try {
      await fn();
      await reload();
      if (okText) say(okText);
    } catch (err) {
      say(err.message, "error");
    }
  }

  const saveDetails = (e) => {
    e.preventDefault();
    attempt(() => api(`/projects/${project.id}/`, { method: "PATCH", body: details }), "Saved.");
  };

  const addMember = (e) => {
    e.preventDefault();
    attempt(async () => {
      await api(`/projects/${project.id}/members/`, { method: "POST", body: newMember });
      setNewMember({ username: "", role: "developer" });
    }, "Member added.");
  };

  async function sync() {
    setSyncing(true);
    await attempt(async () => {
      const r = await api(`/integrations/projects/${project.id}/sync/`, { method: "POST" });
      say(`Synced: ${r.issues_created} new issues, ${r.issues_updated} updated, ${r.commits_added} new commits.`);
    });
    setSyncing(false);
  }

  const webhookUrl = `${window.location.origin}/api/integrations/projects/${project.id}/webhook/`;

  return (
    <div className="stack">
      {msg.text && <div className={msg.type === "error" ? "error" : "notice"}>{msg.text}</div>}

      <form className="card form-grid" onSubmit={saveDetails}>
        <h3 className="wide">Project</h3>
        <label>Name<input value={details.name} disabled={!canManage} onChange={(e) => setDetails({ ...details, name: e.target.value })} required /></label>
        <label>
          <span>GitHub repository <span className="small">(owner/name)</span></span>
          <input value={details.github_repo} disabled={!canManage} placeholder="acme/devtrack" onChange={(e) => setDetails({ ...details, github_repo: e.target.value })} />
        </label>
        <label className="wide">Description<input value={details.description} disabled={!canManage} onChange={(e) => setDetails({ ...details, description: e.target.value })} /></label>
        {canManage && <button className="btn primary">Save</button>}
      </form>

      <div className="card">
        <h3>GitHub integration</h3>
        {!project.github_repo ? (
          <p className="muted">Save a repository above to import its issues and commits.</p>
        ) : (
          <>
            <p className="muted">
              Imports issues as tasks (issues labelled <code>bug</code> become bugs) and mirrors commits.
              Commit messages mentioning <code>{project.key}-12</code> are linked to that task.
            </p>
            {canManage && (
              <button className="btn primary" disabled={syncing} onClick={sync}>
                {syncing ? "Syncing…" : `Sync ${project.github_repo}`}
              </button>
            )}
            {canManage && project.github_webhook_secret && (
              <details>
                <summary>Real-time updates with a webhook</summary>
                <p className="small muted">
                  In the repo's Settings → Webhooks: content type <code>application/json</code>, events
                  "Issues" and "Pushes".
                </p>
                <label>Payload URL<input readOnly value={webhookUrl} onFocus={(e) => e.target.select()} /></label>
                <label>Secret<input readOnly value={project.github_webhook_secret} onFocus={(e) => e.target.select()} /></label>
              </details>
            )}
          </>
        )}
      </div>

      <div className="card">
        <h3>Members</h3>
        <div className="table-wrap">
          <table>
            <tbody>
              {members.map((m) => (
                <tr key={m.id}>
                  <td><Avatar user={m.user} /> {m.user.username}</td>
                  <td>
                    {m.role === "owner" || !canManage ? (
                      <span className="chip">{m.role}</span>
                    ) : (
                      <select
                        value={m.role}
                        onChange={(e) => attempt(() => api(`/projects/${project.id}/members/${m.user.id}/`, { method: "PATCH", body: { role: e.target.value } }))}
                      >
                        <option value="maintainer">maintainer</option>
                        <option value="developer">developer</option>
                        <option value="viewer">viewer</option>
                      </select>
                    )}
                  </td>
                  <td>
                    {m.role !== "owner" && canManage && (
                      <button
                        className="btn ghost"
                        onClick={() => window.confirm(`Remove ${m.user.username}?`) && attempt(() => api(`/projects/${project.id}/members/${m.user.id}/`, { method: "DELETE" }), "Member removed.")}
                      >
                        Remove
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {canManage && (
          <form className="row" onSubmit={addMember}>
            <input className="grow" placeholder="Username to add" value={newMember.username} onChange={(e) => setNewMember({ ...newMember, username: e.target.value })} required />
            <select value={newMember.role} onChange={(e) => setNewMember({ ...newMember, role: e.target.value })}>
              <option value="maintainer">maintainer</option>
              <option value="developer">developer</option>
              <option value="viewer">viewer</option>
            </select>
            <button className="btn">Add</button>
          </form>
        )}
        <p className="small muted">
          Viewers can read everything. Developers can edit tasks. Maintainers manage sprints, members and GitHub. Only the owner can delete the project.
        </p>
      </div>

      {role === "owner" && (
        <div className="card danger-zone">
          <h3>Danger zone</h3>
          <button
            className="btn danger"
            onClick={() => {
              if (window.prompt(`Type ${project.key} to delete this project and all its tasks.`) !== project.key) return;
              api(`/projects/${project.id}/`, { method: "DELETE" })
                .then(() => navigate("/"))
                .catch((err) => say(err.message, "error"));
            }}
          >
            Delete project
          </button>
        </div>
      )}
    </div>
  );
}
