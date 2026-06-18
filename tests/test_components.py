import pytest
from src.reflexion_lab.schemas import QAExample, JudgeResult, ReflectionEntry
from src.reflexion_lab.utils import normalize_answer, safe_parse_json, extract_final_answer

def test_normalize_answer():
    assert normalize_answer("The United States") == "united states"
    assert normalize_answer("yes.") == "yes"
    assert normalize_answer("No!") == "no"
    assert normalize_answer("A cat in the hat.") == "cat in hat"
    assert normalize_answer("True") == "yes"

def test_extract_final_answer():
    text1 = "I think the answer is obvious.\nFinal Answer: London"
    assert extract_final_answer(text1) == "London"
    
    text2 = "Some reasoning.\nTherefore, it is Paris."
    assert extract_final_answer(text2) == "Therefore, it is Paris."
    
def test_safe_parse_json():
    # Valid json
    res = safe_parse_json('{"score": 1, "reason": "good", "failure_mode": "none"}', JudgeResult, {"score": 0})
    assert res.score == 1
    
    # Fenced json
    res2 = safe_parse_json('```json\n{"score": 0, "reason": "bad", "failure_mode": "entity_drift"}\n```', JudgeResult, {"score": 1})
    assert res2.score == 0
    assert res2.failure_mode == "entity_drift"
    
    # Invalid failure mode coercion
    res3 = safe_parse_json('{"score": 1, "reason": "ok", "failure_mode": "invalid_mode"}', JudgeResult, {"score": 0})
    assert res3.failure_mode == "wrong_final_answer"
    
    # Fallback
    res4 = safe_parse_json('not json at all', JudgeResult, {"score": 0, "reason": "fallback", "failure_mode": "none", "confidence": 0.0})
    assert res4.score == 0
    assert res4.reason == "fallback"
