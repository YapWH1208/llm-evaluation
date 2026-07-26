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
