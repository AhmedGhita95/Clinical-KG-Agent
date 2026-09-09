"""Small local LightRAG adapter for one validated HORUS scene."""

from __future__ import annotations

import asyncio
import json
import tempfile
import threading
from dataclasses import dataclass
from typing import Any

from clinical_kg_agent.config import EMBEDDING_MODEL_ID, QWEN_MODEL_ID
from clinical_kg_agent.models import HorusScene
from clinical_kg_agent.ontology import OntologyVocabulary, validate_scene
from clinical_kg_agent.qwen import get_qwen


class RagUnavailable(RuntimeError):
    """Raised when the optional local retrieval dependencies cannot run."""


@dataclass(frozen=True)
class GroundedAnswer:
    """Answer plus the exact LightRAG records supplied to Qwen."""

    answer: str
    evidence: tuple[dict[str, str], ...]


def scene_to_lightrag(
    scene: HorusScene,
    vocabulary: OntologyVocabulary,
) -> dict[str, list[dict[str, Any]]]:
    """Convert only a deterministically valid HORUS scene to LightRAG's KG input."""

    issues = validate_scene(scene, vocabulary)
    if issues:
        detail = "; ".join(f"{issue.path}: {issue.message}" for issue in issues)
        raise ValueError(f"LightRAG rejected an invalid HORUS scene: {detail}")

    instances = {instance.id: instance for instance in scene.instances}
    facts = [
        f"{instance.label} is a HORUS {instance.type}. Evidence: {instance.evidence_text}"
        for instance in scene.instances
    ]
    facts.extend(
        (
            f"{instances[relation.subject].label} {relation.predicate} "
            f"{instances[relation.object].label}. Evidence: {relation.evidence_text}"
        )
        for relation in scene.relations
    )

    return {
        "chunks": [
            {
                "content": f"{scene.source_text}\n\nValidated HORUS facts:\n" + "\n".join(facts),
                "source_id": scene.source_id,
                "chunk_order_index": 0,
                "file_path": scene.source_id,
            }
        ],
        "entities": [
            {
                "entity_name": instance.id,
                "entity_type": instance.type,
                "description": (
                    f"Label: {instance.label}. HORUS type: {instance.type}. "
                    f"Evidence: {instance.evidence_text}"
                ),
                "source_id": scene.source_id,
                "file_path": scene.source_id,
            }
            for instance in scene.instances
        ],
        "relationships": [
            {
                "src_id": relation.subject,
                "tgt_id": relation.object,
                "description": (
                    f"{instances[relation.subject].label} {relation.predicate} "
                    f"{instances[relation.object].label}. Evidence: {relation.evidence_text}"
                ),
                "keywords": relation.predicate,
                "weight": 1.0,
                "source_id": scene.source_id,
                "file_path": scene.source_id,
            }
            for relation in scene.relations
        ],
    }


class _MiniLMService:
    """Load one process-wide local sentence-transformer on first use."""

    def __init__(self) -> None:
        self._model: Any | None = None
        self._lock = threading.RLock()

    def _load(self) -> Any:
        with self._lock:
            if self._model is None:
                try:
                    from sentence_transformers import SentenceTransformer
                except ImportError as error:
                    raise RagUnavailable(
                        "Local embedding dependencies are missing. "
                        "Install the full project profile."
                    ) from error
                self._model = SentenceTransformer(EMBEDDING_MODEL_ID, device="cpu")
            return self._model

    @property
    def dimension(self) -> int:
        dimension = self._load().get_sentence_embedding_dimension()
        if dimension is None:
            raise RagUnavailable("The configured embedding model did not report its dimension.")
        return int(dimension)

    async def encode(self, texts: list[str]) -> Any:
        def _encode() -> Any:
            with self._lock:
                return self._load().encode(
                    texts,
                    normalize_embeddings=True,
                    convert_to_numpy=True,
                    show_progress_bar=False,
                )

        return await asyncio.to_thread(_encode)


_MINILM = _MiniLMService()


async def _embed_texts(texts: list[str]) -> Any:
    """Keep LightRAG's embedding callback deepcopy-safe."""

    return await _MINILM.encode(texts)


class _CodepointTokenizer:
    """Dependency-free, thread-safe token counting for the small scene index."""

    def encode(self, content: str) -> list[int]:
        return [ord(character) for character in content]

    def decode(self, tokens: list[int]) -> str:
        return "".join(chr(token) for token in tokens)

    def __deepcopy__(self, memo: dict[int, Any]) -> _CodepointTokenizer:
        return self


async def _qwen_complete(
    prompt: str,
    system_prompt: str | None = None,
    history_messages: list[dict[str, str]] | None = None,
    **kwargs: Any,
) -> str:
    """Adapt the shared local Qwen service to LightRAG's completion interface."""

    history = "\n".join(
        f"{message.get('role', 'user')}: {message.get('content', '')}"
        for message in (history_messages or [])
    )
    user_prompt = f"Conversation history:\n{history}\n\n{prompt}" if history else prompt
    max_tokens = min(int(kwargs.get("max_tokens", 1200)), 1600)
    return await asyncio.to_thread(
        get_qwen().generate_text,
        system_prompt
        or "Answer from the supplied HORUS scene context only. Say when evidence is insufficient.",
        user_prompt,
        max_new_tokens=max_tokens,
    )


class SceneRAG:
    """Ephemeral LightRAG index for the one scene currently shown in the app."""

    def __init__(self, rag: Any, working_directory: tempfile.TemporaryDirectory[str]) -> None:
        self._rag = rag
        self._working_directory = working_directory

    @classmethod
    async def create(
        cls,
        scene: HorusScene,
        vocabulary: OntologyVocabulary,
    ) -> SceneRAG:
        """Index a validated scene without asking LightRAG to extract a second graph."""

        payload = scene_to_lightrag(scene, vocabulary)
        try:
            from lightrag import LightRAG
            from lightrag.utils import EmbeddingFunc, Tokenizer
        except ImportError as error:
            raise RagUnavailable(
                "LightRAG is not installed. Install the full project profile."
            ) from error

        working_directory = tempfile.TemporaryDirectory(prefix="clinical-kg-agent-")
        embeddings = EmbeddingFunc(
            embedding_dim=_MINILM.dimension,
            max_token_size=256,
            model_name=EMBEDDING_MODEL_ID,
            func=_embed_texts,
        )
        rag = LightRAG(
            working_dir=working_directory.name,
            embedding_func=embeddings,
            embedding_func_max_async=1,
            llm_model_func=_qwen_complete,
            llm_model_name=QWEN_MODEL_ID,
            llm_model_max_async=1,
            tokenizer=Tokenizer("unicode-codepoint", _CodepointTokenizer()),
            enable_llm_cache=False,
            top_k=10,
            chunk_top_k=5,
        )
        try:
            await rag.initialize_storages()
            await rag.ainsert_custom_kg(payload)
        except Exception:
            await rag.finalize_storages()
            working_directory.cleanup()
            raise
        return cls(rag, working_directory)

    async def answer(self, question: str) -> GroundedAnswer:
        """Retrieve structured scene evidence, then ask the shared Qwen to answer from it."""

        question = question.strip()
        if not question:
            raise ValueError("Enter a question about the scene.")

        from lightrag import QueryParam

        result = await self._rag.aquery_data(
            question,
            QueryParam(
                mode="mix",
                top_k=10,
                chunk_top_k=5,
                enable_rerank=False,
                hl_keywords=[question],
                ll_keywords=[question],
            ),
        )
        if result.get("status") != "success" or not result.get("data"):
            raise RagUnavailable(result.get("message", "LightRAG found no scene evidence."))

        evidence = _evidence_rows(result["data"])
        context = json.dumps(result["data"], ensure_ascii=False, indent=2)
        answer = await _qwen_complete(
            f"Question: {question}\n\nRetrieved HORUS scene evidence:\n{context}",
            system_prompt=(
                "Answer the question using only the retrieved HORUS scene evidence. "
                "Be concise, distinguish observations from inference, and say when the "
                "evidence is insufficient."
            ),
        )
        return GroundedAnswer(answer=answer, evidence=evidence)

    async def close(self) -> None:
        """Close LightRAG stores and remove their temporary files."""

        await self._rag.finalize_storages()
        self._working_directory.cleanup()


def _evidence_rows(data: dict[str, Any]) -> tuple[dict[str, str], ...]:
    rows: list[dict[str, str]] = []
    rows.extend(
        {
            "kind": "entity",
            "fact": f"{item.get('entity_name', '')} ({item.get('entity_type', '')})",
            "evidence": str(item.get("description", "")),
        }
        for item in data.get("entities", [])
    )
    rows.extend(
        {
            "kind": "relation",
            "fact": (
                f"{item.get('src_id', '')} --{item.get('keywords', '')}--> {item.get('tgt_id', '')}"
            ),
            "evidence": str(item.get("description", "")),
        }
        for item in data.get("relationships", [])
    )
    rows.extend(
        {
            "kind": "source",
            "fact": str(item.get("file_path", "scene")),
            "evidence": str(item.get("content", "")),
        }
        for item in data.get("chunks", [])
    )
    return tuple(rows)
