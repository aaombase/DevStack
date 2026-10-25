import { useEffect, useState } from "react";
import { api } from "../api";
import { PRIORITIES, STATUSES, TYPES } from "../constants";
import { useProject } from "../pages/ProjectLayout";

// Create (task = null) or edit a task; edit mode also shows comments.
export default function TaskModal({ task, defaults = {}, onClose, onSaved }) {
  const { project, members, sprints, canEdit, canManage } = useProject();
  const editing = Boolean(task);
  const [form, setForm] = useState({
    title: task?.title ?? "",
    description: task?.description ?? "",
    type: task?.type ?? "task",
    status: task?.status ?? "todo",
    priority: task?.priority ?? 2,
    story_points: task?.story_points ?? 0,
    assignee: task?.assignee ?? "",
    sprint: task?.sprint ?? defaults.sprint ?? "",
    due_date: task?.due_date ?? "",
  });
  const [comments, setComments] = useState([]);
  const [comment, setComment] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (editing) api(`/tasks/${task.id}/comments/`).then(setComments).catch(() => {});
  }, [editing, task?.id]);

  const set = (field) => (e) => setForm({ ...form, [field]: e.target.value });

  async function save(e) {
    e.preventDefault();
    setError("");
    const body = {
      ...form,
      priority: Number(form.priority),
      story_points: Number(form.story_points) || 0,
      assignee: form.assignee ? Number(form.assignee) : null,
      sprint: form.sprint ? Number(form.sprint) : null,
      due_date: form.due_date || null,
    };
    try {
      if (editing) await api(`/tasks/${task.id}/`, { method: "PATCH", body });
      else await api("/tasks/", { method: "POST", body: { ...body, project: project.id } });
      onSaved();
    } catch (err) {
      setError(err.message);
    }
  }

  async function remove() {
    if (!window.confirm(`Delete ${task.key}? This can't be undone.`)) return;
    try {
      await api(`/tasks/${task.id}/`, { method: "DELETE" });
      onSaved();
    } catch (err) {
      setError(err.message);
    }
  }

  async function addComment(e) {
    e.preventDefault();
    if (!comment.trim()) return;
    try {
      const created = await api(`/tasks/${task.id}/comments/`, { method: "POST", body: { body: comment } });
      setComments([...comments, created]);
      setComment("");
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal card">
        <div className="row">
          <h3>{editing ? `${task.key}` : "New task"}</h3>
          {task?.github_url && (
            <a className="small" href={task.github_url} target="_blank" rel="noreferrer">
              GitHub #{task.github_issue_number} ↗
            </a>
          )}
          <div className="spacer" />
          <button className="btn ghost" onClick={onClose} aria-label="Close">✕</button>
        </div>

        <form className="form-grid" onSubmit={save}>
          <label className="wide">
            Title
            <input value={form.title} onChange={set("title")} required disabled={!canEdit} autoFocus />
          </label>
          <label className="wide">
            Description
            <textarea rows={4} value={form.description} onChange={set("description")} disabled={!canEdit} />
          </label>
          <label>
            Type
            <select value={form.type} onChange={set("type")} disabled={!canEdit}>
              {TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
            </select>
          </label>
          <label>
            Status
            <select value={form.status} onChange={set("status")} disabled={!canEdit}>
              {STATUSES.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
            </select>
          </label>
          <label>
            Priority
            <select value={form.priority} onChange={set("priority")} disabled={!canEdit}>
              {PRIORITIES.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
            </select>
          </label>
          <label>
            Story points
            <input type="number" min="0" max="100" value={form.story_points} onChange={set("story_points")} disabled={!canEdit} />
          </label>
          <label>
            Assignee
            <select value={form.assignee} onChange={set("assignee")} disabled={!canEdit}>
              <option value="">Unassigned</option>
              {members
                .filter((m) => m.role !== "viewer")
                .map((m) => <option key={m.user.id} value={m.user.id}>{m.user.username}</option>)}
            </select>
          </label>
          <label>
            Sprint
            <select value={form.sprint} onChange={set("sprint")} disabled={!canEdit}>
              <option value="">Backlog</option>
              {sprints.filter((s) => s.status !== "completed" || s.id === task?.sprint).map((s) => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </select>
          </label>
          <label>
            Due date
            <input type="date" value={form.due_date} onChange={set("due_date")} disabled={!canEdit} />
          </label>

          {error && <div className="error wide">{error}</div>}
          {canEdit && (
            <div className="row wide">
              <button className="btn primary">{editing ? "Save changes" : "Create task"}</button>
              {editing && canManage && (
                <button type="button" className="btn danger" onClick={remove}>Delete</button>
              )}
            </div>
          )}
        </form>

        {editing && (
          <section>
            <h4>Comments ({comments.length})</h4>
            {comments.map((c) => (
              <div key={c.id} className="comment">
                <strong>{c.author?.username ?? "deleted user"}</strong>{" "}
                <span className="muted small">{new Date(c.created_at).toLocaleString()}</span>
                <div>{c.body}</div>
              </div>
            ))}
            {canEdit && (
              <form className="row" onSubmit={addComment}>
                <input className="grow" placeholder="Write a comment…" value={comment} onChange={(e) => setComment(e.target.value)} />
                <button className="btn">Post</button>
              </form>
            )}
          </section>
        )}
      </div>
    </div>
  );
}
