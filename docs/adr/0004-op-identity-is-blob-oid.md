# ADR-0004: Op identity is the blob OID

## Status

Accepted — 2026-07-17

## Context

The merge needs to deduplicate ops, and the total order needs a deterministic
tie-breaker for ops that share a lamport value. Both need a stable per-op identifier.

## Decision

An op's identity is the OID of the blob holding its JSON.

## Alternatives considered

The original rationale for this decision was that commit OIDs are unstable under
rewrite — a commit's OID hashes its parent, so re-chaining an op gives it a new commit
OID. ADR-0002's revision removed rewrite from the design entirely, so commit OIDs are
now permanently stable and that argument no longer holds. The decision stands, but on a
different and stronger basis: the total order must depend only on the ops themselves and
never on how they were packaged for transport. A commit OID mixes op content with the
parent, the committer date, and the message — accidents of the envelope. If the commit
encoding ever changes (two ops per commit, an added signature, a different message
format), every commit OID changes and the backlog's historical order silently
reshuffles. A blob OID hashes op content and nothing else.

Related: blob-based dedupe is now defensive rather than load-bearing. `rev-list` already
deduplicates commits during traversal, and git deduplicates objects in the store. It is
free and harmless — keep it, but do not cite it as the justification.

## Consequences

### Positive

- The total order is stable across any future change to the transport encoding.
- Identical ops arriving via two paths of the DAG collapse automatically.

### Negative

1. **This requires byte-deterministic JSON serialization, with no exceptions:**
   `json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)` encoded
   UTF-8, no trailing newline, no indent. If two machines serialize the same op to
   different bytes, their OIDs differ, dedupe fails, and the tie-breaker stops being
   deterministic — invariant I3 breaks silently and the divergence is discovered weeks
   later as two backlogs that do not agree.

2. **We inherit git's hash threat model, including its total absence of collision
   handling.** Git checks whether an OID already exists and skips the write if so, which
   is simultaneously the dedupe mechanism and the reason a collision would silently
   discard content. Accidental collision resistance is complete at our scale (roughly
   10^-41 for 10^4 objects; ~33 orders of magnitude less likely than an uncorrectable
   RAM error). Adversarial collision resistance is SHA-1's, which is broken —
   chosen-prefix collisions were demonstrated at roughly USD 45k in 2020. This is
   irrelevant to us: anyone capable of mounting the attack already has write access to
   the repo and can simply write the malicious op directly. A collision attack only buys
   something when it crosses a trust boundary, and our team has none. Revisit this if the
   backlog is ever exposed beyond people with push access.
