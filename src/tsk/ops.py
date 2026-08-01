import json
import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True)
class Create:
    """Bring a task into existence with a title."""
    id: str
    lamport: int
    title: str

@dataclass(frozen=True)
class SetStatus:
    """Move a task to a new status."""
    id: str
    lamport: int
    status: str

@dataclass(frozen=True)
class SetTitle:
    """Replace a task's title."""
    id: str
    lamport: int
    title: str

@dataclass(frozen=True)
class SetBody:
    """Replace a task's body."""
    id: str
    lamport: int
    body: str

@dataclass(frozen=True)
class SetDeleted:
    """Hide a task from the backlog, or restore it."""
    id: str
    lamport: int
    deleted: bool

@dataclass(frozen=True)
class Unknown:
    """
    An op this version of tsk does not understand.

    A replica running a newer tsk may write ops we have no case for. Parsing
    them into Unknown keeps the payload intact and lets the fold skip a single
    op rather than fail on the whole task.
    """
    id: str
    lamport: int
    payload: dict


Op = Create | SetStatus | SetTitle | SetBody | SetDeleted | Unknown


def to_json(op: Op) -> dict:
    """
    Render an op as the flat dict that goes on the wire.

    Args:
        op: the op to render.

    Returns:
        The op as a flat dict (str keys; str, int or bool values).
    """
    match op:
        case Create(id=task_id, lamport=lamport, title=title):
            return {"op": "create", "id": task_id, "lamport": lamport, "title": title}
        case SetStatus(id=task_id, lamport=lamport, status=status):
            return {"op": "set_status", "id": task_id, "lamport": lamport, "status": status}
        case SetTitle(id=task_id, lamport=lamport, title=title):
            return {"op": "set_title", "id": task_id, "lamport": lamport, "title": title}
        case SetBody(id=task_id, lamport=lamport, body=body):
            return {"op": "set_body", "id": task_id, "lamport": lamport, "body": body}
        case SetDeleted(id=task_id, lamport=lamport, deleted=deleted):
            return {"op": "set_deleted", "id": task_id, "lamport": lamport, "deleted": deleted}
        case Unknown(payload=payload):
            return dict(payload)

def from_json(payload: dict) -> Op:
    """
    Parse a wire dict into an op.

    Anything that does not match a known shape becomes Unknown rather than
    raising: one unreadable op must not make a whole task unreadable.

    Args:
        payload: the op as read back from its blob.

    Returns:
        The parsed op.
    """
    match payload:
        case {"op": "create", "id": task_id, "lamport": lamport, "title": title}:
            return Create(id=task_id, lamport=lamport, title=title)
        case {"op": "set_status", "id": task_id, "lamport": lamport, "status": status}:
            return SetStatus(id=task_id, lamport=lamport, status=status)
        case {"op": "set_title", "id": task_id, "lamport": lamport, "title": title}:
            return SetTitle(id=task_id, lamport=lamport, title=title)
        case {"op": "set_body", "id": task_id, "lamport": lamport, "body": body}:
            return SetBody(id=task_id, lamport=lamport, body=body)
        case {"op": "set_deleted", "id": task_id, "lamport": lamport, "deleted": deleted}:
            return SetDeleted(id=task_id, lamport=lamport, deleted=deleted)
        case _:
            return Unknown(
                id=payload.get("id", ""),
                lamport=payload.get("lamport", 0),
                payload=payload,
            )

def tag(op: Op) -> str:
    """
    Name an op's kind, as it appears on the wire.

    Args:
        op: the op to name.

    Returns:
        The op's tag, e.g. "set_status". Doubles as the commit message.
    """
    return to_json(op)["op"]

def canonical(op: Op) -> bytes:
    """
    Serialize an op to its canonical byte form for hashing.

    Deterministic across machines: NFC-normalized string values, sorted keys,
    no incidental whitespace, UTF-8, no trailing newline. The blob these bytes
    hash to is the op's identity (ADR-0004), so this encoding is frozen.

    Args:
        op: the op to serialize.

    Returns:
        The canonical UTF-8 bytes.
    """
    normalized = {
        key: unicodedata.normalize("NFC", value) if isinstance(value, str) else value
        for key, value in to_json(op).items()
    }
    text = json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return text.encode()
