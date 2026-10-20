import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { messageFromError } from "../api/client";
import { useAuth } from "../state/AuthContext";

export default function Login() {
  const [registerMode, setRegisterMode] = useState(false);
  const [form, setForm] = useState({ email: "", password: "", full_name: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const { signIn, register } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const submit = async (event) => {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      if (registerMode) await register(form);
      else await signIn({ email: form.email, password: form.password });
      navigate(location.state?.from?.pathname ?? "/", { replace: true });
    } catch (requestError) {
      setError(messageFromError(requestError));
    } finally {
      setBusy(false);
    }
  };
  return (
    <main className="login-page">
      <form className="card login-card" onSubmit={submit}>
        <Link className="brand brand-dark" to="/">Campus Pilot<span>YOUR CAMPUS, IN ONE PLACE</span></Link>
        <h1>{registerMode ? "Create your account" : "Welcome back"}</h1>
        <p className="muted">Sign in to access your campus services.</p>
        {registerMode && <label>Full name<input required maxLength="160" autoComplete="name"
          value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} /></label>}
        <label>College email<input type="email" required autoComplete="email"
          value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></label>
        <label>Password<input type="password" required minLength={registerMode ? 10 : 1}
          maxLength={registerMode ? 72 : undefined}
          autoComplete={registerMode ? "new-password" : "current-password"}
          value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} /></label>
        {error && <p className="error" role="alert">{error}</p>}
        <button className="button button-primary" disabled={busy}>{busy ? "Please wait…" : registerMode ? "Create account" : "Sign in"}</button>
        <button type="button" className="text-button" onClick={() => { setRegisterMode(!registerMode); setError(""); }}>
          {registerMode ? "Already registered? Sign in" : "New here? Create an account"}
        </button>
      </form>
    </main>
  );
}
