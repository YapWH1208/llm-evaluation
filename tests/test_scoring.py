from app.services.scoring import ScoringError, score_prediction


def test_deterministic_scoring_rules_cover_exact_numeric_regex_schema_and_f1() -> None:
    assert score_prediction(" BLUE ", {"answer": "blue", "scoring": {"type": "normalized_exact_match"}}) == 1.0
    assert score_prediction("4.05", {"answer": "4", "scoring": {"type": "numeric_match", "absolute_tolerance": 0.1}}) == 1.0
    assert score_prediction("answer: BLUE", {"answer": "", "scoring": {"type": "regex_match", "pattern": r"BLUE$"}}) == 1.0
    assert score_prediction('{"answer":"BLUE"}', {"answer": "", "scoring": {"type": "json_schema", "schema": {"type": "object", "required": ["answer"], "properties": {"answer": {"type": "string"}}}}}) == 1.0
    assert score_prediction("the blue answer", {"answer": "blue answer", "scoring": {"type": "token_f1"}}) == 0.8


def test_scoring_rejects_invalid_rule_configuration() -> None:
    try:
        score_prediction("x", {"answer": "x", "scoring": {"type": "regex_match", "pattern": "["}})
    except ScoringError as error:
        assert "Invalid regex" in str(error)
    else:
        raise AssertionError("Expected invalid regex scoring configuration to fail.")


def test_deterministic_scoring_covers_generation_speech_and_localization_metrics() -> None:
    assert score_prediction("the cat is on the mat", {"answer": "the cat is on the mat", "scoring": {"type": "bleu"}}) == 1.0
    assert score_prediction("the cat sat", {"answer": "the cat sat on mat", "scoring": {"type": "rouge_l"}}) > 0.7
    assert score_prediction("we need blue", {"answer": "we need blue", "scoring": {"type": "wer"}}) == 1.0
    assert score_prediction("blue", {"answer": "blue", "scoring": {"type": "cer"}}) == 1.0
    assert score_prediction("[0, 0, 2, 2]", {"answer": [1, 1, 3, 3], "scoring": {"type": "iou"}}) == round(1 / 7, 12)
    assert score_prediction("[4, 8]", {"answer": [4, 8], "scoring": {"type": "temporal_localization_error", "tolerance_seconds": 1}}) == 1.0


def test_rule_scoring_uses_safe_result_payloads_and_declarative_output_checks() -> None:
    assert score_prediction('{"tests":[true,{"passed":false}]}', {"answer": None, "scoring": {"type": "unit_test_pass_rate", "expected_count": 2}}) == 0.5
    assert score_prediction("one two", {"answer": None, "scoring": {"type": "length_limit", "unit": "tokens", "min": 2, "max": 2}}) == 1.0
    output = '{"answer":"ok","metadata":{"source":"docs"},"tool":"search","arguments":{"query":"llm"}}'
    assert score_prediction(output, {"answer": None, "scoring": {"type": "required_fields", "fields": ["answer", "metadata.source"]}}) == 1.0
    assert score_prediction(output, {"answer": None, "scoring": {"type": "forbidden_fields", "fields": ["debug"]}}) == 1.0
    assert score_prediction(output, {"answer": None, "scoring": {"type": "output_format", "format": "json"}}) == 1.0
    assert score_prediction("I cannot help with that.", {"answer": None, "scoring": {"type": "refusal_behavior", "must_refuse": True}}) == 1.0
    assert score_prediction(output, {"answer": "search", "scoring": {"type": "tool_selection"}}) == 1.0
    assert score_prediction(output, {"answer": None, "scoring": {"type": "tool_argument_validity", "schema": {"type": "object", "required": ["query"]}}}) == 1.0
    assert score_prediction("See [reference](https://example.test/evidence).", {"answer": None, "scoring": {"type": "citation_presence"}}) == 1.0
    assert score_prediction(output, {"answer": None, "scoring": {"type": "schema_compliance", "schema": {"type": "object", "required": ["answer"]}}}) == 1.0
    assert score_prediction(output, {"answer": None, "scoring": {"type": "rule_checks", "checks": [{"type": "required_fields", "fields": ["answer"]}, {"type": "forbidden_fields", "fields": ["debug"]}]}}) == 1.0
