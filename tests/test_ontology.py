from __future__ import annotations

from clinical_kg_agent.models import HorusScene, SceneInstance, SceneRelation
from clinical_kg_agent.ontology import OntologyVocabulary, validate_scene

EXPECTED_CLASSES = {
    "Action",
    "Agent",
    "Assertion",
    "Entity",
    "Object",
    "Occurrent",
    "Place",
    "Procedure",
    "State",
}
EXPECTED_PROPERTIES = {
    "about",
    "actsOn",
    "hasStep",
    "holdsFor",
    "occursIn",
    "performedBy",
}


def test_horus_metadata_and_vocabulary(vocabulary: OntologyVocabulary) -> None:
    assert vocabulary.version == "6.0.0"
    assert str(vocabulary.ontology_iri).endswith("/HORUS/v6")
    assert str(vocabulary.version_iri).endswith("/HORUS/v6/6.0.0")
    assert set(vocabulary.classes) == EXPECTED_CLASSES
    assert set(vocabulary.properties) == EXPECTED_PROPERTIES
    assert vocabulary.constraints["performedBy"].domain == "Action"
    assert vocabulary.constraints["performedBy"].ranges == {"Agent"}
    assert vocabulary.constraints["about"].ranges == {"Entity", "Occurrent", "State"}


def test_subclass_lookup_is_transitive(vocabulary: OntologyVocabulary) -> None:
    assert vocabulary.is_class_or_subclass("Agent", "Entity")
    assert vocabulary.is_class_or_subclass("Action", "Occurrent")
    assert not vocabulary.is_class_or_subclass("Object", "Agent")


def test_valid_scene_has_no_issues(
    patient_transfer_scene: HorusScene,
    vocabulary: OntologyVocabulary,
) -> None:
    assert validate_scene(patient_transfer_scene, vocabulary) == []


def test_unknown_class_is_rejected(vocabulary: OntologyVocabulary) -> None:
    scene = HorusScene(
        source_id="unknown_class",
        source_text="A nurse is present.",
        instances=[
            SceneInstance(
                id="nurse_1",
                type="Nurse",
                label="nurse",
                evidence_text="a nurse",
            )
        ],
        relations=[],
    )
    assert {issue.code for issue in validate_scene(scene, vocabulary)} == {"unknown_class"}


def test_unknown_property_is_rejected(vocabulary: OntologyVocabulary) -> None:
    scene = HorusScene(
        source_id="unknown_property",
        source_text="A nurse sees a patient.",
        instances=[
            SceneInstance(id="nurse_1", type="Agent", label="nurse", evidence_text="nurse"),
            SceneInstance(
                id="patient_1",
                type="Agent",
                label="patient",
                evidence_text="patient",
            ),
        ],
        relations=[
            SceneRelation(
                subject="nurse_1",
                predicate="sees",
                object="patient_1",
                evidence_text="nurse sees a patient",
            )
        ],
    )
    assert {issue.code for issue in validate_scene(scene, vocabulary)} == {"unknown_property"}


def test_missing_endpoint_is_rejected(vocabulary: OntologyVocabulary) -> None:
    scene = HorusScene(
        source_id="missing_endpoint",
        source_text="A nurse performs an action.",
        instances=[
            SceneInstance(
                id="action_1",
                type="Action",
                label="action",
                evidence_text="an action",
            )
        ],
        relations=[
            SceneRelation(
                subject="action_1",
                predicate="performedBy",
                object="nurse_1",
                evidence_text="a nurse performs",
            )
        ],
    )
    assert {issue.code for issue in validate_scene(scene, vocabulary)} == {"missing_object"}


def test_domain_and_range_mismatches_are_rejected(vocabulary: OntologyVocabulary) -> None:
    scene = HorusScene(
        source_id="bad_signature",
        source_text="Invalid relation fixture.",
        instances=[
            SceneInstance(id="room_1", type="Place", label="room", evidence_text="room"),
            SceneInstance(id="bed_1", type="Object", label="bed", evidence_text="bed"),
        ],
        relations=[
            SceneRelation(
                subject="room_1",
                predicate="performedBy",
                object="bed_1",
                evidence_text="invalid relation",
            )
        ],
    )
    assert {issue.code for issue in validate_scene(scene, vocabulary)} == {
        "domain_mismatch",
        "range_mismatch",
    }
