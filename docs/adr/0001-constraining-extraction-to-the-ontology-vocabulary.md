# ADR 0001: Constraining extraction to the ontology vocabulary

## Status

Accepted. Grammar-based decoding is deferred, see Alternatives.

## Context

Extraction asks a local Qwen2.5-VL model to map a scene description onto HORUS
instances and relations, returning one JSON object. The prompt is built from the
loaded OWL file: it lists the class names, the relation signatures as
`property: domain -> ranges`, and the JSON schema produced by
`HorusScene.model_json_schema()`.

On the first real video run the model returned this:

```
relations[0].predicate: 'pushes' is not a HORUS object property
relations[1].predicate: 'in' is not a HORUS object property
relations[2].predicate: 'down' is not a HORUS object property
```

Deterministic validation rejected the scene, which is the designed behaviour. The
question is why the model produced surface verbs at all when the prompt listed the
six permitted properties directly above.

The cause is a contradiction inside the prompt. `SceneRelation.predicate` is
declared as `predicate: str = Field(min_length=1)`, so the generated schema says:

```json
"predicate": { "type": "string", "minLength": 1 }
```

The prose says "use only the supplied HORUS property names". The schema says any
non-empty string is acceptable. A 3B model resolves that conflict in favour of the
machine-readable half, and copies words out of the description.

`SceneInstance.type` has the same defect and would fail the same way with invented
class names. The predicate error simply fired first.

## Decision

Inject the ontology's own terms into the schema before it is serialised into the
prompt. `type` is constrained to the loaded class names and `predicate` to the
loaded object property names, both as JSON Schema `enum` values.

The lists are read from `OntologyVocabulary`, not hardcoded. Vendoring a new HORUS
release changes the enums automatically, preserving the property that the prompt is
generated from the ontology rather than maintained alongside it.

The Pydantic models keep plain `str` fields. Constraining them at the model level
would move ontology knowledge into the data contract, which should stay a
structural description of the JSON. Enforcement of ontology membership belongs in
`validate_scene`, where it already is.

## Consequences

This removes a self-inflicted contradiction. It does not make extraction reliable.

- The constraint is a prompt, not a guarantee. A model can still emit a term
  outside the enum. `validate_scene` remains the thing that actually enforces
  ontology membership, and a rejected scene remains a rejected scene.
- It constrains vocabulary, not judgement. The model can still select a
  permitted property that is semantically wrong, for example `actsOn` where
  `occursIn` was meant. Domain and range checks catch a subset of these. Nothing
  catches the rest.
- It does not scale to large ontologies. Nine classes and six properties fit in a
  prompt comfortably, and a few hundred terms would still fit. An enterprise
  vocabulary of thousands of terms cannot be inlined at all, and would need
  candidate retrieval followed by constrained selection from a shortlist.

## Alternatives

### Grammar-based constrained decoding

Libraries such as `outlines` and `xgrammar` constrain generation at the sampling
step by masking tokens that cannot extend a valid parse of the target grammar or
JSON schema. Invalid output becomes impossible to sample rather than merely
unlikely, so the enum would be enforced by construction.

Deferred rather than rejected. It is the correct end state for making extraction
dependable, and the reasons to wait are:

1. It adds a decoding dependency and couples the project to a specific inference
   path, where today extraction is a plain `transformers` call.
2. The prompt contradiction should be removed first. Measuring the benefit of
   constrained decoding on top of a prompt that contradicts itself would produce a
   misleading result.
3. Validation already prevents a malformed scene from reaching RDF, so the current
   failure mode is a rejected scene rather than a corrupted graph.

Revisit once the enum fix has been observed on real videos. If vocabulary errors
persist at a meaningful rate, grammar-based decoding is the next step. If they
disappear and the remaining errors are semantic, the problem has moved and
constrained decoding will not help with it.

### A larger model

Qwen2.5-VL-7B follows instructions considerably better and fits in 24GB. It would
likely mask the problem without fixing it, at the cost of a larger download and
slower inference. Worth testing as a comparison, not as the fix.

### A repair or retry loop

Explicitly out of scope. Failures surface as failures, and no repair agent
rewrites model output.
