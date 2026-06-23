"""Worked example: a todo app whose schema comes from Pydantic models.

Run, from the python/ workspace root:

    uv run python honest-persist/examples/pydantic_todo.py

Define Pydantic models, load them to an honest-persist Schema with load_schema_from_models, and run
the shared todo demo: migrate to SQLite, add and complete todos through the pure query builders, and
watch the enum foreign key refuse an undeclared status. The demo is the same one django_todo.py runs
— only the model definitions differ, because honest-persist sees only the Schema dict.
"""

import asyncio
from typing import Literal

from pydantic import BaseModel, Field

from honest_persist.loader import load_schema_from_models, table

from _app import run_todo_demo


@table("todos")
class Todo(BaseModel):
    id: int = Field(json_schema_extra={"primary": True})
    title: str
    status: Literal["open", "done"] = Field(json_schema_extra={"default": "'open'"})


if __name__ == "__main__":
    asyncio.run(run_todo_demo(load_schema_from_models(Todo)))
