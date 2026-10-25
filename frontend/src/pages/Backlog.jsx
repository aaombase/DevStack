import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import Avatar from "../components/Avatar";
import TaskModal from "../components/TaskModal";
import { STATUSES, priorityLabel, statusLabel, typeOf } from "../constants";
import { useProject } from "./ProjectLayout";

export default function Backlog() {
  const { project, sprints, canEdit } = useProject();
  const [tasks, setTasks] = useState(null);
  const [search, setSearch] = useState("");
  const [type, setType] = useState("");
  const [status, setStatus] = useState("");
  const [ordering, setOrdering] = useState("-priority");
  const [error, setError] = useState("");
  const [modal, setModal] = useState(null);

  const load = useCallback(async () => {
    try {
      setTasks(await api("/tasks/", { params: { project: project.id, search, type, status, ordering } }));
      setError("");
    } catch (err) {
      setError(err.message);
    }
  }, [project.id, search, type, status, ordering]);

  // Debounce so typing in the search box doesn't fire a request per keystroke.
  useEffect(() => {
    const id = setTimeout(load, 200);
    return () => clearTimeout(id);
  }, [load]);

  async function setSprint(task, value) {
    try {
      await api(`/tasks/${task.id}/`, { method: "PATCH", body: { sprint: value ? Number(value) : null } });
      load();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <>
      <div className="row filters">
        <input placeholder="Search tasks…" value={search} onChange={(e) => setSearch(e.target.value)} />
        <select value={type} onChange={(e) => setType(e.target.value)}>
          <option value="">All types</option>
          <option value="task">Tasks</option>
          <option value="story">Stories</option>
          <option value="bug">Bugs</option>
        </select>
        <select value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">All statuses</option>
          {STATUSES.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
        </select>
        <select value={ordering} onChange={(e) => setOrdering(e.target.value)}>
          <option value="-priority">Highest priority</option>
          <option value="-created_at">Newest</option>
          <option value="due_date">Due soonest</option>
        </select>
        <div className="spacer" />
        {canEdit && <button className="btn primary" onClick={() => setModal({ task: null })}>+ New task</button>}
      </div>
      {error && <div className="error">{error}</div>}
      {tasks === null && !error && <p className="muted">Loading…</p>}
      {tasks?.length === 0 && <p className="muted">No tasks match.</p>}

      {tasks?.length > 0 && (
        <div className="card table-wrap">
          <table>
            <thead>
              <tr>
                <th>Key</th><th>Title</th><th>Status</th><th>Priority</th><th>Pts</th><th>Assignee</th><th>Sprint</th>
              </tr>
            </thead>
            <tbody>
              {tasks.map((t) => (
                <tr key={t.id}>
                  <td className="nowrap muted">
                    <span className={`type type-${t.type}`}>{typeOf(t.type).icon}</span> {t.key}
                  </td>
                  <td><button className="link" onClick={() => setModal({ task: t })}>{t.title}</button></td>
                  <td><span className={`status s-${t.status}`}>{statusLabel(t.status)}</span></td>
                  <td><span className={`pill p${t.priority}`}>{priorityLabel(t.priority)}</span></td>
                  <td>{t.story_points || "–"}</td>
                  <td><Avatar user={t.assignee_detail} /></td>
                  <td>
                    <select
                      value={t.sprint ?? ""}
                      disabled={!canEdit}
                      onChange={(e) => setSprint(t, e.target.value)}
                      aria-label={`Sprint for ${t.key}`}
                    >
                      <option value="">Backlog</option>
                      {sprints
                        .filter((s) => s.status !== "completed" || s.id === t.sprint)
                        .map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
                    </select>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {modal && (
        <TaskModal
          task={modal.task}
          onClose={() => setModal(null)}
          onSaved={() => {
            setModal(null);
            load();
          }}
        />
      )}
    </>
  );
}
