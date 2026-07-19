from dataclasses import dataclass

@dataclass
class Task:
    id: str
    title: str
    status: str = "todo"
