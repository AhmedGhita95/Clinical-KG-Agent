from __future__ import annotations

import app
from clinical_kg_agent.qwen import get_qwen


def test_app_build_is_lazy() -> None:
    assert app.DEMO_VIDEO_PATH.is_file()
    assert [path.name for path in (app.CLIPS_DIR / "demo").glob("*.mp4")] == [
        "animated_patient_transfer.mp4"
    ]
    assert not get_qwen().is_loaded
    demo = app.build_app()
    assert demo is not None
    assert not get_qwen().is_loaded


def test_bundled_demo_needs_no_model() -> None:
    values = app.load_bundled_demo()
    scene_data, description, facts, validation = values[:4]

    assert scene_data["source_id"] == "patient_transfer_001"
    assert description
    assert facts
    assert "passed" in validation
    assert not get_qwen().is_loaded
