"""RAG composer — retrieve → assemble → generate → cite → grounding check.

Per the Evaluation Methodology Rule, the grounding criterion is:
`len(citations) > 0` is required when `answer` is not the empty-
retrieval sentinel. Every cited `chunk_id` must correspond to a
chunk in the top-`k` retrieved from Weaviate.

The generator call uses `do_sample=False` so retrieval and metric
reproducibility hold across runs.
"""
import re
from typing import Tuple

PROMPT_TEMPLATE = """\
You are answering a recipe question. Use ONLY the numbered sources below.
Cite each claim with the source number in square brackets, e.g. [1].
If the sources do not contain the answer, say: I cannot answer this from the available sources.

Sources:
{sources}

Question: {question}
Answer:"""

SENTINEL = "I cannot answer this from the available sources"
CITATION_PATTERN = re.compile(r"\[(\d+)\]")


def assemble_prompt(question: str, chunks: list[dict]) -> Tuple[str, dict[int, dict]]:
    """Number the retrieved chunks 1..k and substitute into the prompt template.

    Returns (prompt_str, {citation_index: chunk_dict}).
    """
    # TODO: walk the chunks list, build numbered source lines, and call
    #       PROMPT_TEMPLATE.format(...). Return the prompt string and the
    #       index→chunk mapping. Index starts at 1, not 0.
    raise NotImplementedError


def extract_citations(answer: str, numbered: dict[int, dict]) -> list[dict]:
    """Pull [N]-style markers from `answer` and resolve to retrieved chunks.

    Each return value is shaped {"chunk_id": int, "score": float}. Only
    indices that are present in `numbered` are returned; duplicates are
    de-duplicated.
    """
    # TODO: iterate CITATION_PATTERN.finditer(answer), look up each index
    #       in `numbered`, and emit one {"chunk_id", "score"} dict per
    #       unique index that maps to a real retrieved chunk.
    raise NotImplementedError


def compose_rag(question: str, embedder, weaviate_client, generator, k: int = 4) -> dict:
    """Run the four-stage RAG pipeline.

    Returns a dict {"answer": str, "citations": list[dict], "confidence": float}.

    Grounding contract:
    - If Weaviate returns zero chunks → return SENTINEL with citations=[]
      and confidence=0.0.
    - If the generator returns text with no resolvable citation
      markers → also return SENTINEL with citations=[] and
      confidence=0.0. (This is the "refuse rather than hallucinate"
      rule the autograder enforces.)
    """
import re
from typing import Tuple

PROMPT_TEMPLATE = """\
You are answering a recipe question. Use ONLY the numbered sources below.
Cite each claim with the source number in square brackets, e.g. [1].
If the sources do not contain the answer, say: I cannot answer this from the available sources.

Sources:
{sources}

Question: {question}
Answer:"""

SENTINEL = "I cannot answer this from the available sources"
CITATION_PATTERN = re.compile(r"\[(\d+)\]")


def _clip_score(value: float) -> float:
    """Keep confidence/citation scores inside [0, 1]."""
    return max(0.0, min(1.0, value))


def _sentinel_response() -> dict:
    """Return the standard grounded-refusal response."""
    return {
        "answer": SENTINEL,
        "citations": [],
        "confidence": 0.0,
    }


def _score_from_distance(distance) -> float:
    """Convert Weaviate distance to a citation score.

    The lab defines citation score as 1.0 - distance, clipped to [0, 1].
    """
    if distance is None:
        return 0.0

    return _clip_score(1.0 - float(distance))


def _extract_generated_text(generator_output) -> str:
    """Normalize HuggingFace pipeline output to a plain string.

    The real flan-t5 pipeline returns:
        [{"generated_text": "..."}]

    Some tests may use a fake generator that returns a plain string.
    This helper supports both shapes.
    """
    if isinstance(generator_output, str):
        return generator_output

    if isinstance(generator_output, list) and generator_output:
        first = generator_output[0]

        if isinstance(first, dict):
            return str(first.get("generated_text", ""))

        return str(first)

    if isinstance(generator_output, dict):
        return str(generator_output.get("generated_text", ""))

    return str(generator_output)


def _parse_weaviate_chunks(result: dict) -> list[dict]:
    """Parse Weaviate's GraphQL response into simple chunk dicts."""
    raw_chunks = (
        result
        .get("data", {})
        .get("Get", {})
        .get("Chunk", [])
    )

    chunks = []

    for raw in raw_chunks:
        additional = raw.get("_additional", {})
        distance = additional.get("distance")

        chunks.append(
            {
                "text": raw["text"],
                "chunk_id": int(raw["chunk_id"]),
                "distance": distance,
                "score": _score_from_distance(distance),
            }
        )

    return chunks


def assemble_prompt(question: str, chunks: list[dict]) -> Tuple[str, dict[int, dict]]:
    """Number the retrieved chunks 1..k and substitute into the prompt template.

    Returns:
        (prompt_str, {citation_index: chunk_dict})

    Index starts at 1 because citations in the generated answer look like [1], [2], ...
    """
    numbered: dict[int, dict] = {}
    source_lines: list[str] = []

    for index, chunk in enumerate(chunks, start=1):
        numbered[index] = chunk
        source_lines.append(f"[{index}] {chunk['text']}")

    prompt = PROMPT_TEMPLATE.format(
        sources="\n".join(source_lines),
        question=question,
    )

    return prompt, numbered


def extract_citations(answer: str, numbered: dict[int, dict]) -> list[dict]:
    """Pull [N]-style markers from `answer` and resolve to retrieved chunks.

    Each return value is shaped:
        {"chunk_id": int, "score": float}

    Only markers that point to real retrieved chunks are kept.
    Duplicate citation markers are de-duplicated.
    """
    citations: list[dict] = []
    seen_indices: set[int] = set()

    for match in CITATION_PATTERN.finditer(answer):
        citation_index = int(match.group(1))

        if citation_index in seen_indices:
            continue

        chunk = numbered.get(citation_index)
        if chunk is None:
            continue

        seen_indices.add(citation_index)

        citations.append(
            {
                "chunk_id": int(chunk["chunk_id"]),
                "score": _clip_score(float(chunk["score"])),
            }
        )

    return citations


def compose_rag(question: str, embedder, weaviate_client, generator, k: int = 4) -> dict:
    """Run the four-stage RAG pipeline.

    Returns:
        {"answer": str, "citations": list[dict], "confidence": float}

    Grounding contract:
    - If Weaviate returns zero chunks, return SENTINEL with citations=[] and confidence=0.0.
    - If the generator returns text with no valid citation markers, also return SENTINEL.
    """
    encoded = embedder.encode(question)
    vector = encoded.tolist() if hasattr(encoded, "tolist") else encoded

    result = (
        weaviate_client.query
        .get("Chunk", ["text", "chunk_id"])
        .with_near_vector({"vector": vector})
        .with_additional(["distance"])
        .with_limit(k)
        .do()
    )

    retrieved = _parse_weaviate_chunks(result)

    if not retrieved:
        return _sentinel_response()

    prompt, numbered = assemble_prompt(question, retrieved)

    generated = generator(
        prompt,
        max_new_tokens=256,
        do_sample=False,
    )

    answer = _extract_generated_text(generated).strip()
    citations = extract_citations(answer, numbered)

    if not citations:
        return _sentinel_response()

    confidence = sum(citation["score"] for citation in citations) / len(citations)

    return {
        "answer": answer,
        "citations": citations,
        "confidence": _clip_score(confidence),
    }