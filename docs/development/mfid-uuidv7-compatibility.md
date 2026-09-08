# MFID UUIDv7 compatibility assessment

## Status

MFID generation remains unchanged. Nano continues to depend on `mfid>=1.0.0`, and locally supplied or generated MFIDs remain supported. Migrating the generator to final RFC 9562 UUIDv7 is deferred because the API currently relies on the historical MFID lexical ordering for collection ordering and keyset pagination.

This assessment records the behavior behind nano-crucible issue [#14](https://github.com/MolecularFoundryCrucible/nano-crucible/issues/14). It does not authorize an MFID dependency or format change.

## Current implementation

The [`MolecularFoundry/mfid`](https://github.com/MolecularFoundry/mfid) package encodes a 128-bit UUID as 26 lowercase Crockford Base32 characters. Nano validates the resulting shape but otherwise treats MFIDs as opaque canonical identifiers.

MFID 1.0.0 depends on the [`uuid7`](https://github.com/stevesimmons/uuid7) package. That dependency describes itself as implementing the Peabody UUIDv7 draft and its source references `draft-peabody-dispatch-new-uuid-format-02`. Its layout allocates approximately 36 bits to whole seconds, 24 bits to fractional seconds, 14 bits to a sequence counter, and 48 bits to randomness, in addition to the version and variant bits.

The MFID README links to final RFC 9562 and describes the package as standards-compliant, but its UUID anatomy diagram and installed dependency implement the earlier draft layout. Setting the UUID version field to 7 does not make that layout compliant with the final RFC.

Final [RFC 9562 UUIDv7](https://www.rfc-editor.org/rfc/rfc9562.html#section-5.7) instead uses a 48-bit Unix millisecond timestamp followed by the version, 12-bit `rand_a`, variant, and 62-bit `rand_b` fields. The `rand_a` field may contain randomness, a sub-millisecond fraction, a counter, or a combination of those values.

## Windows prefix behavior

The historical implementation obtains sub-second timestamp bits from `time.time_ns()`. Windows may return the same effective clock value for several rapid calls. The dependency then increments its sequence counter and generates a new random tail, preserving uniqueness of the complete UUID.

The first 13 Crockford Base32 characters encode the historical layout's timestamp, version, and a fixed variant bit. Its sequence counter and random tail occur later. Multiple values generated during one reported clock tick can therefore have identical 13-character prefixes while retaining distinct complete MFIDs.

A constant-clock check of 20 generated values produced 20 unique full MFIDs, one unique 13-character prefix, and monotonically ordered complete MFIDs. This reproduces the relevant behavior without requiring Windows.

The MFID README presents the first 13 characters as a shortened MFID for cases where time collisions are considered unlikely. That prefix is not a globally unique identifier and must not be used for persistence, lookup, authorization, relationships, or interchange. Nano uses complete 26-character MFIDs for those operations.

## Reliability concerns in the upstream package

- The runtime UUID dependency implements draft-02 rather than final RFC 9562. The dependency tracks this as [`stevesimmons/uuid7#1`](https://github.com/stevesimmons/uuid7/issues/1).
- The MFID documentation combines final-RFC claims with the older draft layout.
- `mfid()` catches every exception raised by UUIDv7 generation and silently falls back to UUIDv4. That preserves probable uniqueness but silently removes time ordering and hides programming or runtime failures.
- The repository contains no automated test suite or continuous integration workflow for Linux, macOS, or Windows. Its only workflow is a manually triggered package publication workflow.
- The package does not test full uniqueness, lexical monotonicity, constant-clock behavior, concurrent generation, fallback behavior, or the documented shortened representation.
- The dependency is not constrained to a known compatible release, so a future upstream release could change the UUID layout without an explicit MFID major-version decision.

## Compatibility impact of final RFC UUIDv7

Both historical and final-RFC values can retain the existing 26-character lowercase Crockford Base32 representation. Equality, database uniqueness, filenames, URLs, and Nano's shape validation would continue to work.

Chronological lexical ordering across the format boundary would not continue to work. Contemporary final-RFC values sort before historical draft-based values because the two layouts encode time differently. Values remain time ordered within their respective format cohorts, but their mixed ordering does not represent creation chronology.

This matters to Crucible because the API currently orders dataset and sample collections by `unique_id DESC` and advances keyset pagination with `unique_id < cursor`. A direct generator migration would place newly generated final-RFC records after historical records instead of at the head of newest-first collections. Static cursor traversal would remain deterministic, but newest-first behavior and incremental consumers could fail.

## Current decision

- Do not change Nano's MFID dependency or generation format as part of issue #14.
- Continue accepting locally supplied and locally generated complete MFIDs.
- Treat the full 26-character value as the only canonical MFID. Do not promise uniqueness for a 13-character prefix.
- Do not add sleeps between generations. Delays are platform-dependent, reduce throughput, and do not establish a reliable uniqueness guarantee.
- Do not silently adopt native `uuid.uuid7()` based on Python version because that would mix final-RFC values with historical values across clients.

## Possible future paths

A narrow upstream repair could retain the historical layout while using a monotonic process-local time source on low-resolution clocks. This could improve visible prefix variation during rapid generation in one process without changing the broad historical ordering. It would not guarantee prefix uniqueness across processes or hosts, so full MFIDs would remain mandatory.

A final RFC 9562 migration requires coordinated ecosystem work:

1. Replace MFID-based chronological ordering in the API with an explicit creation timestamp and deterministic tie-breaker.
2. Replace MFID-only keyset cursors with composite or opaque cursors and handle historical records with missing timestamps.
3. Audit clients, integrations, exports, and storage conventions for direct MFID sorting or timestamp decoding.
4. Define whether rapid-generation prefix differentiation is a supported MFID property and, if so, specify counter behavior in `rand_a`.
5. Add cross-platform, constant-clock, concurrency, encoding, conversion, and mixed-format compatibility tests to the MFID package.
6. Remove the broad UUIDv4 fallback or restrict it to an explicitly selected compatibility mode.
7. Release the new generator as a major MFID version and coordinate its adoption by the API, Nano, ingestion, and other MFID producers.

Historical identifiers must remain valid opaque identifiers after any future migration. Creation timestamps, not mixed-format MFID ordering, should be authoritative for chronological behavior.
