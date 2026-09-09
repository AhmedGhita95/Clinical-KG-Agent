"""Clinical scene extraction grounded in the HORUS ontology."""

from clinical_kg_agent.models import HorusScene, SceneInstance, SceneRelation
from clinical_kg_agent.ontology import OntologyVocabulary, load_ontology

__all__ = [
    "HorusScene",
    "OntologyVocabulary",
    "SceneInstance",
    "SceneRelation",
    "load_ontology",
]
