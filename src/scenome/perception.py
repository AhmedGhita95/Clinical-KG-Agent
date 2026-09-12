"""Local video perception for Scenome."""

from __future__ import annotations

from scenome.qwen import get_qwen


def describe_video(video_path: str) -> str:
    """Produce the factual description consumed by HORUS extraction."""

    if not video_path:
        raise ValueError("A video path is required.")
    return get_qwen().describe_video(video_path)
