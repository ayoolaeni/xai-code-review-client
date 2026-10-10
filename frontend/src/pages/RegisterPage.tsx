import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { ErrorAlert } from "../components/Feedback";

export function passwordProblem(password: string): string | null {
  if (password.length < 8 || password.length > 128) return "Use 8 to 128 characters.";
  if (!/[A-Za-z]/.test(password) || !/\d/.test(password)) return "Include at least one letter and one digit.";
  return null;
}

export function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [storeCode, setStoreCode] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const pwProblem = password ? passwordProblem(password) : null;

  useEffect(() => {
    document.title = "Register · Explainable AI Code Review Assistant";
  }, []);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (passwordProblem(password)) return;
    setBusy(true);
    setError(null);
    try {
      await register({ full_name: name, email, password, store_code_default: storeCode });
      navigate("/", { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not create your account.");
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-md">
      <h1>Create an account</h1>
      <p className="mt-1 text-muted">An account lets you keep and reopen your past analyses.</p>
      <form className="card mt-5 space-y-4" onSubmit={submit} noValidate>
        {error && <ErrorAlert title="Registration failed" message={error} />}
        <div>
          <label htmlFor="name" className="label">
            Full name
          </label>
          <input
            id="name"
            className="input"
            autoComplete="name"
            maxLength={120}
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
          />
        </div>
        <div>
          <label htmlFor="reg-email" className="label">
            Email
          </label>
          <input
            id="reg-email"
            type="email"
            autoComplete="email"
            className="input"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </div>
        <div>
          <label htmlFor="reg-password" className="label">
            Password
          </label>
          <input
            id="reg-password"
            type="password"
            autoComplete="new-password"
            className="input"
            aria-describedby="pw-hint"
            aria-invalid={!!pwProblem}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
          <p id="pw-hint" className={`hint ${pwProblem ? "font-semibold text-red-800" : ""}`}>
            {pwProblem ?? "8 to 128 characters, with at least one letter and one digit."}
          </p>
        </div>
        <div className="flex items-start gap-2">
          <input
            id="reg-store"
            type="checkbox"
            className="mt-1 h-4 w-4"
            checked={storeCode}
            onChange={(e) => setStoreCode(e.target.checked)}
          />
          <label htmlFor="reg-store" className="text-sm">
            Keep my code in my history by default
            <span className="hint block">You can change this later and for each analysis.</span>
          </label>
        </div>
        <button
          type="submit"
          className="btn-primary w-full"
          disabled={busy || !name.trim() || !email || !!pwProblem || !password}
        >
          {busy ? "Creating account…" : "Register"}
        </button>
        <p className="text-center text-sm text-muted">
          Already registered? <Link to="/login">Log in</Link>
        </p>
      </form>
    </div>
  );
}
