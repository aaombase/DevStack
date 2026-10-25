// Initials in a color derived from the username, so each person is recognisable.
export default function Avatar({ user, size = 22 }) {
  if (!user) return <span className="avatar empty" style={{ width: size, height: size }} title="Unassigned">?</span>;
  let hash = 0;
  for (const ch of user.username) hash = (hash * 31 + ch.charCodeAt(0)) % 360;
  return (
    <span
      className="avatar"
      title={user.username}
      style={{ width: size, height: size, background: `hsl(${hash} 55% 45%)`, fontSize: size * 0.45 }}
    >
      {user.username.slice(0, 2).toUpperCase()}
    </span>
  );
}
