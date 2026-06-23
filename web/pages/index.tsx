export default function HomePage() {
  return (
    <main>
      <h1>M10 Recipe Service — Demo</h1>

      <p>
        This demo uses JWT authentication. Start with Login, then try the
        protected NLP, Knowledge Graph, and RAG pages.
      </p>

      <ul>
        <li>
          <a href="/login">Login</a>
        </li>
        <li>
          <a href="/extract">Extract entities</a>
        </li>
        <li>
          <a href="/kg">Query the recipe knowledge graph</a>
        </li>
        <li>
          <a href="/rag">Ask a recipe question (RAG)</a>
        </li>
      </ul>
    </main>
  );
}
