"""HORUS vocabulary loading and deterministic scene validation."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from rdflib import BNode, Graph, Literal, URIRef
from rdflib.collection import Collection
from rdflib.namespace import OWL, RDF, RDFS

from clinical_kg_agent.models import HorusScene


@dataclass(frozen=True)
class PropertyConstraint:
    """Named domain and accepted range classes for one HORUS property."""

    domain: str
    ranges: frozenset[str]


@dataclass(frozen=True)
class ValidationIssue:
    """One deterministic problem found in an extracted scene."""

    code: str
    path: str
    message: str


@dataclass
class OntologyVocabulary:
    """Runtime view of the classes and properties declared by HORUS."""

    graph: Graph
    ontology_iri: URIRef
    version_iri: URIRef
    version: str
    classes: dict[str, URIRef]
    class_labels: dict[str, str]
    properties: dict[str, URIRef]
    property_labels: dict[str, str]
    constraints: dict[str, PropertyConstraint]
    parents: dict[str, frozenset[str]]

    def is_class_or_subclass(self, child: str, parent: str) -> bool:
        """Return whether child equals or transitively specializes parent."""

        if child == parent:
            return True

        visited: set[str] = set()
        pending = list(self.parents.get(child, ()))
        while pending:
            candidate = pending.pop()
            if candidate == parent:
                return True
            if candidate in visited:
                continue
            visited.add(candidate)
            pending.extend(self.parents.get(candidate, ()))
        return False


def _local_name(value: URIRef) -> str:
    text = str(value)
    if "#" in text:
        return text.rsplit("#", 1)[1]
    return text.rstrip("/").rsplit("/", 1)[-1]


def _english_label(graph: Graph, subject: URIRef, fallback: str) -> str:
    labels = list(graph.objects(subject, RDFS.label))
    english = [label for label in labels if isinstance(label, Literal) and label.language == "en"]
    selected = english[0] if english else (labels[0] if labels else fallback)
    return str(selected)


def _named_class(value: object, classes_by_iri: dict[URIRef, str]) -> str | None:
    return classes_by_iri.get(value) if isinstance(value, URIRef) else None


def _range_names(
    graph: Graph,
    range_value: object,
    classes_by_iri: dict[URIRef, str],
) -> frozenset[str]:
    direct = _named_class(range_value, classes_by_iri)
    if direct:
        return frozenset({direct})
    if not isinstance(range_value, BNode):
        return frozenset()

    union_head = graph.value(range_value, OWL.unionOf)
    if union_head is None:
        return frozenset()

    names = {
        name
        for member in Collection(graph, union_head)
        if (name := _named_class(member, classes_by_iri)) is not None
    }
    return frozenset(names)


@lru_cache(maxsize=4)
def load_ontology(path: str | Path) -> OntologyVocabulary:
    """Parse a HORUS release and expose the vocabulary needed at runtime."""

    ontology_path = Path(path).resolve()
    if not ontology_path.is_file():
        raise FileNotFoundError(f"ontology not found: {ontology_path}")

    graph = Graph()
    graph.parse(ontology_path, format="xml")

    ontology_iris = [
        subject for subject in graph.subjects(RDF.type, OWL.Ontology) if isinstance(subject, URIRef)
    ]
    if len(ontology_iris) != 1:
        raise ValueError("HORUS must declare exactly one named ontology")

    ontology_iri = ontology_iris[0]
    version_iri_value = graph.value(ontology_iri, OWL.versionIRI)
    version_value = graph.value(ontology_iri, OWL.versionInfo)
    if not isinstance(version_iri_value, URIRef) or version_value is None:
        raise ValueError("HORUS is missing version metadata")

    class_iris = sorted(
        {subject for subject in graph.subjects(RDF.type, OWL.Class) if isinstance(subject, URIRef)},
        key=str,
    )
    property_iris = sorted(
        {
            subject
            for subject in graph.subjects(RDF.type, OWL.ObjectProperty)
            if isinstance(subject, URIRef)
        },
        key=str,
    )

    classes = {_local_name(uri): uri for uri in class_iris}
    properties = {_local_name(uri): uri for uri in property_iris}
    if len(classes) != len(class_iris) or len(properties) != len(property_iris):
        raise ValueError("HORUS contains duplicate local vocabulary names")

    classes_by_iri = {uri: name for name, uri in classes.items()}
    parents: dict[str, frozenset[str]] = {}
    for name, uri in classes.items():
        parent_names = {
            parent_name
            for parent in graph.objects(uri, RDFS.subClassOf)
            if (parent_name := _named_class(parent, classes_by_iri)) is not None
        }
        parents[name] = frozenset(parent_names)

    constraints: dict[str, PropertyConstraint] = {}
    for name, uri in properties.items():
        domain_value = graph.value(uri, RDFS.domain)
        range_value = graph.value(uri, RDFS.range)
        domain_name = _named_class(domain_value, classes_by_iri)
        range_names = _range_names(graph, range_value, classes_by_iri)
        if domain_name is None or not range_names:
            raise ValueError(f"property {name} must have a named domain and supported range")
        constraints[name] = PropertyConstraint(domain=domain_name, ranges=range_names)

    return OntologyVocabulary(
        graph=graph,
        ontology_iri=ontology_iri,
        version_iri=version_iri_value,
        version=str(version_value),
        classes=classes,
        class_labels={name: _english_label(graph, uri, name) for name, uri in classes.items()},
        properties=properties,
        property_labels={
            name: _english_label(graph, uri, name) for name, uri in properties.items()
        },
        constraints=constraints,
        parents=parents,
    )


def validate_scene(
    scene: HorusScene,
    vocabulary: OntologyVocabulary,
) -> list[ValidationIssue]:
    """Check a structured scene against the vocabulary and relation signatures."""

    issues: list[ValidationIssue] = []
    instances = {instance.id: instance for instance in scene.instances}

    for index, instance in enumerate(scene.instances):
        if instance.type not in vocabulary.classes:
            issues.append(
                ValidationIssue(
                    code="unknown_class",
                    path=f"instances[{index}].type",
                    message=f"{instance.type!r} is not a HORUS class",
                )
            )

    for index, relation in enumerate(scene.relations):
        path = f"relations[{index}]"
        constraint = vocabulary.constraints.get(relation.predicate)
        if constraint is None:
            issues.append(
                ValidationIssue(
                    code="unknown_property",
                    path=f"{path}.predicate",
                    message=f"{relation.predicate!r} is not a HORUS object property",
                )
            )

        subject = instances.get(relation.subject)
        target = instances.get(relation.object)
        if subject is None:
            issues.append(
                ValidationIssue(
                    code="missing_subject",
                    path=f"{path}.subject",
                    message=f"instance {relation.subject!r} does not exist",
                )
            )
        if target is None:
            issues.append(
                ValidationIssue(
                    code="missing_object",
                    path=f"{path}.object",
                    message=f"instance {relation.object!r} does not exist",
                )
            )
        if constraint is None or subject is None or target is None:
            continue
        if subject.type in vocabulary.classes and not vocabulary.is_class_or_subclass(
            subject.type,
            constraint.domain,
        ):
            issues.append(
                ValidationIssue(
                    code="domain_mismatch",
                    path=f"{path}.subject",
                    message=(
                        f"{relation.predicate} expects {constraint.domain}, "
                        f"but {relation.subject} is {subject.type}"
                    ),
                )
            )
        if target.type in vocabulary.classes and not any(
            vocabulary.is_class_or_subclass(target.type, accepted) for accepted in constraint.ranges
        ):
            accepted = ", ".join(sorted(constraint.ranges))
            issues.append(
                ValidationIssue(
                    code="range_mismatch",
                    path=f"{path}.object",
                    message=(
                        f"{relation.predicate} expects one of [{accepted}], "
                        f"but {relation.object} is {target.type}"
                    ),
                )
            )

    return issues
