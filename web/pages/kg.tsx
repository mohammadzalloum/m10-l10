import { useState } from "react";

import type { KGResponse } from "../lib/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function formatCell(value: unknown): string {
  if (value === null || value === undefined) {
    return "";
  }

  if (typeof value === "object") {
    return JSON.stringify(value);
  }

  return String(value);
}

function formatDetail(detail: unknown): string {
  if (typeof detail === "string") {
    return detail;
  }

  if (detail && typeof detail === "object" && "supported_patterns" in detail) {
    const typed = detail as {
      reason?: string;
      supported_patterns?: string[];
    };

    return [
      typed.reason ?? "unsupported_question",
      "",
      "Supported patterns:",
      ...(typed.supported_patterns ?? []).map((pattern) => `- ${pattern}`),
    ].join("\n");
  }

  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (typeof item === "object" && item !== null && "msg" in item) {
          return String((item as { msg: unknown }).msg);
        }

        return JSON.stringify(item);
      })
      .join("\n");
  }

  if (detail && typeof detail === "object") {
    return JSON.stringify(detail, null, 2);
  }

  return "Request failed.";
}

async function errorMessageFor(response: Response): Promise<string> {
  if (response.status === 503) {
    return "The backend is starting up — please try again in a moment.";
  }

  const body = await response.json().catch(() => null);

  if (response.status === 422) {
    return formatDetail(body?.detail ?? body);
  }

  return `Request failed with status ${response.status}.`;
}

export default function KgPage() {
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState<KGResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit() {
    setLoading(true);
    setError("");
    setResult(null);

    try {
      const response = await fetch(`${API_URL}/kg/query`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ question }),
      });

      if (!response.ok) {
        setError(await errorMessageFor(response));
        return;
      }

      const data = (await response.json()) as KGResponse;
      setResult(data);
    } catch {
      setError("Could not reach the backend.");
    } finally {
      setLoading(false);
    }
  }

  const columns =
    result && result.rows.length > 0 ? Object.keys(result.rows[0]) : [];

  return (
    <main>
      <h1>Knowledge Graph — Recipe Query</h1>

      <p>Ask one of the supported recipe knowledge-graph questions.</p>

      <input
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
        placeholder="e.g. Find Sichuan recipes"
      />

      <button onClick={submit} disabled={!question.trim() || loading}>
        {loading ? "Asking..." : "Ask"}
      </button>

      {error && <pre role="alert">{error}</pre>}

      {result && (
        <section>
          <h2>Cypher</h2>
          <pre>{result.cypher}</pre>

          <h2>Rows ({result.count})</h2>

          {result.rows.length === 0 ? (
            <p>No rows returned.</p>
          ) : (
            <table>
              <thead>
                <tr>
                  {columns.map((column) => (
                    <th key={column}>{column}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {result.rows.map((row, rowIndex) => (
                  <tr key={rowIndex} data-testid="kg-row">
                    {columns.map((column) => (
                      <td key={column}>{formatCell(row[column])}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      )}
    </main>
  );
}