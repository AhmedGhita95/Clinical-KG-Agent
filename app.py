"""Video-first Gradio demo for local HORUS scene graphs."""

from __future__ import annotations

import asyncio
import html
import json
from functools import lru_cache
from typing import Any

import gradio as gr

from clinical_kg_agent.config import (
    CLIPS_DIR,
    FIXTURE_DIR,
    GRADIO_SERVER_NAME,
    GRADIO_SERVER_PORT,
    ONTOLOGY_PATH,
    QUERY_DIR,
    SHAPES_PATH,
)
from clinical_kg_agent.extraction import extract_scene
from clinical_kg_agent.models import HorusScene
from clinical_kg_agent.ontology import OntologyVocabulary, load_ontology
from clinical_kg_agent.perception import describe_video
from clinical_kg_agent.rag import SceneRAG
from clinical_kg_agent.semantic import (
    build_scene_graph,
    build_visualization_html,
    execute_select,
    load_queries,
    load_scene_fixture,
    scene_facts,
    validate_graph,
)

FACT_HEADERS = ["kind", "subject", "predicate", "object", "evidence"]
EVIDENCE_HEADERS = ["kind", "fact", "evidence"]
DEMO_VIDEO_PATH = CLIPS_DIR / "demo" / "animated_patient_transfer.mp4"


@lru_cache(maxsize=1)
def vocabulary() -> OntologyVocabulary:
    """Load the bundled HORUS release once."""

    return load_ontology(ONTOLOGY_PATH)


@lru_cache(maxsize=1)
def competency_queries() -> dict[str, str]:
    """Load the five bundled HORUS competency queries once."""

    return load_queries(QUERY_DIR)


@lru_cache(maxsize=1)
def competency_questions() -> dict[str, str]:
    path = QUERY_DIR / "questions.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _query_choices() -> list[tuple[str, str]]:
    return [
        (f"{query_id}: {question}", query_id)
        for query_id, question in competency_questions().items()
    ]


def _fact_values(scene: HorusScene) -> list[list[str]]:
    return [[row[column] for column in FACT_HEADERS] for row in scene_facts(scene)]


def _evidence_values(rows: tuple[dict[str, str], ...]) -> list[list[str]]:
    return [[row[column] for column in EVIDENCE_HEADERS] for row in rows]


def _graph_frame(document: str) -> str:
    source = html.escape(document, quote=True)
    return (
        '<iframe title="HORUS scene graph" sandbox="allow-scripts" '
        'style="width:100%;height:540px;border:1px solid #d8dee9;border-radius:8px" '
        f'srcdoc="{source}"></iframe>'
    )


def _sparql_markdown(scene: HorusScene, query_id: str) -> str:
    query_text = competency_queries().get(query_id)
    if query_text is None:
        return "Select a bundled competency query."

    result = execute_select(build_scene_graph(scene, vocabulary()), query_text)
    if not result.rows:
        return "_No matching rows._"

    header = "| " + " | ".join(result.columns) + " |"
    separator = "| " + " | ".join("---" for _ in result.columns) + " |"
    rows = [
        "| " + " | ".join(value.replace("|", "\\|") for value in row) + " |" for row in result.rows
    ]
    return "\n".join([header, separator, *rows])


def _present_scene(scene: HorusScene) -> tuple[Any, ...]:
    graph = build_scene_graph(scene, vocabulary())
    shacl = validate_graph(graph, vocabulary(), SHAPES_PATH)
    validation = (
        "✅ **HORUS JSON validation and SHACL validation passed.**"
        if shacl.conforms
        else f"❌ **SHACL validation failed.**\n\n```text\n{shacl.report_text}\n```"
    )
    first_query = next(iter(competency_queries()))
    return (
        scene.model_dump(mode="json"),
        scene.source_text,
        _fact_values(scene),
        validation,
        _graph_frame(build_visualization_html(scene, graph, vocabulary())),
        graph.serialize(format="turtle"),
        gr.Dropdown(value=first_query, choices=_query_choices()),
        _sparql_markdown(scene, first_query),
        "Scene ready. Ask a question below to run local LightRAG.",
        "",
        [],
    )


def load_bundled_demo() -> tuple[Any, ...]:
    """Show the reviewed fixture without loading either local AI model."""

    try:
        scene = load_scene_fixture(FIXTURE_DIR / "patient_transfer.json")
        return _present_scene(scene)
    except Exception as error:
        raise gr.Error(f"Could not load the bundled demo: {error}") from error


async def analyze_video(video_path: str | None) -> tuple[Any, ...]:
    """Run Qwen perception and extraction before deterministic semantic checks."""

    if not video_path:
        raise gr.Error("Choose a video first.")
    try:
        description = await asyncio.to_thread(describe_video, video_path)
        scene = await asyncio.to_thread(
            extract_scene,
            description,
            "uploaded_video",
            vocabulary(),
        )
        return _present_scene(scene)
    except Exception as error:
        raise gr.Error(str(error)) from error


def run_competency_query(scene_data: dict[str, Any] | None, query_id: str) -> str:
    if not scene_data:
        return "Load or analyze a scene first."
    try:
        return _sparql_markdown(HorusScene.model_validate(scene_data), query_id)
    except Exception as error:
        raise gr.Error(f"SPARQL query failed: {error}") from error


async def answer_question(
    scene_data: dict[str, Any] | None,
    question: str,
) -> tuple[str, list[list[str]], str]:
    """Build one small local index and return an answer with retrieved evidence."""

    if not scene_data:
        raise gr.Error("Load or analyze a scene first.")
    if not question.strip():
        raise gr.Error("Enter a question about the scene.")

    rag: SceneRAG | None = None
    try:
        scene = HorusScene.model_validate(scene_data)
        rag = await SceneRAG.create(scene, vocabulary())
        result = await rag.answer(question)
        return (
            result.answer,
            _evidence_values(result.evidence),
            "Answer grounded by local LightRAG.",
        )
    except Exception as error:
        raise gr.Error(str(error)) from error
    finally:
        if rag is not None:
            await rag.close()


def build_app() -> gr.Blocks:
    """Build the interface without loading models or launching a server."""

    with gr.Blocks(title="Clinical KG Agent") as demo:
        scene_state = gr.State(value=None)

        gr.Markdown("# Clinical KG Agent")

        with gr.Row():
            video = gr.Video(
                value=str(DEMO_VIDEO_PATH),
                label="Clinical scene video",
            )
            with gr.Column():
                analyze = gr.Button("Analyze video", variant="primary")
                bundled_demo = gr.Button("Load bundled demo (no GPU)")
                status = gr.Markdown(
                    "Analyze the animated video or load its reviewed no-GPU fixture."
                )

        description = gr.Textbox(label="Scene description", lines=5, interactive=False)
        validation = gr.Markdown()
        facts = gr.Dataframe(
            headers=FACT_HEADERS,
            datatype="str",
            label="Validated HORUS facts",
            interactive=False,
            wrap=True,
            row_count=1,
        )
        graph_view = gr.HTML(label="RDF graph", padding=False)

        with gr.Accordion("RDF and competency queries", open=False):
            turtle = gr.Code(label="Generated Turtle", language=None, interactive=False)
            query = gr.Dropdown(choices=_query_choices(), label="HORUS competency query")
            query_result = gr.Markdown()

        with gr.Accordion("Grounded scene questions", open=True):
            question = gr.Textbox(label="Question", placeholder="Who performs the transfer action?")
            ask = gr.Button("Ask with LightRAG")
            answer = gr.Textbox(label="Answer", lines=4, interactive=False)
            evidence = gr.Dataframe(
                headers=EVIDENCE_HEADERS,
                datatype="str",
                label="Retrieved evidence",
                interactive=False,
                wrap=True,
                row_count=1,
            )

        scene_outputs = [
            scene_state,
            description,
            facts,
            validation,
            graph_view,
            turtle,
            query,
            query_result,
            status,
            answer,
            evidence,
        ]
        analyze.click(analyze_video, inputs=video, outputs=scene_outputs)
        bundled_demo.click(load_bundled_demo, outputs=scene_outputs)
        query.change(run_competency_query, inputs=[scene_state, query], outputs=query_result)
        ask.click(
            answer_question,
            inputs=[scene_state, question],
            outputs=[answer, evidence, status],
        )

    return demo


def main() -> None:
    build_app().queue(default_concurrency_limit=1).launch(
        server_name=GRADIO_SERVER_NAME,
        server_port=GRADIO_SERVER_PORT,
        share=False,
    )


if __name__ == "__main__":
    main()
