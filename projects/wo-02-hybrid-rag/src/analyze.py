"""Separate retrieval failures from grounded-answer generation failures."""

from .models import GroundedAnswer, Qrels, Queries, Run

ERROR_EXAMPLES = 5
RETRIEVAL_CUTOFF = 10


def build_failure_analysis(
    queries: Queries,
    qrels: Qrels,
    final_run: Run,
    answers: list[GroundedAnswer],
) -> dict[str, object]:
    """Return counts and representative cases for two independent failure stages."""
    retrieval_failures: list[dict[str, object]] = []
    for query_id, relevant in qrels.items():
        top_docs = final_run.get(query_id, [])[:RETRIEVAL_CUTOFF]
        if set(top_docs) & relevant.keys():
            continue
        retrieval_failures.append(
            {
                "query_id": query_id,
                "query": queries[query_id],
                "relevant_doc_ids": list(relevant),
                "retrieved_top10": top_docs,
                "reason": "No human-labeled relevant document was retrieved in the top 10.",
            }
        )

    generation_failures: list[dict[str, object]] = []
    for answer in answers:
        relevant_retrieved = bool(
            set(answer.relevant_doc_ids) & set(answer.retrieved_doc_ids[:RETRIEVAL_CUTOFF])
        )
        citation_doc = answer.citation.split("#", maxsplit=1)[0]
        citation_correct = citation_doc in answer.relevant_doc_ids
        verdict_correct = answer.predicted_label == answer.expected_label
        if not relevant_retrieved or (citation_correct and verdict_correct):
            continue
        reasons: list[str] = []
        if not citation_correct:
            reasons.append("the generator cited a non-gold document")
        if not verdict_correct:
            reasons.append("the NLI verdict disagreed with the human label")
        generation_failures.append(
            {
                "query_id": answer.query_id,
                "question_type": answer.question_type,
                "claim": answer.claim,
                "relevant_rank": answer.relevant_rank,
                "expected_label": answer.expected_label,
                "predicted_label": answer.predicted_label,
                "citation": answer.citation,
                "reason": " and ".join(reasons),
            }
        )

    return {
        "retrieval_failure_count": len(retrieval_failures),
        "retrieval_failure_examples": retrieval_failures[:ERROR_EXAMPLES],
        "generation_failure_count": len(generation_failures),
        "generation_failure_examples": generation_failures[:ERROR_EXAMPLES],
    }
