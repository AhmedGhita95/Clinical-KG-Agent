"""Structured data exchanged between extraction and semantic processing."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

ID_PATTERN = r"^[A-Za-z][A-Za-z0-9_-]*$"


class SceneInstance(BaseModel):
    """One observed scene element typed with a HORUS class."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: str = Field(pattern=ID_PATTERN)
    type: str = Field(min_length=1)
    label: str = Field(min_length=1)
    evidence_text: str = Field(min_length=1)


class SceneRelation(BaseModel):
    """One relation between two scene instances."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    subject: str = Field(pattern=ID_PATTERN)
    predicate: str = Field(min_length=1)
    object: str = Field(pattern=ID_PATTERN)
    evidence_text: str = Field(min_length=1)


class HorusScene(BaseModel):
    """Complete structured extraction for a single source description."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    source_id: str = Field(pattern=ID_PATTERN)
    source_text: str = Field(min_length=1)
    instances: list[SceneInstance]
    relations: list[SceneRelation]

    @model_validator(mode="after")
    def instance_ids_are_unique(self) -> HorusScene:
        ids = [instance.id for instance in self.instances]
        duplicates = sorted({item for item in ids if ids.count(item) > 1})
        if duplicates:
            joined = ", ".join(duplicates)
            raise ValueError(f"duplicate instance ids: {joined}")
        return self
