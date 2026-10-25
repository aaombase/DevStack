import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "../auth";

export default function Login({ register: isRegister = false }) {
  const { user, login, register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ username: "", email: "", password: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to="/" replace />;

  const set = (field) => (e) => setForm({ ...form, [field]: e.target.value });

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      if (isRegister) await register(form);
      else await login(form.username, form.password);
      navigate("/");
    } catch (err) {
      setError(err.status === 401 ? "Wrong username or password." : err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-wrap">
      <form className="card auth" onSubmit={submit}>
        <h1>
          <span className="logo">▦</span> DevTrack
        </h1>
        <p className="muted">{isRegister ? "Create your account" : "Sign in to your workspace"}</p>
        <label>
          Username
          <input value={form.username} onChange={set("username")} autoFocus required />
        </label>
        {isRegister && (
          <label>
            Email
            <input type="email" value={form.email} onChange={set("email")} />
          </label>
        )}
        <label>
          Password
          <input type="password" value={form.password} onChange={set("password")} required />
        </label>
        {error && <div className="error">{error}</div>}
        <button className="btn primary" disabled={busy}>
          {busy ? "…" : isRegister ? "Create account" : "Sign in"}
        </button>
        <p className="muted small">
          {isRegister ? (
            <>
              Have an account? <Link to="/login">Sign in</Link>
            </>
          ) : (
            <>
              New here? <Link to="/register">Create an account</Link>
              <br />
              Demo data: <code>demo</code> / <code>devtrack-demo-1</code>
            </>
          )}
        </p>
      </form>
    </div>
  );
}
