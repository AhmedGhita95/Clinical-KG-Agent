"""Application configuration and repository paths."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")
ONTOLOGY_PATH = PROJECT_ROOT / "ontology" / "HORUS-6.0.0.owl"
SHAPES_PATH = PROJECT_ROOT / "ontology" / "HORUS-6.0.0.shacl.ttl"
QUERY_DIR = PROJECT_ROOT / "queries"
FIXTURE_DIR = PROJECT_ROOT / "fixtures"
CLIPS_DIR = PROJECT_ROOT / "clips"

QWEN_MODEL_ID = os.getenv(
    "QWEN_MODEL_ID",
    "Qwen/Qwen2.5-VL-3B-Instruct",
).strip()
EMBEDDING_MODEL_ID = os.getenv(
    "EMBEDDING_MODEL_ID",
    "sentence-transformers/all-MiniLM-L6-v2",
).strip()

# a Space is only reachable when the app binds every interface. locally, stay on loopback.
_DEFAULT_SERVER_NAME = "0.0.0.0" if os.getenv("SPACE_ID") else "127.0.0.1"
GRADIO_SERVER_NAME = os.getenv("GRADIO_SERVER_NAME", _DEFAULT_SERVER_NAME).strip()
GRADIO_SERVER_PORT = int(os.getenv("GRADIO_SERVER_PORT", "7860"))
