# Architecture Decision Records

An ADR records one architectural decision: the context that forced it, the choice
made, the alternatives rejected, and the price paid. We keep them because `tsk`
exists to learn git internals, and the reasoning behind a design is worth more than
the design itself — an ADR is where that reasoning survives after the code stops
explaining it.

## Numbering

ADRs are numbered sequentially with four digits (`0001`, `0002`, ...). Numbers are
never reused. A withdrawn or superseded ADR keeps its number forever.

## Immutability

An ADR is immutable once accepted. We do not edit an accepted ADR to reflect a new
decision. When a decision changes, we mark the old ADR `Superseded` and write a new
ADR that supersedes it. The old reasoning stays readable exactly as it was, because
the point of the log is to show how the design moved, not to hide that it did.

## Index

| Number | Title | Status |
| --- | --- | --- |
| [0001](docs/adr/0001-ops-in-custom-refs.md) | Ops in custom refs | Accepted |
| [0002](docs/adr/0002-dag-merge-not-linear-rebase.md) | DAG merge, not linear rebase | Accepted |
| [0003](docs/adr/0003-op-payload-in-blob-not-commit-message.md) | Op payload in blob+tree, not in the commit message | Accepted |
| [0004](docs/adr/0004-op-identity-is-blob-oid.md) | Op identity is the blob OID | Accepted |
