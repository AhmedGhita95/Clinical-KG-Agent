"""Shared lazy access to the local Qwen vision-language model."""

from __future__ import annotations

import importlib.util
import threading
from typing import Any

from scenome.config import QWEN_MODEL_ID


class LocalModelUnavailable(RuntimeError):
    """Raised when the local video model cannot run in this environment."""


class QwenService:
    """Load Qwen once and serialize all access to the shared GPU model."""

    def __init__(self, model_id: str = QWEN_MODEL_ID) -> None:
        self.model_id = model_id
        self._model: Any | None = None
        self._processor: Any | None = None
        self._lock = threading.Lock()

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    def _load(self) -> tuple[Any, Any]:
        if self._model is not None and self._processor is not None:
            return self._model, self._processor

        try:
            import torch
            from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration
        except ImportError as error:
            raise LocalModelUnavailable(
                "Full local-model dependencies are missing. Install the full project profile."
            ) from error

        if not torch.cuda.is_available():
            raise LocalModelUnavailable("A CUDA-capable GPU is required to process a new video.")

        attention = (
            "flash_attention_2" if importlib.util.find_spec("flash_attn") is not None else "sdpa"
        )
        self._model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
            self.model_id,
            torch_dtype=torch.bfloat16,
            attn_implementation=attention,
            device_map="auto",
        )
        self._processor = AutoProcessor.from_pretrained(
            self.model_id,
            min_pixels=256 * 28 * 28,
            max_pixels=360 * 28 * 28,
            use_fast=True,
        )
        return self._model, self._processor

    def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        max_new_tokens: int = 1600,
    ) -> str:
        """Run a deterministic text-only pass through the shared Qwen model."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        return self._generate(messages, max_new_tokens=max_new_tokens, has_video=False)

    def describe_video(self, video_path: str, *, max_new_tokens: int = 1200) -> str:
        """Describe one clinical video without sending it to an external service."""

        system_prompt = (
            "Describe only what is supported by the video. Cover people, objects, places, "
            "actions, procedures, and visible states. Avoid diagnoses and unsupported intent."
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "video", "video": video_path, "fps": 1.0, "max_frames": 32},
                    {"type": "text", "text": "Write a concise factual scene description."},
                ],
            },
        ]
        return self._generate(messages, max_new_tokens=max_new_tokens, has_video=True)

    def _generate(
        self,
        messages: list[dict[str, Any]],
        *,
        max_new_tokens: int,
        has_video: bool,
    ) -> str:
        with self._lock:
            model, processor = self._load()

            import torch

            prompt = processor.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
            )
            processor_args: dict[str, Any] = {"text": [prompt]}
            if has_video:
                try:
                    from qwen_vl_utils import process_vision_info
                except ImportError as error:
                    raise LocalModelUnavailable(
                        "qwen-vl-utils is required to process video input."
                    ) from error
                image_inputs, video_inputs = process_vision_info(messages)
                processor_args.update(images=image_inputs, videos=video_inputs)

            inputs = processor(
                **processor_args,
                padding=True,
                return_tensors="pt",
            ).to(model.device)
            with torch.inference_mode():
                output_ids = model.generate(
                    **inputs,
                    max_new_tokens=max_new_tokens,
                    do_sample=False,
                )

            generated = output_ids[:, inputs.input_ids.shape[1] :]
            decoded = processor.batch_decode(
                generated,
                skip_special_tokens=True,
                clean_up_tokenization_spaces=True,
            )
            return decoded[0].strip()


_SHARED_QWEN = QwenService()


def get_qwen() -> QwenService:
    """Return the process-wide local Qwen service without loading its weights."""

    return _SHARED_QWEN
