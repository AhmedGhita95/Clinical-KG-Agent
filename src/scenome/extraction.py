"""Text-only HORUS extraction using the shared local Qwen model."""

from __future__ import annotations

import copy
import json
from collections.abc import Callable
from typing import Any

from pydantic import ValidationError

from scenome.models import HorusScene
from scenome.ontology import OntologyVocabulary, ValidationIssue, validate_scene
from scenome.qwen import get_qwen

TextGenerator = Callable[[str, str], str]


class ExtractionError(ValueError):
    """Raised when local model output is not a valid HORUS scene."""


def _vocabulary_schema(vocabulary: OntologyVocabulary) -> dict[str, Any]:
    """Replace the free-text type and predicate fields with the ontology's own terms.

    Pydantic describes both as plain strings, which contradicts the prompt text and
    invites the model to answer with words lifted from the description.
    """

    schema = copy.deepcopy(HorusScene.model_json_schema())
    definitions = schema.get("$defs", {})
    restrictions = (
        ("SceneInstance", "type", sorted(vocabulary.classes)),
        ("SceneRelation", "predicate", sorted(vocabulary.properties)),
    )
    for definition, field, allowed in restrictions:
        properties = definitions.get(definition, {}).get("properties", {})
        if field in properties:
            properties[field] = {"type": "string", "enum": allowed}
    return schema


def build_extraction_prompt(
    description: str,
    source_id: str,
    vocabulary: OntologyVocabulary,
) -> tuple[str, str]:
    """Build a compact prompt directly from the loaded HORUS vocabulary."""

    classes = ", ".join(sorted(vocabulary.classes))
    signatures = "\n".join(
        f"- {name}: {constraint.domain} -> {' | '.join(sorted(constraint.ranges))}"
        for name, constraint in sorted(vocabulary.constraints.items())
    )
    schema = json.dumps(_vocabulary_schema(vocabulary), ensure_ascii=False)
    system_prompt = (
        "Extract only facts stated or directly visible in a clinical scene description. "
        "Return one JSON object and no Markdown. Preserve observed words as instance labels. "
        "Use only the supplied HORUS class and property names. Evidence must be a short exact "
        "quote from the description."
    )
    user_prompt = f"""Source id: {source_id}

HORUS classes:
{classes}

HORUS relation signatures:
{signatures}

Required JSON schema:
{schema}

Scene description:
{description}
"""
    return system_prompt, user_prompt


def parse_json_object(raw_output: str) -> dict:
    """Extract the first complete JSON object from model output."""

    decoder = json.JSONDecoder()
    for index, character in enumerate(raw_output):
        if character != "{":
            continue
        try:
            value, _ = decoder.raw_decode(raw_output[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise ExtractionError("Qwen did not return a valid JSON object.")


def extract_scene(
    description: str,
    source_id: str,
    vocabulary: OntologyVocabulary,
    generator: TextGenerator | None = None,
) -> HorusScene:
    """Extract and validate one HORUS scene in a single model pass."""

    if generator is None:

        def generator(system: str, user: str) -> str:
            return get_qwen().generate_text(system, user)

    system_prompt, user_prompt = build_extraction_prompt(description, source_id, vocabulary)
    raw_output = generator(system_prompt, user_prompt)
    data = parse_json_object(raw_output)
    data["source_id"] = source_id
    data["source_text"] = description

    try:
        scene = HorusScene.model_validate(data)
    except ValidationError as error:
        raise ExtractionError(f"Qwen returned invalid scene JSON: {error}") from error

    issues = validate_scene(scene, vocabulary)
    if issues:
        raise ExtractionError(_format_issues(issues))
    return scene


def _format_issues(issues: list[ValidationIssue]) -> str:
    details = "; ".join(f"{issue.path}: {issue.message}" for issue in issues)
    return f"Qwen returned facts that do not conform to HORUS: {details}"
