"""Load FUNSD entities and candidate key-value links from the official split."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image


@dataclass(frozen=True)
class Entity:
    """A FUNSD semantic entity and its normalized document location."""

    document_id: str
    entity_id: int
    text: str
    label: str
    box: tuple[float, float, float, float]
    page_width: float
    page_height: float


@dataclass(frozen=True)
class PairExample:
    """One question-answer candidate and whether FUNSD links the pair."""

    document_id: str
    question: Entity
    answer: Entity
    linked: bool


def _read_document(annotation_path: Path, image_path: Path) -> list[dict[str, Any]]:
    """Read annotation entities and validate their referenced image dimensions."""
    payload = json.loads(annotation_path.read_text(encoding="utf-8"))
    with Image.open(image_path) as image:
        width, height = image.size
    if width <= 0 or height <= 0:
        raise ValueError(f"Invalid image dimensions: {image_path}")
    form = payload.get("form")
    if not isinstance(form, list):
        raise ValueError(f"Missing form entity list in {annotation_path}")
    return [{**entity, "_page_width": width, "_page_height": height} for entity in form]


def load_split(root: Path, split: str) -> list[PairExample]:
    """Load all question-answer candidates from FUNSD's train or test split."""
    if split not in {"training_data", "testing_data"}:
        raise ValueError("split must be 'training_data' or 'testing_data'")
    split_dir = root / split
    annotations_dir = split_dir / "annotations"
    image_dir = split_dir / "images"
    annotation_paths = sorted(annotations_dir.glob("*.json"))
    if not annotation_paths:
        raise FileNotFoundError(f"No FUNSD annotations found in {annotations_dir}")

    examples: list[PairExample] = []
    for path in annotation_paths:
        image_path = image_dir / f"{path.stem}.png"
        if not image_path.is_file():
            raise FileNotFoundError(f"Image missing for annotation: {path.name}")
        raw_entities = _read_document(path, image_path)
        entities: dict[int, Entity] = {}
        links: set[tuple[int, int]] = set()
        for raw in raw_entities:
            entity_id = int(raw["id"])
            box_values = tuple(float(value) for value in raw["box"])
            if len(box_values) != 4:
                raise ValueError(f"Entity {entity_id} has invalid box in {path}")
            entity = Entity(
                document_id=path.stem,
                entity_id=entity_id,
                text=str(raw.get("text", "")).strip(),
                label=str(raw.get("label", "other")),
                box=box_values,  # type: ignore[arg-type]
                page_width=float(raw["_page_width"]),
                page_height=float(raw["_page_height"]),
            )
            entities[entity_id] = entity
            for linked_ids in raw.get("linking", []):
                if len(linked_ids) != 2:
                    raise ValueError(f"Invalid link from entity {entity_id} in {path}")
                links.add((int(linked_ids[0]), int(linked_ids[1])))

        questions = [entity for entity in entities.values() if entity.label == "question"]
        answers = [entity for entity in entities.values() if entity.label == "answer"]
        positive_links = {
            (entities[left].entity_id, entities[right].entity_id)
            for left, right in links
            if left in entities
            and right in entities
            and entities[left].label == "question"
            and entities[right].label == "answer"
        }
        for question in questions:
            for answer in answers:
                examples.append(
                    PairExample(
                        document_id=path.stem,
                        question=question,
                        answer=answer,
                        linked=(question.entity_id, answer.entity_id) in positive_links,
                    )
                )
    return examples


def linked_pair_keys(examples: list[PairExample]) -> set[tuple[str, int, int]]:
    """Return the gold or predicted linked key-value entity identifiers."""
    return {
        (example.document_id, example.question.entity_id, example.answer.entity_id)
        for example in examples
        if example.linked
    }
