"""Check paired uncertainty calculations on small deterministic vectors."""

import numpy as np

from src.dataset import QAExample, select_examples
from src.evaluation import holm_adjusted_p_values, paired_bootstrap_interval
from src.prompts import PROMPT_A_SYSTEM, PROMPT_B_SYSTEM


def test_holm_step_down_adjustment_is_monotone_in_sorted_order() -> None:
    """Holm adjusted p-values remain bounded and respect sorted ranks."""
    adjusted = holm_adjusted_p_values([0.01, 0.04, 0.03])
    assert adjusted == [0.03, 0.06, 0.06]


def test_bootstrap_interval_contains_effect_of_constant_paired_deltas() -> None:
    """A constant paired difference yields a degenerate interval at that effect."""
    interval = paired_bootstrap_interval(np.full(20, 0.25), repetitions=200, seed=1)
    assert interval == [0.25, 0.25]


def test_subset_is_balanced_and_reproducible() -> None:
    """A requested balanced subset contains equal answerability segments."""
    examples = [
        QAExample(str(index), "title", "context", "question", (() if index < 6 else ("answer",)), index < 6)
        for index in range(12)
    ]
    selected = select_examples(examples, 8, seed=5)
    assert len(selected) == 8
    assert sum(example.is_impossible for example in selected) == 4
    assert selected == select_examples(examples, 8, seed=5)


def test_prompt_b_adds_only_the_unanswerable_instruction() -> None:
    """The prompt pair differs only in its abstention rule."""
    assert PROMPT_A_SYSTEM != PROMPT_B_SYSTEM
    assert "NO_ANSWER" not in PROMPT_A_SYSTEM
    assert "NO_ANSWER" in PROMPT_B_SYSTEM
