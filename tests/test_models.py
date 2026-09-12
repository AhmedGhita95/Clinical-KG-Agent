from __future__ import annotations

import pytest
from pydantic import ValidationError

from scenome.models import HorusScene, SceneInstance


def test_instance_identifier_must_be_uri_safe() -> None:
    with pytest.raises(ValidationError):
        SceneInstance(
            id="not safe",
            type="Agent",
            label="nurse",
            evidence_text="a nurse",
        )


def test_instance_identifiers_must_be_unique() -> None:
    duplicate = SceneInstance(
        id="nurse_1",
        type="Agent",
        label="nurse",
        evidence_text="a nurse",
    )
    with pytest.raises(ValidationError, match="duplicate instance ids"):
        HorusScene(
            source_id="duplicate_ids",
            source_text="Two observations were assigned one identifier.",
            instances=[duplicate, duplicate.model_copy()],
            relations=[],
        )
