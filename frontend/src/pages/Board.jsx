import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api";
import Avatar from "../components/Avatar";
import TaskModal from "../components/TaskModal";
import { STATUSES, priorityLabel, typeOf } from "../constants";
import { useProject } from "./ProjectLayout";

export default function Board() {
  const { project, sprints, members, canEdit } = useProject();
  const activeSprint = sprints.find((s) => s.status === "active");
  const [sprint, setSprint] = useState(activeSprint ? String(activeSprint.id) : "all");
  const [assignee, setAssignee] = useState("");
  const [type, setType] = useState("");
  const [tasks, setTasks] = useState(null);
  const [error, setError] = useState("");
  const [modal, setModal] = useState(null); // {task} or {task: null}
  const [overCol, setOverCol] = useState(null);
  const dragId = useRef(null);

  const load = useCallback(async () => {
    try {
      const params = { project: project.id, assignee, type };
      if (sprint !== "all") params.sprint = sprint;
      setTasks(await api("/tasks/", { params }));
      setError("");
    } catch (err) {
      setError(err.message);
    }
  }, [project.id, sprint, assignee, type]);

  useEffect(() => {
    load();
  }, [load]);

  const columns = useMemo(
    () =>
      STATUSES.map((s) => ({
        ...s,
        tasks: (tasks ?? [])
          .filter((t) => t.status === s.value)
          .sort((a, b) => a.position - b.position || a.id - b.id),
      })),
    [tasks],
  );

  function dropIndex(colEl, y) {
    const cards = [...colEl.querySelectorAll("[data-task-id]")].filter(
      (el) => Number(el.dataset.taskId) !== dragId.current,
    );
    return cards.filter((el) => {
      const r = el.getBoundingClientRect();
      return y > r.top + r.height / 2;
    }).length;
  }

  async function onDrop(e, status) {
    e.preventDefault();
    setOverCol(null);
    const id = dragId.current;
    dragId.current = null;
    if (!id || !canEdit) return;
    const index = dropIndex(e.currentTarget, e.clientY);

    // Optimistic update so the card lands instantly; reload if the server disagrees.
    setTasks((prev) => {
      const moving = prev.find((t) => t.id === id);
      const column = prev
        .filter((t) => t.status === status && t.id !== id)
        .sort((a, b) => a.position - b.position || a.id - b.id);
      column.splice(index, 0, { ...moving, status });
      const positions = new Map(column.map((t, i) => [t.id, i]));
      return prev
        .filter((t) => t.id !== id)
        .map((t) => (positions.has(t.id) ? { ...t, position: positions.get(t.id) } : t))
        .concat({ ...moving, status, position: index });
    });
    try {
      await api(`/tasks/${id}/move/`, { method: "POST", body: { status, position: index } });
      load();
    } catch (err) {
      setError(err.message);
      load();
    }
  }

  const done = () => {
    setModal(null);
    load();
  };

  return (
    <>
      <div className="row filters">
        <select value={sprint} onChange={(e) => setSprint(e.target.value)} aria-label="Sprint">
          <option value="all">All tasks</option>
          <option value="none">Backlog only</option>
          {sprints.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
              {s.status === "active" ? " (active)" : ""}
            </option>
          ))}
        </select>
        <select value={assignee} onChange={(e) => setAssignee(e.target.value)} aria-label="Assignee">
          <option value="">Everyone</option>
          <option value="me">Assigned to me</option>
          <option value="none">Unassigned</option>
          {members.map((m) => (
            <option key={m.user.id} value={m.user.id}>{m.user.username}</option>
          ))}
        </select>
        <select value={type} onChange={(e) => setType(e.target.value)} aria-label="Type">
          <option value="">All types</option>
          <option value="task">Tasks</option>
          <option value="story">Stories</option>
          <option value="bug">Bugs</option>
        </select>
        <div className="spacer" />
        {canEdit && (
          <button className="btn primary" onClick={() => setModal({ task: null })}>+ New task</button>
        )}
      </div>
      {error && <div className="error">{error}</div>}
      {tasks === null && !error && <p className="muted">Loading…</p>}

      <div className="board">
        {columns.map((col) => (
          <section
            key={col.value}
            className={`column ${overCol === col.value ? "over" : ""}`}
            onDragOver={(e) => {
              if (!canEdit) return;
              e.preventDefault();
              setOverCol(col.value);
            }}
            onDragLeave={(e) => {
              if (!e.currentTarget.contains(e.relatedTarget)) setOverCol(null);
            }}
            onDrop={(e) => onDrop(e, col.value)}
          >
            <header>
              <span>{col.label}</span>
              <span className="count">{col.tasks.length}</span>
            </header>
            {col.tasks.map((t) => (
              <article
                key={t.id}
                data-task-id={t.id}
                className={`task priority-${t.priority}`}
                draggable={canEdit}
                onDragStart={(e) => {
                  dragId.current = t.id;
                  e.dataTransfer.effectAllowed = "move";
                }}
                onDragEnd={() => setOverCol(null)}
                onClick={() => setModal({ task: t })}
              >
                <div className="title">{t.title}</div>
                <div className="meta">
                  <span className={`type type-${t.type}`} title={typeOf(t.type).label}>{typeOf(t.type).icon}</span>
                  <span className="muted small">{t.key}</span>
                  {t.priority >= 3 && <span className={`pill p${t.priority}`}>{priorityLabel(t.priority)}</span>}
                  {t.story_points > 0 && <span className="pts">{t.story_points}</span>}
                  {t.comment_count > 0 && <span className="muted small">💬 {t.comment_count}</span>}
                  <div className="spacer" />
                  <Avatar user={t.assignee_detail} />
                </div>
                {t.due_date && t.status !== "done" && new Date(t.due_date) < new Date(new Date().toDateString()) && (
                  <div className="overdue small">Overdue · {t.due_date}</div>
                )}
              </article>
            ))}
          </section>
        ))}
      </div>

      {modal && (
        <TaskModal
          task={modal.task}
          defaults={{ sprint: sprint !== "all" && sprint !== "none" ? Number(sprint) : "" }}
          onClose={() => setModal(null)}
          onSaved={done}
        />
      )}
    </>
  );
}
