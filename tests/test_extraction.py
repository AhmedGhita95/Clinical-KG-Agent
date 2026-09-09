from __future__ import annotations

import json

import pytest

from clinical_kg_agent.extraction import ExtractionError, build_extraction_prompt, extract_scene
from clinical_kg_agent.models import HorusScene
from clinical_kg_agent.ontology import OntologyVocabulary
from clinical_kg_agent.qwen import get_qwen


def test_prompt_is_built_from_horus(vocabulary: OntologyVocabulary) -> None:
    system, user = build_extraction_prompt("A nurse pushes a wheelchair.", "scene_1", vocabulary)
    assert "Return one JSON object" in system
    assert "Agent" in user
    assert "performedBy: Action -> Agent" in user
    assert "A nurse pushes a wheelchair." in user


def test_valid_local_output_becomes_a_horus_scene(
    patient_transfer_scene: HorusScene,
    vocabulary: OntologyVocabulary,
) -> None:
    output = patient_transfer_scene.model_dump()
    output["source_id"] = "model_supplied_id"
    output["source_text"] = "model-supplied text"

    scene = extract_scene(
        patient_transfer_scene.source_text,
        patient_transfer_scene.source_id,
        vocabulary,
        generator=lambda _system, _user: json.dumps(output),
    )
    assert scene == patient_transfer_scene


def test_invalid_json_fails_without_a_retry(vocabulary: OntologyVocabulary) -> None:
    calls = 0

    def invalid_generator(_system: str, _user: str) -> str:
        nonlocal calls
        calls += 1
        return "not json"

    with pytest.raises(ExtractionError, match="valid JSON"):
        extract_scene("A nurse is present.", "scene_1", vocabulary, invalid_generator)
    assert calls == 1


def test_unknown_model_type_fails_horus_validation(
    patient_transfer_scene: HorusScene,
    vocabulary: OntologyVocabulary,
) -> None:
    output = patient_transfer_scene.model_dump()
    output["instances"][0]["type"] = "Nurse"

    with pytest.raises(ExtractionError, match="not a HORUS class"):
        extract_scene(
            patient_transfer_scene.source_text,
            patient_transfer_scene.source_id,
            vocabulary,
            generator=lambda _system, _user: json.dumps(output),
        )


def test_shared_qwen_is_lazy() -> None:
    assert not get_qwen().is_loaded
