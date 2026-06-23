"""Pydantic request/response models for the recipe service.

These models are the typed API boundary for the FastAPI backend.
They must mirror the TypeScript interfaces in `web/lib/types.ts`
exactly. Field-name drift can make the frontend render empty results
without an obvious backend error.
"""
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


# --- /extract --------------------------------------------------------


class ExtractRequest(BaseModel):
    """Request body for POST /extract.

    Contract:
    - text is required.
    - text must not be empty.
    - text must be at most 5000 characters.
    """
    model_config = ConfigDict(extra="forbid")

    text: str = Field(..., min_length=1, max_length=5000)


class Entity(BaseModel):
    """One named-entity span returned by spaCy.

    start and end are character offsets, not token indexes.
    """
    model_config = ConfigDict(extra="forbid")

    text: str
    label: str
    start: int = Field(..., ge=0)
    end: int = Field(..., ge=0)


class ExtractResponse(BaseModel):
    """Response body for POST /extract.

    entities should be ordered by start offset ascending.
    """
    model_config = ConfigDict(extra="forbid")

    entities: list[Entity]


# --- /kg/query -------------------------------------------------------


class KGRequest(BaseModel):
    """Request body for POST /kg/query.

    Contract:
    - question is required.
    - question must not be empty.
    - question must be at most 500 characters.
    """
    model_config = ConfigDict(extra="forbid")

    question: str = Field(..., min_length=1, max_length=500)


class KGResponse(BaseModel):
    """Response body for POST /kg/query.

    rows must be JSON-serializable dictionaries produced from
    Neo4j records via record.data().
    """
    model_config = ConfigDict(extra="forbid")

    cypher: str
    rows: list[dict[str, Any]]
    count: int = Field(..., ge=0)


class UnsupportedQueryDetail(BaseModel):
    """Structured 422 detail body for unsupported KG questions."""
    model_config = ConfigDict(extra="forbid")

    reason: Literal["unsupported_question"]
    supported_patterns: list[str]


# --- /rag/answer -----------------------------------------------------


class RAGRequest(BaseModel):
    """Request body for POST /rag/answer.

    Contract:
    - question is required.
    - question must not be empty.
    - question must be at most 500 characters.
    - k defaults to 4 and must be between 1 and 10.
    """
    model_config = ConfigDict(extra="forbid")

    question: str = Field(..., min_length=1, max_length=500)
    k: int = Field(default=4, ge=1, le=10)


class Citation(BaseModel):
    """One citation pointing back to a retrieved Weaviate chunk."""
    model_config = ConfigDict(extra="forbid")

    chunk_id: int
    score: float = Field(..., ge=0.0, le=1.0)


class RAGResponse(BaseModel):
    """Response body for POST /rag/answer.

    If answer is not the sentinel refusal, citations should contain
    at least one valid source chunk.
    """
    model_config = ConfigDict(extra="forbid")

    answer: str
    citations: list[Citation]
    confidence: float = Field(..., ge=0.0, le=1.0)


# --- Health / readiness ---------------------------------------------


class HealthResponse(BaseModel):
    """Liveness response for GET /healthz.

    /healthz is process-level and should not depend on Neo4j or Weaviate.
    """
    model_config = ConfigDict(extra="forbid")

    status: Literal["ok"]


class ReadyDetail(BaseModel):
    """Readiness detail for GET /readyz.

    Used both for successful readiness responses and structured 503
    error details when a dependency is down.
    """
    model_config = ConfigDict(extra="forbid")

    neo4j: str
    weaviate: str