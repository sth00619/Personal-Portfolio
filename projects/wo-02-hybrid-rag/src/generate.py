"""Create cited answers with a local NLI model and extractive evidence."""

import re
from collections import defaultdict

import numpy as np
from sentence_transformers import CrossEncoder

from .models import EvalQuestion, GroundedAnswer, SearchHit

NLI_MODEL = "cross-encoder/nli-deberta-v3-xsmall"
NLI_BATCH_SIZE = 64
GENERATION_CONTEXTS = 1
MAX_SENTENCES_PER_CHUNK = 8
MIN_SENTENCE_CHARACTERS = 30
LABEL_ORDER = ("CONTRADICT", "SUPPORT", "NEUTRAL")
SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")


def evidence_sentences(text: str) -> list[str]:
    """Split a chunk into sufficiently informative sentence candidates."""
    sentences = [
        sentence.strip()
        for sentence in SENTENCE_BOUNDARY.split(text)
        if len(sentence.strip()) >= MIN_SENTENCE_CHARACTERS
    ]
    return sentences[:MAX_SENTENCES_PER_CHUNK] or [text.strip()]


def _relevant_rank(question: EvalQuestion, hits: list[SearchHit]) -> int | None:
    """Return the first rank containing a human-labeled relevant document."""
    relevant = set(question.relevant_doc_ids)
    return next(
        (rank for rank, hit in enumerate(hits, 1) if hit.doc_id in relevant), None
    )


def generate_answers(
    questions: list[EvalQuestion],
    contexts: dict[str, list[SearchHit]],
    nli_model: CrossEncoder,
) -> list[GroundedAnswer]:
    """Predict verdicts and quote the strongest cited evidence sentence."""
    pairs: list[tuple[str, str]] = []
    candidates: list[tuple[str, SearchHit, str]] = []
    question_lookup = {question.query_id: question for question in questions}
    candidate_indices: defaultdict[str, list[int]] = defaultdict(list)

    for question in questions:
        for hit in contexts[question.query_id][:GENERATION_CONTEXTS]:
            for sentence in evidence_sentences(hit.text):
                candidate_indices[question.query_id].append(len(candidates))
                candidates.append((question.query_id, hit, sentence))
                pairs.append((sentence, question.claim))

    raw_scores = np.asarray(
        nli_model.predict(pairs, batch_size=NLI_BATCH_SIZE, show_progress_bar=True)
    )
    if raw_scores.ndim != 2 or raw_scores.shape[1] != len(LABEL_ORDER):
        raise ValueError(f"Unexpected NLI score shape: {raw_scores.shape}")

    answers: list[GroundedAnswer] = []
    for query_id, indices in candidate_indices.items():
        question = question_lookup[query_id]
        best_index = max(
            indices,
            key=lambda index: float(max(raw_scores[index][0], raw_scores[index][1])),
        )
        _, hit, rationale = candidates[best_index]
        contradiction, support, _neutral = raw_scores[best_index]
        predicted = "SUPPORT" if support >= contradiction else "CONTRADICT"
        confidence = float(max(support, contradiction))
        ranked_hits = contexts[query_id]
        answer_text = f"{predicted}. {rationale} [{hit.chunk_id}]"
        answers.append(
            GroundedAnswer(
                query_id=query_id,
                question_type=question.question_type,
                expected_label=question.expected_label,
                predicted_label=predicted,
                claim=question.claim,
                answer=answer_text,
                rationale=rationale,
                citation=hit.chunk_id,
                citation_text=hit.text,
                confidence=confidence,
                relevant_doc_ids=question.relevant_doc_ids,
                retrieved_doc_ids=tuple(item.doc_id for item in ranked_hits),
                relevant_rank=_relevant_rank(question, ranked_hits),
            )
        )
    return answers
