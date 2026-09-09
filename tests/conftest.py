from __future__ import annotations

from pathlib import Path

import pytest

from clinical_kg_agent.config import FIXTURE_DIR, ONTOLOGY_PATH
from clinical_kg_agent.models import HorusScene
from clinical_kg_agent.ontology import OntologyVocabulary, load_ontology
from clinical_kg_agent.semantic import load_scene_fixture


@pytest.fixture(scope="session")
def vocabulary() -> OntologyVocabulary:
    return load_ontology(ONTOLOGY_PATH)


@pytest.fixture()
def patient_transfer_scene() -> HorusScene:
    return load_scene_fixture(FIXTURE_DIR / "patient_transfer.json")


@pytest.fixture(scope="session")
def project_root() -> Path:
    return ONTOLOGY_PATH.parents[1]
