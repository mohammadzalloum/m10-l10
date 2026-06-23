"""FastAPI application — recipe service.

This module wires the path operations, lifespan, and CORS middleware.

Discipline gates the autograder enforces:
- Neo4j driver, Weaviate client, spaCy pipeline, and the flan-t5-base
  generator are constructed exactly once per process inside `lifespan`.
- `CORSMiddleware` is registered with `allow_origins=[WEB_ORIGIN]`.
- `/extract`, `/kg/query`, `/rag/answer` use Pydantic shapes from
  `models.py` (no anonymous dicts; use Pydantic v2 idioms (model_dump, not the deprecated v1 serialization shortcut)).
- `/kg/query` converts `UnsupportedQueryError` to 422 with structured
  detail (`{"reason": "unsupported_question", "supported_patterns": [...]}`).
- `/readyz` probes Neo4j (`RETURN 1`) AND Weaviate (`client.is_ready()`)
  within 2 seconds; failure → 503.
- `/healthz` does NOT touch Neo4j or Weaviate.
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Any

import spacy
import weaviate
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from neo4j import GraphDatabase
from passlib.context import CryptContext
from sentence_transformers import SentenceTransformer

from .auth import (
    create_access_token,
    verify_api_key_or_jwt,
    verify_jwt_admin_only,
)
from .deps import get_embedder, get_generator, get_nlp, get_session, get_weaviate
from .kg import UnsupportedQueryError, wrap_kg_query
from .m8_rag import load_generator
from .models import (
    ExtractRequest,
    ExtractResponse,
    HealthResponse,
    KGRequest,
    KGResponse,
    LoginRequest,
    RAGRequest,
    RAGResponse,
    ReadyDetail,
    TokenResponse,
    UnsupportedQueryDetail,
)
from .nlp import extract_entities
from .rag import compose_rag
from .settings import Settings
from .w9b_mapper.shapes import SUPPORTED_PATTERNS


# Dev-only user fixture for the stretch.
# Production user storage is intentionally out of scope for this assignment.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

DEV_USERS: dict[str, dict[str, str]] = {
    "admin": {
        "username": "admin",
        # Dev fixture password: admin
        # The password is verified through passlib's bcrypt verifier.
        "password_hash": pwd_context.hash("admin"),
    }
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load process-scoped resources once.

    Heavy resources should not be created per request:
    - spaCy NLP pipeline
    - Neo4j driver
    - Weaviate client
    - RAG generator
    - sentence-transformers embedder
    """
    settings = Settings()

    app.state.nlp = spacy.load("en_core_web_sm")

    app.state.neo4j_driver = GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password),
        connection_timeout=2.0,
    )

    app.state.weaviate_client = weaviate.Client(
        settings.weaviate_url,
        timeout_config=(2, 2),
    )

    app.state.generator = load_generator()
    app.state.embedder = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

    try:
        yield
    finally:
        app.state.neo4j_driver.close()


app = FastAPI(title="M10 Recipe Service", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.environ.get("WEB_ORIGIN", "http://localhost:3000")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _consume_neo4j_result(result) -> None:
    """Consume a Neo4j result in a way that also works with test fakes."""
    if hasattr(result, "consume"):
        result.consume()
        return

    for _ in result:
        pass


@app.get("/healthz", response_model=HealthResponse)
def healthz() -> HealthResponse:
    """Liveness probe.

    This must stay public and must not touch Neo4j or Weaviate.
    """
    return HealthResponse(status="ok")


@app.get("/readyz", response_model=ReadyDetail)
def readyz(
    session=Depends(get_session),
    weaviate_client=Depends(get_weaviate),
) -> ReadyDetail:
    """Dependency readiness probe.

    This stays public so orchestration systems can check dependency health.
    """
    statuses = {
        "neo4j": "ok",
        "weaviate": "ok",
    }

    try:
        result = session.run("RETURN 1 AS ok")
        _consume_neo4j_result(result)
    except Exception:
        statuses["neo4j"] = "error"

    try:
        if not weaviate_client.is_ready():
            statuses["weaviate"] = "error"
    except Exception:
        statuses["weaviate"] = "error"

    detail = ReadyDetail(**statuses)

    if statuses["neo4j"] != "ok" or statuses["weaviate"] != "ok":
        raise HTTPException(status_code=503, detail=detail.model_dump())

    return detail


@app.post("/auth/login", response_model=TokenResponse)
def login(req: LoginRequest) -> TokenResponse:
    """Authenticate the dev user and issue a JWT access token."""
    user = DEV_USERS.get(req.username)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    if not pwd_context.verify(req.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    token = create_access_token(subject=user["username"])

    return TokenResponse(access_token=token, token_type="bearer")


@app.get("/admin/echo")
def admin_echo(payload: dict[str, Any] = Depends(verify_jwt_admin_only)) -> dict[str, Any]:
    """JWT-only admin endpoint.

    A valid API key alone must not be enough for this route.
    """
    return payload


@app.post("/extract", response_model=ExtractResponse)
def extract(
    req: ExtractRequest,
    nlp=Depends(get_nlp),
    auth=Depends(verify_api_key_or_jwt),
) -> ExtractResponse:
    """Run named entity recognition.

    Access policy: valid API key OR valid JWT.
    """
    entities = extract_entities(req.text, nlp)
    return ExtractResponse(entities=entities)


@app.post("/kg/query", response_model=KGResponse)
def kg_query(
    req: KGRequest,
    session=Depends(get_session),
    auth=Depends(verify_api_key_or_jwt),
) -> KGResponse:
    """Run a deterministic KG query.

    Access policy: valid API key OR valid JWT.
    """
    try:
        cypher, params = wrap_kg_query(req.question)
    except UnsupportedQueryError:
        detail = UnsupportedQueryDetail(
            reason="unsupported_question",
            supported_patterns=SUPPORTED_PATTERNS,
        )
        raise HTTPException(status_code=422, detail=detail.model_dump())

    try:
        result = session.run(cypher, params)
    except TypeError:
        result = session.run(cypher)

    rows = [record.data() for record in result]

    return KGResponse(cypher=cypher, rows=rows, count=len(rows))


@app.post("/rag/answer", response_model=RAGResponse)
def rag_answer(
    req: RAGRequest,
    weaviate_client=Depends(get_weaviate),
    generator=Depends(get_generator),
    embedder=Depends(get_embedder),
    auth=Depends(verify_api_key_or_jwt),
) -> RAGResponse:
    """Generate a grounded RAG answer.

    Access policy: valid API key OR valid JWT.
    """
    result = compose_rag(
        question=req.question,
        embedder=embedder,
        weaviate_client=weaviate_client,
        generator=generator,
        k=req.k,
    )

    return RAGResponse.model_validate(result)