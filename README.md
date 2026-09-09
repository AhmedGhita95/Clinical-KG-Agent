---
title: Clinical KG Agent
emoji: 🩺
colorFrom: blue
colorTo: green
sdk: gradio
sdk_version: 5.50.0
python_version: '3.11'
app_file: app.py
pinned: false
license: mit
short_description: Ontology-validated knowledge graphs from clinical scene video
---

# Clinical KG Agent

[![Open in Spaces](https://huggingface.co/datasets/huggingface/badges/resolve/main/open-in-hf-spaces-md.svg)](https://huggingface.co/spaces/AhmedGhita/clinical-kg-agent)

Clinical KG Agent turns a clinical-scene video into a validated, queryable
knowledge graph using Vision-Language-Models (VLMs) and the HORUS ontology.

This repository is an MVP demonstrating the integration of vision-language models with formal ontologies for structured scene understanding and knowledge representation in clinical environments.

## Pipeline

It takes a video of a clinical scene and produces a queryable knowledge graph.

1. **Perception.** A vision-language model generates a natural-language description of
   the scene: *"a nurse pushes a seated patient in a wheelchair along a corridor."*
2. **Extraction.** A second model pass maps the scene description onto typed instances and
   relations: `nurse` as an Agent, `pushing` as an Action performed by that Agent,
   `corridor` as a Place.
3. **Validation.** Each type and relation is validated against HORUS OWL ontology. Assertions outside its vocabulary are rejected.
4. **Representation.** Validated assertions are serialized as RDF, queried via SPARQL, and rendered as an interactive graph.
5. **Retrieval.** A retrieval layer resolves natural-language questions over the validated facts and returns the supporting evidence.

## Quick start (no GPU)

Runs the bundled fixture through the real validation, RDF, SHACL, SPARQL, and
visualization code. It does not process a new video or run grounded Q&A. Works on
any platform with Python 3.11 or 3.12.

```bash
# macOS / Linux
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
python app.py
```

```powershell
# Windows
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python app.py
```

Open the displayed local URL and click **Load bundled demo (no GPU)**.

## Full local setup

Required only to process a new video or run grounded Q&A.

Prerequisites:

- Python 3.11 or 3.12
- An NVIDIA CUDA GPU. Windows and Linux only; macOS has no CUDA support and can run
  the bundled demo but not video processing.
- A CUDA-enabled PyTorch build matching the machine's driver

Create an environment, install the CUDA build named by the
[official PyTorch selector](https://pytorch.org/get-started/locally/), then install
the project:

```bash
# macOS / Linux
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[full,dev]"
python -c "import torch; print(torch.cuda.is_available())"
python app.py
```

```powershell
# Windows
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[full,dev]"
python -c "import torch; print(torch.cuda.is_available())"
python app.py
```

The CUDA check must print `True` before a new video can be processed. Model weights
download on first use and are cached locally.

To override the default config, copy `.env.example` to `.env` and edit it:

```dotenv
QWEN_MODEL_ID=Qwen/Qwen2.5-VL-3B-Instruct
EMBEDDING_MODEL_ID=sentence-transformers/all-MiniLM-L6-v2
GRADIO_SERVER_NAME=127.0.0.1
GRADIO_SERVER_PORT=7860
```


## Using the app

For a new scene:

1. Use the included animated synthetic video or select another synthetic or properly
   de-identified video.
2. Click **Analyze video**.
3. Inspect the description, extracted facts, validation status, graph, and Turtle.
4. Run one of the five HORUS competency queries.
5. Ask a scene question and inspect both the answer and retrieved evidence.

## Ontology

The vendored `HORUS-6.0.0.owl` defines nine classes and six object properties, with
matching SHACL shapes and five competency queries. See [docs/HORUS.md](docs/HORUS.md)
for the vocabulary and [ontology/README.md](ontology/README.md) for release metadata
and checksum.


## Limitations

- Model output may be incomplete or wrong. Passing validation means the graph conforms
  to the HORUS schema, not that the observation is clinically correct.
- This is a demonstration, not a clinical decision support system.
- Real patient media must not be used without an approved legal basis.

## License

This repository is released under the [MIT License](LICENSE). 

The HORUS ontology is licensed separately, under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), and is used here with attribution to its author. See [ontology/README.md](ontology/README.md).
