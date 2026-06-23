import { FormEvent, useState } from "react";
import { useRouter } from "next/router";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type LoginResponse = {
  access_token: string;
  token_type: "bearer";
};

function formatLoginError(status: number, body: unknown): string {
  if (status === 401) {
    return "Invalid username or password.";
  }

  if (status === 422) {
    return "Please enter a valid username and password.";
  }

  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;

    if (typeof detail === "string") {
      return detail;
    }

    return JSON.stringify(detail);
  }

  return `Login failed with status ${status}.`;
}

export default function LoginPage() {
  const router = useRouter();

  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("admin");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    setLoading(true);
    setError("");

    try {
      const response = await fetch(`${API_URL}/auth/login`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          username,
          password,
        }),
      });

      const body = await response.json().catch(() => null);

      if (!response.ok) {
        setError(formatLoginError(response.status, body));
        return;
      }

      const data = body as LoginResponse;

      if (!data.access_token) {
        setError("Login response did not include an access token.");
        return;
      }

      // localStorage exists only in the browser, so keep it inside submit.
      localStorage.setItem("access_token", data.access_token);

      await router.push("/extract");
    } catch {
      setError("Could not reach the backend. Make sure the API is running.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main>
      <h1>Login</h1>

      <p>
        Sign in to get a JWT access token. The token will be used by the
        frontend when calling the protected API endpoints.
      </p>

      <form onSubmit={handleSubmit}>
        <label htmlFor="username">Username</label>
        <input
          id="username"
          name="username"
          value={username}
          onChange={(event) => setUsername(event.target.value)}
          autoComplete="username"
        />

        <label htmlFor="password">Password</label>
        <input
          id="password"
          name="password"
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          autoComplete="current-password"
        />

        <button
          type="submit"
          disabled={!username.trim() || !password.trim() || loading}
        >
          {loading ? "Logging in..." : "Log in"}
        </button>
      </form>

      {error && <pre role="alert">{error}</pre>}

      <section>
        <h2>Dev credentials</h2>
        <p>
          Username: <code>admin</code>
          <br />
          Password: <code>admin</code>
        </p>
      </section>
    </main>
  );
}
