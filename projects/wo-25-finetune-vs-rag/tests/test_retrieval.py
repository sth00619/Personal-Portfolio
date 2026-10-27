import pytest

from wo25.retrieval import WorkedExampleRetriever, tokenize


def test_retriever_returns_top_k_and_excludes_exact_query():
    examples = [
        {"case_id": "a", "question": "How many apples are left?", "answer": "#### 2"},
        {"case_id": "b", "question": "How many oranges remain?", "answer": "#### 3"},
        {"case_id": "c", "question": "How many apples were bought?", "answer": "#### 4"},
    ]
    retriever = WorkedExampleRetriever(examples)
    results = retriever.retrieve("How many apples are left?", 2, {"How many apples are left?"})
    assert len(results) == 2
    assert all(row["case_id"] != "a" for row in results)


def test_retriever_rejects_invalid_inputs():
    with pytest.raises(ValueError):
        WorkedExampleRetriever([])
    retriever = WorkedExampleRetriever([{"question": "Q", "answer": "A"}])
    with pytest.raises(ValueError):
        retriever.retrieve("Q", 0)
    assert tokenize("Cats 1,234") == ["cats", "1", "234"]
