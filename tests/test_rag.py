from __future__ import annotations

import asyncio

import pytest

from clinical_kg_agent import rag as rag_module
from clinical_kg_agent.models import HorusScene
from clinical_kg_agent.ontology import OntologyVocabulary
from clinical_kg_agent.rag import SceneRAG, scene_to_lightrag


def test_validated_scene_becomes_custom_kg(
    patient_transfer_scene: HorusScene,
    vocabulary: OntologyVocabulary,
) -> None:
    payload = scene_to_lightrag(patient_transfer_scene, vocabulary)

    assert len(payload["chunks"]) == 1
    assert len(payload["entities"]) == len(patient_transfer_scene.instances)
    assert len(payload["relationships"]) == len(patient_transfer_scene.relations)
    assert payload["chunks"][0]["source_id"] == patient_transfer_scene.source_id
    assert all("Evidence:" in entity["description"] for entity in payload["entities"])
    assert all("Evidence:" in relation["description"] for relation in payload["relationships"])


def test_invalid_scene_never_reaches_lightrag(
    patient_transfer_scene: HorusScene,
    vocabulary: OntologyVocabulary,
) -> None:
    invalid = patient_transfer_scene.model_copy(deep=True)
    invalid.instances[0].type = "ImaginaryClass"

    with pytest.raises(ValueError, match="invalid HORUS scene"):
        scene_to_lightrag(invalid, vocabulary)


def test_installed_lightrag_accepts_the_validated_scene(
    patient_transfer_scene: HorusScene,
    vocabulary: OntologyVocabulary,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    numpy = pytest.importorskip("numpy")
    pytest.importorskip("lightrag")

    class FakeEmbeddingModel:
        def get_sentence_embedding_dimension(self) -> int:
            return 32

        def encode(self, texts: list[str], **_: object) -> object:
            vectors = numpy.zeros((len(texts), 32), dtype=numpy.float32)
            for row, value in enumerate(texts):
                vectors[row, sum(value.encode("utf-8")) % 32] = 1.0
            return vectors

    monkeypatch.setattr(rag_module._MINILM, "_model", FakeEmbeddingModel())

    async def fake_qwen(*_: object, **__: object) -> str:
        return "The nurse performs the action."

    monkeypatch.setattr(rag_module, "_qwen_complete", fake_qwen)

    async def exercise() -> None:
        rag = await SceneRAG.create(patient_transfer_scene, vocabulary)
        try:
            result = await rag.answer("Who performs the transfer action?")
            assert result.answer == "The nurse performs the action."
            assert result.evidence
            assert any("nurse" in row["evidence"].lower() for row in result.evidence)
        finally:
            await rag.close()

    asyncio.run(exercise())
