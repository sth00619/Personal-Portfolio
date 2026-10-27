"""Validate the downloaded official SQuAD 2.0 development split."""

from src.dataset import DATA_PATH, load_examples


def test_official_dev_rows_and_answerability_counts() -> None:
    """The pinned official dev file expands to its known records and segments."""
    assert DATA_PATH.is_file(), "Run `docker compose run --rm download` first"
    examples = load_examples()
    assert len(examples) == 11_873
    assert sum(example.is_impossible for example in examples) == 5_945
    assert sum(not example.is_impossible for example in examples) == 5_928
