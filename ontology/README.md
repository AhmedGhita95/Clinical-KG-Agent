# HORUS ontology

This directory contains the released HORUS ontology used by Clinical KG Agent.
The application treats this release as its semantic contract for scene types and
relations.

## Vendored release

| Field | Value |
| --- | --- |
| File | `HORUS-6.0.0.owl` |
| Version | `6.0.0` |
| Ontology IRI | `http://www.semanticweb.org/ahmedghita/ontologies/2025/HORUS/v6` |
| Version IRI | `http://www.semanticweb.org/ahmedghita/ontologies/2025/HORUS/v6/6.0.0` |
| Serialization | RDF/XML |
| SHA-256 | `69e00023d15e79794bf646c7d08663d7d5fc1db4a663d2429861bd1fe2800cc2` |

The release contains nine named classes, six object properties, and five
subclass axioms. Every named class and property has an English label and comment.

## Source of truth

HORUS is maintained in its own repository: https://github.com/AhmedGhita95/HORUS

`HORUS-6.0.0.owl` is vendored unmodified from
[`ontology/releases/6.0.0`](https://github.com/AhmedGhita95/HORUS/tree/main/ontology/releases/6.0.0)
in that repository. The copy in this directory is byte-identical to upstream at the
checksum recorded above.

Do not edit a released ontology file in this repository. Make ontology changes
upstream, publish a new version there, and then vendor the new release here.

## License

HORUS is licensed under [Creative Commons Attribution 4.0 International][cc]
(`CC-BY-4.0`), declared in the [upstream LICENSE][upstream-license]. Reuse of
`HORUS-6.0.0.owl` requires attribution to Ahmed Ghita, a link to the license, and
an indication of any changes. This repository vendors the release unmodified.

The MIT license at the repository root covers the Clinical KG Agent application
code, not the vendored ontology.

[cc]: https://creativecommons.org/licenses/by/4.0/
[upstream-license]: https://github.com/AhmedGhita95/HORUS/blob/main/LICENSE

## Updating the ontology

1. Publish and validate a release in the HORUS repository.
2. Copy the release artifact into this directory.
3. Update the filename, version metadata, and checksum in this README.
4. Vendor the release's matching SHACL shapes and competency queries.
5. Run the Clinical KG Agent test suite.

Verify the current artifact against the recorded checksum:

```powershell
Get-FileHash -Algorithm SHA256 ontology/HORUS-6.0.0.owl
```

Confirm it still matches upstream:

```powershell
curl -sL https://raw.githubusercontent.com/AhmedGhita95/HORUS/main/ontology/releases/6.0.0/HORUS-6.0.0.owl -o upstream.owl
Get-FileHash -Algorithm SHA256 upstream.owl
```
