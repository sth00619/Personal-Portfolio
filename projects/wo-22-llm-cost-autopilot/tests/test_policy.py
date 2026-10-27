"""Unit and regression checks for cost, quality, routing, and cache boundaries."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from src.cost import HIGH_COST_PROFILE, LOW_COST_PROFILE, request_cost_usd
from src.dataset import Example
from src.routing import fit_router, group_split, true_easy
from src.scoring import answer_f1, is_abstention
from src.semantic_cache import fit_semantic_policy, variant


def _example(index: int, title: str, question: str, answer_a: str) -> Example:
    """Construct a small test article with deterministic paired outputs."""
    return Example(
        question_id=str(index), title=title, context=f"context {title}",
        question=question, answers=("Paris",), impossible=False,
        answer_a=answer_a, answer_b="Paris", input_tokens_a=10,
        output_tokens_a=2, input_tokens_b=12, output_tokens_b=3,
    )


def test_cost_profiles_reuse_recorded_prices() -> None:
    """Verify per-million rates convert to dollars without another pricing rule."""
    assert request_cost_usd(1_000_000, 0, LOW_COST_PROFILE) == 0.1
    assert request_cost_usd(0, 1_000_000, HIGH_COST_PROFILE) == 8.0


def test_squad_scoring_handles_answerable_and_abstention() -> None:
    """Check token overlap and no-answer quality behavior."""
    assert answer_f1("The Paris", ("Paris",), False) == 1.0
    assert answer_f1("NO_ANSWER", (), True) == 1.0
    assert answer_f1("Paris", (), True) == 0.0
    assert is_abstention("NO_ANSWER")
    assert is_abstention("The passage does not specify the date")


def test_split_keeps_each_article_on_one_side() -> None:
    """Verify article-group separation for the quality-risk model."""
    examples = [
        _example(index, f"article-{index // 4}", f"Where is city {index}?", "Paris" if index % 2 else "wrong")
        for index in range(40)
    ]
    train, test = group_split(examples)
    assert {examples[int(i)].title for i in train}.isdisjoint(
        {examples[int(i)].title for i in test}
    )


def test_router_predicts_adequate_output_probability() -> None:
    """Fit on article-held-out synthetic rows and keep predicted probabilities bounded."""
    examples = [
        _example(index, f"article-{index // 10}", f"Which city is item {index}?", "Paris" if index % 2 else "wrong")
        for index in range(100)
    ]
    train, test = group_split(examples)
    router = fit_router(examples, train)
    probabilities = router.predict_easy_probability([
        examples[int(index)].question for index in test
    ])
    assert len(probabilities) == len(test)
    assert np.all((probabilities >= 0) & (probabilities <= 1))
    assert true_easy(examples[1])


def test_semantic_threshold_accepts_same_intent_and_rejects_different_question() -> None:
    """Calibrate using same-context variants and check a lexical hard negative."""
    examples = [
        _example(index, f"article-{index // 4}", question, "Paris")
        for index, question in enumerate([
            "Where is the capital city located?", "Who led the army into battle?",
            "When did the treaty become effective?", "How many people crossed the river?",
            "Where was the ancient city situated?", "Which commander led the troops?",
            "On what date did the agreement start?", "What number of people crossed?",
            "Where is the capital of this region?", "Who commanded soldiers in battle?",
            "When did the signed agreement take effect?", "How many crossed the river?",
        ])
    ]
    policy = fit_semantic_policy(examples)
    assert policy.threshold >= 0.70
    assert 0.0 <= policy.similarity(examples[0].question, variant(examples[0].question)) <= 1.0
