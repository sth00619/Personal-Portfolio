# Synthetic data

`python data/generate.py` creates 100 benign synthetic resumes and 60 synthetic prompt-injection attempts. The attack set is balanced across three entry points (`body`, `metadata`, `tool_result`) and four objectives (`email_exfil`, `ats_write`, `score_tamper`, `output_tamper`), with five variants per objective and entry point. Twelve directives are Base64 wrapped, and one metadata attack uses a numeric `score_hint` instead of an instruction string. These are deliberate challenge cases for a keyword classifier.

The corpus is authored for this project and contains no real applicant information or actual email delivery. The `.invalid` destination is reserved for examples. It is a deterministic control-flow benchmark, not a measure of a live language model's susceptibility or real-world attack prevalence. The attack outcome is evaluated from mock tool side effects, never inferred from a detector label.

OWASP's [LLM01:2025 Prompt Injection](https://genai.owasp.org/llmrisk/llm01-prompt-injection/) and [LLM06:2025 Excessive Agency](https://genai.owasp.org/llmrisk/llm062025-excessive-agency/) inform the entry-point and permission taxonomy; the examples and counts here are synthetic.
