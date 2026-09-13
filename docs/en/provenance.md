# Provenance and integrity

**English** | [Português (Brasil)](../proveniencia.md) · [English index](README.md)

This organization started with the handoff specified by the user and consulted
local reports, scripts, and results. It did not search for benchmarks on the
internet, read the entire previous transcript, or perform a new GPU measurement.

## Preserved sources

| Source | Treatment |
|---|---|
| [Handoff](../history/handoff-2026-09-12.md) | Copy of the file available when the archive was organized. A session summary, with claims that require checking against raw output. |
| [Previous README](../history/README-before-organization.md) | Preserved before replacing the project entry point; includes attribution of the `chat_raw.gemma4` run to the i7-14700KF CPU. |
| [Results](../../results/) | Historical reports and responses preserved, including invalidated rounds. |
| [Prompts](../../prompts/) | Canonical prompt, backup, and experimental attempts preserved. |
| [Sessions](../../SESSOES.md) | Origin references; these do not represent session files included in the repository. |
| [Manifest](../../artifacts/manifest.json) | List of evidence files, sizes, and SHA-256 hashes; type indicates the extension, not validity or hardware. |

The handoff snapshot has SHA-256
`1a76112cb51736b0d6c4683568321cd71428c26362b37569472549cb3f16beaa`.
The local source is `.herdr/handoff/llm-bench-20260912-220504-3731916.md`.
The file was updated externally between the first reading on resumption and
this copy: the final Phase 6b addendum, previously contradictory, is already
corrected in the snapshot. The PT→EN claims remain as they were in the source
and are qualified in the [dedicated finding](findings/qwen3-14b-language-template.md).

The complete previous session was identified as a JSONL with ID
`d5005acf-9e83-40c4-b68b-84d0e6feb85e`. It is not included in the publication.
The reports also cite `.herdr/review/`, temporary files, and consumer projects.
Those external references are not equivalent to complete evidence present in
this repository. The catalog identifies reproducibility gaps.

## Reading order and conflicts

Read the consolidation in [benchmarks](benchmarks.md), [findings](findings.md),
and [decisions](decisions.md) first, then the linked source. Some historical
reports preserve withdrawn recommendations and superseded numbers; their final
correction sections are an essential part of the evidence. A document named
“FINAL” or a handoff does not remove the need for this check.

When a summary and raw output disagree, the new documentation records both and
explains which conclusion the inspection supports. Raw data were not changed to
make them agree with the narrative. If the raw output does not exist, the result
is attributed to the report and the limitation is stated.

Examples:

- PT→EN: the handoff's “264 bytes” and “30/30 PT” are not reproduced by the
  inspection recorded in the [finding](findings/qwen3-14b-language-template.md).
- Phase 6b: truncation is observed, but the explanation that context is divided
  among slots was contradicted by the log, as documented in the
  [correction](../../results/RESULTADO-fase6b-numparallel-contexto-longo-2026-09-12.md).
- Judges and Phase 7: earlier versions have harness defects and must not be
  aggregated with corrected remeasurements. [Catalog](benchmarks.md).

## Publication and maintenance

The repository includes documentation, scripts, prompts, and evidence selected
by the inventory. Virtual environments, caches, local Herdr state, and
credential files stay outside Git. Historical artifact paths were retained to
preserve references and scripts' relative path resolution.

The `.gitattributes` rule preserves bytes, including on Windows checkouts.
The manifest covers evidence, not the editorial indexes in `docs/` or READMEs.
Link validation covers new documents and skips historical snapshots; it does
not check external destinations or section fragments.

The English documentation is a translated view linked to the Portuguese
originals. Original evidence remains in its original language. Future changes
to these documents must update both the Portuguese and English versions.

To add a measurement, use the [template](templates/experiment.md), record complete
data, update the appropriate catalog, and run the [offline verification](methodology.md)
commands. Correcting documentation is not correcting a production system;
record any operational application separately.
