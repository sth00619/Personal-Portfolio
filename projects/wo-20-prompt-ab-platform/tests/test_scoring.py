"""Verify SQuAD answer normalization and impossible-question scoring."""

from src.scoring import exact_match, is_abstention, normalize_answer, score_answer, token_f1


def test_official_normalization_ignores_case_articles_punctuation() -> None:
    """Punctuation, articles, and case do not change an exact match."""
    assert normalize_answer("The U.S. Constitution!") == "us constitution"
    assert exact_match("The U.S. Constitution!", ("US constitution",)) == 1.0


def test_f1_uses_best_reference_answer() -> None:
    """Multiple human references are evaluated by their best token overlap."""
    assert token_f1("New York", "New York City") == 0.8
    assert score_answer("New York", ("New York City", "NYC"), False)["f1"] == 0.8


def test_impossible_question_requires_an_abstention() -> None:
    """Explicit refusal scores as the empty SQuAD answer only on impossible items."""
    assert is_abstention("NO_ANSWER")
    assert score_answer("NO_ANSWER", (), True)["em"] == 1.0
    assert score_answer("Paris", (), True)["f1"] == 0.0
    assert score_answer("NO_ANSWER", ("Paris",), False)["f1"] == 0.0


def test_context_limited_explanation_counts_as_abstention() -> None:
    """A full sentence refusing unsupported information maps to empty answer."""
    response = "The passage does not specify packet switching's bit rate."
    assert is_abstention(response)
    assert score_answer(response, (), True)["f1"] == 1.0
    assert score_answer(response, ("10 Mbps",), False)["f1"] == 0.0


def test_context_caveat_does_not_hide_an_answer_in_the_same_response() -> None:
    """A refusal-like preface remains scorable when the response contains the gold."""
    response = "The passage does not say they secured the right; it says they petitioned in 1697."
    score = score_answer(response, ("1697",), False)
    assert score["f1"] > 0.0
    assert score["abstained"] is False
