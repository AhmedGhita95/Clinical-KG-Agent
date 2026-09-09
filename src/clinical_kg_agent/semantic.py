"""RDF construction, SHACL validation, SPARQL, and graph presentation."""

from __future__ import annotations

import html
import json
from dataclasses import dataclass
from pathlib import Path

from pyshacl import validate as validate_with_shacl
from pyvis.network import Network
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS, PROV, RDF, RDFS

from clinical_kg_agent.models import HorusScene
from clinical_kg_agent.ontology import OntologyVocabulary, ValidationIssue, validate_scene


@dataclass(frozen=True)
class ShaclResult:
    """SHACL conformance and its human-readable validation report."""

    conforms: bool
    report_graph: Graph
    report_text: str


@dataclass(frozen=True)
class SparqlResult:
    """Column names and display-ready rows returned by one SELECT query."""

    columns: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]


class SceneValidationError(ValueError):
    """Raised when a scene cannot safely become RDF."""

    def __init__(self, issues: list[ValidationIssue]) -> None:
        self.issues = issues
        detail = "; ".join(f"{issue.path}: {issue.message}" for issue in issues)
        super().__init__(detail)


CLASS_COLORS = {
    "Agent": "#2563eb",
    "Object": "#d97706",
    "Place": "#059669",
    "Action": "#dc2626",
    "Procedure": "#7c3aed",
    "State": "#0891b2",
    "Assertion": "#64748b",
    "Entity": "#475569",
    "Occurrent": "#be123c",
}
SCENE = Namespace("urn:clinical-kg-agent:scene:")


def build_scene_graph(
    scene: HorusScene,
    vocabulary: OntologyVocabulary,
) -> Graph:
    """Build RDF only after deterministic HORUS validation succeeds."""

    issues = validate_scene(scene, vocabulary)
    if issues:
        raise SceneValidationError(issues)

    graph = Graph()
    horus_ns = Namespace(f"{vocabulary.ontology_iri}#")
    scene_resource = SCENE["scene"]

    graph.bind("h", horus_ns)
    graph.bind("scene", SCENE)
    graph.bind("dcterms", DCTERMS)
    graph.bind("prov", PROV)
    graph.bind("rdfs", RDFS)

    graph.add((scene_resource, RDF.type, PROV.Entity))
    graph.add((scene_resource, DCTERMS.identifier, Literal(scene.source_id)))
    graph.add((scene_resource, DCTERMS.description, Literal(scene.source_text)))

    for instance in scene.instances:
        resource = SCENE[instance.id]
        graph.add((resource, RDF.type, vocabulary.classes[instance.type]))
        graph.add((resource, RDFS.label, Literal(instance.label)))
        graph.add((resource, PROV.wasDerivedFrom, scene_resource))

    for relation in scene.relations:
        graph.add(
            (
                SCENE[relation.subject],
                vocabulary.properties[relation.predicate],
                SCENE[relation.object],
            )
        )

    return graph


def validate_graph(
    graph: Graph,
    vocabulary: OntologyVocabulary,
    shapes_path: str | Path,
) -> ShaclResult:
    """Validate one scene graph with the released HORUS SHACL shapes."""

    shapes_graph = Graph()
    shapes_graph.parse(Path(shapes_path).resolve(), format="turtle")
    conforms, report_graph, report_text = validate_with_shacl(
        data_graph=graph,
        shacl_graph=shapes_graph,
        ont_graph=vocabulary.graph,
        # Domain/range inference can hide incorrectly typed relation endpoints.
        inference="none",
        abort_on_first=False,
        allow_infos=False,
        allow_warnings=False,
    )
    return ShaclResult(
        conforms=bool(conforms),
        report_graph=report_graph,
        report_text=str(report_text),
    )


def execute_select(graph: Graph, query_text: str) -> SparqlResult:
    """Execute a local SPARQL SELECT query and return plain strings."""

    result = graph.query(query_text)
    if result.type != "SELECT":
        raise ValueError("only SPARQL SELECT queries are supported")

    columns = tuple(str(variable) for variable in result.vars)
    rows = tuple(tuple("" if value is None else str(value) for value in row) for row in result)
    return SparqlResult(columns=columns, rows=rows)


def load_queries(query_dir: str | Path) -> dict[str, str]:
    """Load the bundled competency queries in filename order."""

    directory = Path(query_dir)
    return {path.stem: path.read_text(encoding="utf-8") for path in sorted(directory.glob("*.rq"))}


def scene_facts(scene: HorusScene) -> list[dict[str, str]]:
    """Create compact rows for the application facts table."""

    instances = {instance.id: instance for instance in scene.instances}
    rows = [
        {
            "kind": "instance",
            "subject": instance.label,
            "predicate": "rdf:type",
            "object": instance.type,
            "evidence": instance.evidence_text,
        }
        for instance in scene.instances
    ]
    rows.extend(
        {
            "kind": "relation",
            "subject": instances[relation.subject].label,
            "predicate": relation.predicate,
            "object": instances[relation.object].label,
            "evidence": relation.evidence_text,
        }
        for relation in scene.relations
    )
    return rows


def build_visualization_html(
    scene: HorusScene,
    graph: Graph,
    vocabulary: OntologyVocabulary,
) -> str:
    """Render the HORUS resources and relations found in the RDF graph."""

    network = Network(
        height="520px",
        width="100%",
        directed=True,
        bgcolor="#ffffff",
        font_color="#172033",
        cdn_resources="in_line",
    )
    network.toggle_physics(True)

    class_names = {uri: name for name, uri in vocabulary.classes.items()}
    property_names = {uri: name for name, uri in vocabulary.properties.items()}
    instance_evidence = {instance.id: instance.evidence_text for instance in scene.instances}
    relation_evidence = {
        (relation.subject, relation.predicate, relation.object): relation.evidence_text
        for relation in scene.relations
    }

    nodes: list[tuple[URIRef, URIRef]] = []
    for subject, class_uri in graph.subject_objects(RDF.type):
        if isinstance(subject, URIRef) and class_uri in class_names:
            nodes.append((subject, class_uri))

    for subject, class_uri in sorted(nodes, key=lambda item: str(item[0])):
        instance_id = str(subject).removeprefix(str(SCENE))
        label = str(graph.value(subject, RDFS.label) or instance_id)
        class_name = class_names[class_uri]
        evidence = instance_evidence.get(instance_id, "")
        title = (
            f"<b>{html.escape(label)}</b><br>"
            f"type: {html.escape(class_name)} ({html.escape(str(class_uri))})<br>"
            f"iri: {html.escape(str(subject))}<br>"
            f"evidence: {html.escape(evidence)}"
        )
        network.add_node(
            str(subject),
            label=label,
            title=title,
            color=CLASS_COLORS.get(class_name, "#475569"),
            shape="dot",
            size=22,
        )

    edges = [
        (subject, predicate, target)
        for subject, predicate, target in graph
        if predicate in property_names
        and isinstance(subject, URIRef)
        and isinstance(target, URIRef)
    ]
    for subject, predicate, target in sorted(edges, key=lambda item: tuple(map(str, item))):
        subject_id = str(subject).removeprefix(str(SCENE))
        target_id = str(target).removeprefix(str(SCENE))
        property_name = property_names[predicate]
        evidence = relation_evidence.get((subject_id, property_name, target_id), "")
        network.add_edge(
            str(subject),
            str(target),
            label=property_name,
            title=f"<b>{html.escape(property_name)}</b><br>{html.escape(evidence)}",
            arrows="to",
        )

    return network.generate_html(notebook=False)


def load_scene_fixture(path: str | Path) -> HorusScene:
    """Load a reviewed scene fixture without invoking a model."""

    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return HorusScene.model_validate(data)
