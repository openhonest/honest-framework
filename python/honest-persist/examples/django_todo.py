"""Worked example: a todo app whose schema comes from Django models.

Run, from the python/ workspace root:

    uv run python honest-persist/examples/django_todo.py

Define Django models, load them to an honest-persist Schema with load_schema_from_django, and run the
same shared todo demo as pydantic_todo.py. Only the model definitions differ; honest-persist sees the
same Schema and behaves identically. Django needs its settings configured before any model is
defined, so that happens at the top — the throwaway configuration a standalone Django script uses.
"""

import asyncio

import django
from django.conf import settings

settings.configure(INSTALLED_APPS=["django.contrib.contenttypes", "django.contrib.auth"], DATABASES={})
django.setup()

from django.db import models

from honest_persist.django_loader import load_schema_from_django

from _app import run_todo_demo


class Todo(models.Model):
    title = models.CharField(max_length=200)
    status = models.CharField(max_length=10, choices=[("open", "Open"), ("done", "Done")], default="open")

    class Meta:
        app_label = "demo"
        db_table = "todos"


if __name__ == "__main__":
    asyncio.run(run_todo_demo(load_schema_from_django(Todo)))
