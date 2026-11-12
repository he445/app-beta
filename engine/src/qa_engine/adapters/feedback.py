"""Coleta do beta em SQLite, com as imagens em ``data_dir/feedback`` (só nesta máquina)."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from qa_engine.adapters.sqlite import SqliteRepository
from qa_engine.ports import FeedbackExample

FEEDBACK_DIR = "feedback"


class SqliteFeedbackStore:
    """``FeedbackStore`` sobre o banco do programa."""

    def __init__(self, repo: SqliteRepository, data_dir: Path) -> None:
        self.repo = repo
        self.folder = data_dir / FEEDBACK_DIR

    def _drop(self, name: str | None) -> None:
        if name:
            (self.folder / name).unlink(missing_ok=True)

    def add(self, example: FeedbackExample) -> None:
        """Grava o exemplo e a imagem dele."""
        example_id = str(uuid.uuid4())
        image_file = None
        if example.image_png:
            self.folder.mkdir(parents=True, exist_ok=True)
            image_file = f"{example.kind}-{example_id}.png"
            (self.folder / image_file).write_bytes(example.image_png)
        replaced = self.repo.put_feedback(
            {
                "id": example_id,
                "kind": example.kind,
                "batch_id": example.batch_id,
                "page_id": example.page_id,
                "reviewer": example.reviewer,
                "created_at": example.created_at,
                "expires_at": example.expires_at,
                "label": dict(example.label),
                "model": dict(example.model),
                "image_file": image_file,
            }
        )
        self._drop(replaced)

    def remove(self, kind: str, page_id: str) -> None:
        """Apaga o exemplo e a imagem dele."""
        self._drop(self.repo.remove_feedback(kind, page_id))

    def examples(
        self, kind: str | None = None, since: str | None = None, until: str | None = None
    ) -> list[dict[str, Any]]:
        """Exemplos com o caminho da imagem."""
        rows = self.repo.feedback_rows(kind, since, until)
        for row in rows:
            name = row.pop("image_file")
            path = self.folder / name if name else None
            row["image_path"] = path if path is not None and path.is_file() else None
        return rows

    def purge(self, now_iso: str) -> int:
        """Apaga os vencidos e as imagens deles."""
        files = self.repo.purge_feedback(now_iso)
        for name in files:
            self._drop(name)
        return len(files)
