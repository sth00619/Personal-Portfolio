"""SQuAD-style exact-match, token F1, and abstention metrics."""

from __future__ import annotations

import re
import string
from collections import Counter


ARTICLES = re.compile(r"\b(a|an|the)\b", flags=re.IGNORECASE)
WHITESPACE = re.compile(r"\s+")
ABSTENTION_PATTERNS = tuple(re.compile(pattern, flags=re.IGNORECASE) for pattern in (
    r"^(?:no[_ ]answer|unanswerable|unknown|n/?a)\s*[.!]*$",
    r"^(?:i )?(?:do not|don't) know(?:\b.*)?$",
    r"^(?:i )?(?:cannot|can't|am unable to) answer(?:\b.*)?$",
    r"^(?:there is )?not enough (?:information|context)(?:\b.*)?$",
    r"^(?:the )?answer (?:is )?(?:not (?:in|given by|provided by|stated in|mentioned in) (?:the )?(?:passage|context|text)|cannot be determined)(?:\b.*)?$",
    r"^(?:the )?(?:passage|context|text)\b.*\b(?:does not|doesn't|doesnt|cannot|can't)\s+(?:specify|state|say|mention|provide|contain|include|identify|give|indicate|name|tell|explain|describe|confirm|cover|address|reveal)\b.*$",
))


def normalize_answer(text: str) -> str:
    """Apply the official SQuAD lowercase, punctuation, article, and spacing rules."""
    lowered = text.lower()
    without_punctuation = "".join(character for character in lowered if character not in string.punctuation)
    without_articles = ARTICLES.sub(" ", without_punctuation)
    return WHITESPACE.sub(" ", without_articles).strip()


def is_abstention(text: str) -> bool:
    """Recognize a small, explicit set of answer-refusal forms for impossible items."""
    candidate = WHITESPACE.sub(" ", text.strip())
    return not candidate or any(pattern.fullmatch(candidate) for pattern in ABSTENTION_PATTERNS)


def exact_match(prediction: str, references: tuple[str, ...]) -> float:
    """Return the best normalized exact-match score across reference answers."""
    normalized_prediction = normalize_answer(prediction)
    return float(any(normalized_prediction == normalize_answer(reference) for reference in references))


def token_f1(prediction: str, reference: str) -> float:
    """Return SQuAD's token-overlap F1 for a single answer reference."""
    predicted_tokens = normalize_answer(prediction).split()
    reference_tokens = normalize_answer(reference).split()
    if not predicted_tokens or not reference_tokens:
        return float(predicted_tokens == reference_tokens)
    common = Counter(predicted_tokens) & Counter(reference_tokens)
    overlap = sum(common.values())
    if overlap == 0:
        return 0.0
    precision = overlap / len(predicted_tokens)
    recall = overlap / len(reference_tokens)
    return 2 * precision * recall / (precision + recall)


def score_answer(
    prediction: str,
    references: tuple[str, ...],
    is_impossible: bool,
) -> dict[str, float | bool]:
    """Score an answerable item or map an explicit abstention to SQuAD's empty answer."""
    abstained = is_abstention(prediction)
    if is_impossible:
        score = float(abstained)
        return {"em": score, "f1": score, "abstained": abstained}
    if abstained:
        overlap = max((token_f1(prediction, reference) for reference in references), default=0.0)
        if overlap == 0.0:
            return {"em": 0.0, "f1": 0.0, "abstained": True}
    em = exact_match(prediction, references)
    f1 = max((token_f1(prediction, reference) for reference in references), default=0.0)
    return {"em": em, "f1": f1, "abstained": False}
