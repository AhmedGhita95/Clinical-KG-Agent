from __future__ import annotations

import json

from rdflib import Graph

from clinical_kg_agent.config import FIXTURE_DIR, QUERY_DIR, SHAPES_PATH
from clinical_kg_agent.models import HorusScene
from clinical_kg_agent.ontology import OntologyVocabulary
from clinical_kg_agent.semantic import (
    SCENE,
    build_scene_graph,
    build_visualization_html,
    execute_select,
    load_queries,
    validate_graph,
)


def test_graph_contains_expected_fixture_triples(
    patient_transfer_scene: HorusScene,
    vocabulary: OntologyVocabulary,
) -> None:
    generated = build_scene_graph(patient_transfer_scene, vocabulary)
    expected = Graph().parse(FIXTURE_DIR / "patient_transfer.ttl", format="turtle")

    fixture_ns = "urn:horus:example:"
    translated_expected = {
        (
            SCENE[str(subject).removeprefix(fixture_ns)],
            predicate,
            SCENE[str(target).removeprefix(fixture_ns)]
            if str(target).startswith(fixture_ns)
            else target,
        )
        for subject, predicate, target in expected
    }
    assert translated_expected.issubset(set(generated))


def test_valid_graph_conforms_to_horus_shapes(
    patient_transfer_scene: HorusScene,
    vocabulary: OntologyVocabulary,
) -> None:
    graph = build_scene_graph(patient_transfer_scene, vocabulary)
    result = validate_graph(graph, vocabulary, SHAPES_PATH)
    assert result.conforms, result.report_text


def test_wrong_relation_target_fails_shacl(
    patient_transfer_scene: HorusScene,
    vocabulary: OntologyVocabulary,
) -> None:
    graph = build_scene_graph(patient_transfer_scene, vocabulary)
    graph.add(
        (
            SCENE["pushing_1"],
            vocabulary.properties["performedBy"],
            SCENE["wheelchair_1"],
        )
    )
    result = validate_graph(graph, vocabulary, SHAPES_PATH)
    assert not result.conforms
    assert "Agent" in result.report_text


def test_competency_query_results(
    patient_transfer_scene: HorusScene,
    vocabulary: OntologyVocabulary,
) -> None:
    graph = build_scene_graph(patient_transfer_scene, vocabulary)
    expected = json.loads((FIXTURE_DIR / "expected_queries.json").read_text(encoding="utf-8"))

    for query_id, query_text in load_queries(QUERY_DIR).items():
        result = execute_select(graph, query_text)
        assert list(result.columns) == expected[query_id]["columns"]
        assert [list(row) for row in result.rows] == expected[query_id]["rows"]


def test_visualization_is_generated_from_rdf(
    patient_transfer_scene: HorusScene,
    vocabulary: OntologyVocabulary,
) -> None:
    graph = build_scene_graph(patient_transfer_scene, vocabulary)
    rendered = build_visualization_html(patient_transfer_scene, graph, vocabulary)
    assert "patient transfer" in rendered
    assert "performedBy" in rendered
    assert str(vocabulary.classes["Action"]) in rendered
