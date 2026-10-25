export const STATUSES = [
  { value: "todo", label: "To Do" },
  { value: "in_progress", label: "In Progress" },
  { value: "review", label: "In Review" },
  { value: "done", label: "Done" },
];

export const TYPES = [
  { value: "task", label: "Task", icon: "✓" },
  { value: "story", label: "Story", icon: "★" },
  { value: "bug", label: "Bug", icon: "●" },
];

export const PRIORITIES = [
  { value: 1, label: "Low" },
  { value: 2, label: "Medium" },
  { value: 3, label: "High" },
  { value: 4, label: "Critical" },
];

export const typeOf = (v) => TYPES.find((t) => t.value === v) ?? TYPES[0];
export const priorityLabel = (v) => PRIORITIES.find((p) => p.value === v)?.label ?? "";
export const statusLabel = (v) => STATUSES.find((s) => s.value === v)?.label ?? v;
