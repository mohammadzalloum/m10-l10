import { useState } from "react";

import type { ExtractResponse } from "../lib/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function formatDetail(detail: unknown): string {
  if (typeof detail === "string") {
    return detail;
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

export default function ExtractPage() {
  const [text, setText] = useState("");
  const [result, setResult] = useState<ExtractResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit() {
    setLoading(true);
    setError("");
    setResult(null);

    try {
      const response = await fetch(`${API_URL}/extract`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ text }),
      });

      if (!response.ok) {
        setError(await errorMessageFor(response));
        return;
      }

      const data = (await response.json()) as ExtractResponse;
      setResult(data);
    } catch {
      setError("Could not reach the backend.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main>
      <h1>Extract — Named Entity Recognition</h1>

      <p>
        Enter text and the backend will return named entities detected by spaCy.
      </p>

      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Akira Kurosawa directed Seven Samurai in 1954."
        rows={5}
      />

      <button onClick={submit} disabled={!text.trim() || loading}>
        {loading ? "Extracting..." : "Extract"}
      </button>

      {error && <pre role="alert">{error}</pre>}

      {result && (
        <section>
          <h2>Entities</h2>

          {result.entities.length === 0 ? (
            <p>No entities found.</p>
          ) : (
            <ul>
              {result.entities.map((entity, index) => (
                <li key={`${entity.start}-${entity.end}-${index}`}>
                  <span className="entity-span" data-testid="entity-span">
                    {entity.text}
                  </span>{" "}
                  <strong>{entity.label}</strong>{" "}
                  <small>
                    ({entity.start}–{entity.end})
                  </small>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
    </main>
  );
}