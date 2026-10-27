from wo25.scoring import parse_gold_gsm8k, parse_gsm8k_answer, parse_mmlu_answer


def test_gsm8k_answer_marker_and_numeric_normalization():
    assert parse_gsm8k_answer("work\n#### $1,200") == "1200"
    assert parse_gsm8k_answer("calculation 4 + 7 = 11") == "11"
    assert parse_gold_gsm8k("reason\n#### 0.50") == "0.5"
    assert parse_gsm8k_answer("no numeric answer") is None


def test_mmlu_answer_parser_handles_short_and_explanatory_forms():
    assert parse_mmlu_answer("B") == 1
    assert parse_mmlu_answer("Answer: (D).") == 3
    assert parse_mmlu_answer("Answer: C\n") == 2
    assert parse_mmlu_answer("Answer: A because it is the best choice.") == 0

