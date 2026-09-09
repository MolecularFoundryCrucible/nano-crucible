# Dataset sidecar and Cast convergence

## Status

The dataset sidecar requested in nano-crucible issue [#24](https://github.com/MolecularFoundryCrucible/nano-crucible/issues/24) is deferred until the Cast workflow is revisited. Nano will not introduce a separate upload receipt, deduplication, or resume format before that design work.

This document records a possible future direction rather than supported user behavior.

## Problem

After uploading local data, a user may need a durable record of the created dataset MFID and Explorer location. Console output is ephemeral, and repeating a create command can accidentally create another dataset.

Issue #24 proposes writing a YAML sidecar beside each uploaded file and using it to skip or resume later uploads. Cast already records created resource MFIDs, file hashes, ingestion requests, relationship state, and partial progress in a lock file. Implementing the sidecar independently would create a second state and resume system with overlapping responsibilities and potentially different safety rules.

API v3 also rejects creation with an MFID that already belongs to a resource. A sidecar cannot safely resume by submitting the original create request again. Resumption must retrieve and verify the existing dataset, compare local and recorded files, and continue only the unfinished operations.

## Shared state direction

Dataset creation and Cast should eventually share an internal state model capable of representing:

- Schema version and producing client version.
- Normalized API endpoint and deployment environment.
- Local source paths relative to an appropriate workflow root.
- File sizes and cryptographic content hashes.
- Created dataset, sample, and associated-file MFIDs.
- Upload, ingestion, metadata, keyword, thumbnail, and relationship progress.
- Entity configuration hashes used to detect changed input after creation.
- Recorded failures and the last safely completed operation.

State must be written atomically after each irreversible remote mutation. A newly created resource must be recorded before later file, metadata, ingestion, thumbnail, or relationship work begins. Resume logic must verify both local input and accessible remote state before skipping an operation.

## Separate user-facing artifacts

The implementations may share a schema and persistence library without forcing every workflow to use the same physical file.

- A single-dataset command may write a concise YAML sidecar beside each explicitly supplied source file. Its primary purpose is discovery and provenance for a human user.
- Cast may retain a workflow-level lock beside the `.crux` recipe. Its primary purpose is complete multi-resource resumption and relationship tracking.

A sidecar should expose only stable identifiers and source provenance. It must not contain credentials, private owner information, signed URLs, or a copied scientific metadata record that can silently become stale.

A possible sidecar representation is:

```yaml
schema_version: 1
api_url: https://crucible.lbl.gov/api/v3
dataset:
  unique_id: 0tbxk31g2dyvf00062prqjhsqc
  project_id: example
  explorer_url: https://crucible.lbl.gov/...
source:
  filename: cool_data_234.h5
  size: 123456
  sha256: ...
associated_file:
  mfid: 0tbxk31g2dyvf00062prqjhsqd
```

The final representation must be derived from the shared state contract rather than adopting this example unchanged.

## Safety requirements

- Sidecar discovery must never silently redirect a command to another API endpoint, project, or dataset.
- An existing sidecar must be validated before any new remote mutation occurs.
- A changed source hash must prevent automatic skipping or resumption.
- A missing, inaccessible, deleted, or mismatched remote dataset must produce an actionable error rather than implicit recreation.
- Existing sidecars and Cast locks must not be overwritten without an explicit option.
- Multi-file datasets must define whether every input receives a sidecar and how all sidecars identify one shared dataset operation.
- Parser-discovered files must be distinguished from files supplied directly by the user.
- Dry runs must not write state that causes a later real operation to be skipped.
- Concurrent processes must not update the same workflow state without exclusive locking.

## Deferred interface questions

- Whether the canonical flag should write sidecars automatically, accept an explicit destination, or support both behaviors.
- Whether a repeated dataset command should only report the existing MFID or offer an explicit verified resume mode.
- Whether a dataset sidecar can be imported into a Cast recipe or lock without recreating the resource.
- Whether YAML is appropriate for both human receipts and machine resume state, or whether they should use separate serializations of one model.
- How state schema migrations and backward compatibility should be managed.
- How cleanup, deletion, and ownership transfer affect local state.

## Revisit conditions

Revisit issue #24 together with Cast when the following work is authorized:

1. Define the shared versioned state model and ownership of its implementation.
2. Audit current Cast lock compatibility and resumption behavior.
3. Define a verified single-dataset resume algorithm against API v3.
4. Specify user-visible sidecar naming, overwrite, import, and recovery behavior.
5. Add state-transition tests covering creation, partial file failure, ingestion failure, changed inputs, missing remote resources, concurrency, and resumption.
6. Update Cast, dataset creation, CLI help, user documentation, and changelog together.

Until then, dataset creation continues to return and display the created MFID, while Cast remains the supported resumable workflow mechanism.
