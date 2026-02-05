"""Query classification for hybrid ask: LLM-based routing (Phase 5C)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

# Classification prompt (keep it simple and structured)
CLASSIFY_PROMPT = '''Classify this code query into ONE category:
- USAGE: asks where/how something is used (e.g., "where is X called?", "what uses Y?")
- DEFINITION: asks what/where something is (e.g., "where is class X?", "find function Y")
- EXPLANATION: asks how/why something works (e.g., "explain X", "how does Y work?")
- GENERATION: asks to create/write code (e.g., "write a function", "generate tests")

Query: "{query}"

Category (one word):'''


class QueryType(Enum):
    """Query type for routing: graph (usage/definition), RAG (explanation), LLM (generation)."""

    USAGE = "usage"
    DEFINITION = "definition"
    EXPLANATION = "explanation"
    GENERATION = "generation"


@dataclass
class ClassifiedQuery:
    """Result of query classification."""

    query_type: QueryType
    entity_name: str | None  # Extracted entity for graph-backed queries


# Entity extraction patterns (used when LLM returns USAGE/DEFINITION/EXPLANATION)
# Order matters: first match wins. Captures identifier-like names (words, Class.method).
_ENTITY_PATTERNS = [
    r"where\s+is\s+(?P<entity>[\w.]+)\s+(?:used|called|defined)",
    r"where\s+are\s+(?P<entity>[\w.]+)\s+(?:used|called|defined)",
    r"(?:who|what)\s+calls\s+(?P<entity>[\w.]+)",
    r"find\s+(?:the\s+)?(?P<entity>[\w.]+)",
    r"find\s+(?:all\s+)?usages?\s+of\s+(?P<entity>[\w.]+)",
    r"references?\s+to\s+(?P<entity>[\w.]+)",
    r"explain\s+how\s+(?P<entity>[\w.]+)\s+[\w.]+\s+works?",
    r"explain\s+(?P<entity>[\w.]+)",
    r"how\s+does\s+(?P<entity>[\w.]+)\s+(?:work|function)",
    r"how\s+do\s+(?P<entity>[\w.]+)\s+work",
    r"what\s+does\s+(?P<entity>[\w.]+)\s+do",
    r"describe\s+(?P<entity>[\w.]+)",
    r"tell\s+me\s+about\s+(?P<entity>[\w.]+)",
    r"what\s+is\s+(?P<entity>[\w.]+)\s*\??",
    r"where\s+is\s+(?P<entity>[\w.]+)\s*\??",
    r"define\s+(?P<entity>[\w.]+)",
    r"definition\s+of\s+(?P<entity>[\w.]+)",
]


def _extract_entity(query: str) -> str | None:
    """Extract entity name from query using regex. Returns None if no match."""
    q = query.strip()
    for pat in _ENTITY_PATTERNS:
        m = re.search(pat, q, re.IGNORECASE)
        if m:
            try:
                return m.group("entity")
            except (IndexError, KeyError):
                pass
    return None


def _parse_category(raw: str) -> QueryType:
    """Parse LLM response into QueryType. Falls back to EXPLANATION if unrecognized."""
    s = (raw or "").strip().upper()
    # Take first word in case LLM added extra text
    first = s.split()[0] if s else ""
    try:
        return QueryType(first)
    except ValueError:
        # Partial matches for robustness
        if "USAGE" in s or first == "USAGE":
            return QueryType.USAGE
        if "DEFINITION" in s or first == "DEFINITION":
            return QueryType.DEFINITION
        if "GENERATION" in s or first == "GENERATION":
            return QueryType.GENERATION
        # Default: EXPLANATION (RAG path)
        return QueryType.EXPLANATION


class QueryRouter:
    """
    LLM-based query router for hybrid ask.
    Uses a small model for fast classification.
    """

    def __init__(
        self,
        classifier_model: str | None = None,
        generate_fn=None,
    ) -> None:
        self.classifier_model = classifier_model or "qwen2.5-coder-cpu:1.5b"
        self._generate = generate_fn

    def _get_generate(self):
        if self._generate is not None:
            return self._generate
        from paranoid.llm.ollama import generate_simple
        return generate_simple

    def classify(self, query: str) -> ClassifiedQuery:
        """
        Classify query using small LLM. Extracts entity via regex for graph-backed types.
        """
        q = query.strip()
        if not q:
            return ClassifiedQuery(query_type=QueryType.EXPLANATION, entity_name=None)

        generate = self._get_generate()
        prompt = CLASSIFY_PROMPT.format(query=q)
        try:
            response = generate(
                prompt,
                self.classifier_model,
                options={"temperature": 0, "num_predict": 10},
            )
        except Exception:
            # On connection error or model missing, fall back to EXPLANATION (RAG path)
            return ClassifiedQuery(query_type=QueryType.EXPLANATION, entity_name=_extract_entity(q))

        query_type = _parse_category(response)
        entity = _extract_entity(q) if query_type in (QueryType.USAGE, QueryType.DEFINITION, QueryType.EXPLANATION) else None
        return ClassifiedQuery(query_type=query_type, entity_name=entity)


# Default router instance (uses config at runtime)
_default_router: QueryRouter | None = None


def _get_router(config: dict | None = None) -> QueryRouter:
    global _default_router
    if _default_router is None:
        if config is None:
            from paranoid.config import load_config
            config = load_config(None)
        model = config.get("default_classifier_model") or "qwen2.5-coder-cpu:1.5b"
        _default_router = QueryRouter(classifier_model=model)
    return _default_router


def classify_query(
    question: str,
    config: dict | None = None,
    classifier_model: str | None = None,
) -> ClassifiedQuery:
    """
    Classify a natural language question using LLM-based routing.
    Returns ClassifiedQuery with query_type and optional entity_name.
    """
    router = _get_router(config)
    if classifier_model is not None:
        router = QueryRouter(classifier_model=classifier_model, generate_fn=router._get_generate())
    return router.classify(question)


# Test cases for classifier validation
TEST_CASES = [
    ("where is User.login called?", QueryType.USAGE),
    ("find the authenticate function", QueryType.DEFINITION),
    ("explain how JWT validation works", QueryType.EXPLANATION),
    ("write a test for login", QueryType.GENERATION),
]
