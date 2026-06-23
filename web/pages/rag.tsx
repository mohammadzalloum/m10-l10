import { useState } from "react";
import { useRouter } from "next/router";

import { API_URL, authFetch } from "../lib/api";
import type { RAGResponse } from "../lib/types";

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
  if (response.status === 401) {
    return "Please log in to continue.";
  }

  if (response.status === 403) {
    return "Insufficient scope for this action.";
  }

  if (response.status === 503) {
    return "The backend is starting up — please try again in a moment.";
  }

  const body = await response.json().catch(() => null);

  if (response.status === 422) {
    return formatDetail(body?.detail ?? body);
  }

  return `Request failed with status ${response.status}.`;
}

function renderAnswerWithCitationMarkers(answer: string) {
  return answer.split(/(\[\d+\])/g).map((part, index) => {
    if (/^\[\d+\]$/.test(part)) {
      return (
        <span key={index} data-testid="citation-marker">
          {part}
        </span>
      );
    }

    return <span key={index}>{part}</span>;
  });
}

export default function RagPage() {
  const router = useRouter();

  const [question, setQuestion] = useState("");
  const [result, setResult] = useState<RAGResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit() {
    setLoading(true);
    setError("");
    setResult(null);

    try {
      const response = await authFetch(`${API_URL}/rag/answer`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ question, k: 4 }),
      });

      if (response.status === 401) {
        await router.push("/login");
        return;
      }

      if (!response.ok) {
        setError(await errorMessageFor(response));
        return;
      }

      const data = (await response.json()) as RAGResponse;
      setResult(data);
    } catch {
      setError("Could not reach the backend.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main>
      <h1>RAG — Cited Answer</h1>

      <p>Ask a recipe question and get a grounded answer with citations.</p>

      <input
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
        placeholder="How do I prep ginger for stir-fry?"
      />

      <button onClick={submit} disabled={!question.trim() || loading}>
        {loading ? "Asking..." : "Ask"}
      </button>

      {error && <pre role="alert">{error}</pre>}

      {result && (
        <section>
          <h2>Answer</h2>
          <p>{renderAnswerWithCitationMarkers(result.answer)}</p>

          <h2>Citations</h2>

          {result.citations.length === 0 ? (
            <p>No citations returned.</p>
          ) : (
            <ul>
              {result.citations.map((citation) => (
                <li key={citation.chunk_id}>
                  chunk_id={citation.chunk_id}, score=
                  {citation.score.toFixed(3)}
                </li>
              ))}
            </ul>
          )}

          <p>
            <strong>Confidence:</strong> {result.confidence.toFixed(3)}
          </p>
        </section>
      )}
    </main>
  );
}
