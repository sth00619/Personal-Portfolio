"""SQuAD-compatible answer quality metrics."""

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
    """Apply SQuAD lowercase, punctuation, article, and whitespace rules."""
    lowered = text.lower()
    no_punctuation = "".join(char for char in lowered if char not in string.punctuation)
    return WHITESPACE.sub(" ", ARTICLES.sub(" ", no_punctuation)).strip()


def answer_f1(prediction: str, references: tuple[str, ...], impossible: bool) -> float:
    """Return the best token-overlap F1, scoring abstention on impossible items."""
    normalized = normalize_answer(prediction)
    abstained = is_abstention(prediction)
    if impossible:
        return float(abstained)
    predicted = normalized.split()
    scores = [token_f1(prediction, reference) for reference in references]
    overlap = max(scores, default=0.0)
    return overlap if abstained and overlap > 0.0 else (0.0 if abstained else overlap)


def token_f1(prediction: str, reference: str) -> float:
    """Return SQuAD's token-overlap F1 for one answer-reference pair."""
    predicted_tokens = normalize_answer(prediction).split()
    reference_tokens = normalize_answer(reference).split()
    if not predicted_tokens or not reference_tokens:
        return float(predicted_tokens == reference_tokens)
    overlap = sum((Counter(predicted_tokens) & Counter(reference_tokens)).values())
    if overlap == 0:
        return 0.0
    precision = overlap / len(predicted_tokens)
    recall = overlap / len(reference_tokens)
    return 2 * precision * recall / (precision + recall)


def is_abstention(prediction: str) -> bool:
    """Return whether the answer uses a recognized explicit abstention form."""
    candidate = WHITESPACE.sub(" ", prediction.strip())
    return not candidate or any(pattern.fullmatch(candidate) for pattern in ABSTENTION_PATTERNS)
