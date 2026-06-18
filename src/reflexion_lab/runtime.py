import os
import time
from typing import Protocol
from .schemas import QAExample, JudgeResult, ReflectionEntry
from .utils import normalize_answer, safe_parse_json, extract_final_answer

class ActorOutput:
    def __init__(self, answer: str, raw: str, token_usage: int, latency_ms: float):
        self.answer = answer
        self.raw = raw
        self.token_usage = token_usage
        self.latency_ms = latency_ms

class EvaluatorOutput:
    def __init__(self, judge: JudgeResult, raw: str, token_usage: int, latency_ms: float):
        self.judge = judge
        self.raw = raw
        self.token_usage = token_usage
        self.latency_ms = latency_ms

class ReflectorOutput:
    def __init__(self, reflection: ReflectionEntry, raw: str, token_usage: int, latency_ms: float):
        self.reflection = reflection
        self.raw = raw
        self.token_usage = token_usage
        self.latency_ms = latency_ms

class RuntimeProtocol(Protocol):
    def actor(self, example: QAExample, attempt_id: int, agent_type: str, reflection_memory: list[str]) -> ActorOutput:
        ...
    def evaluator(self, example: QAExample, predicted_answer: str) -> EvaluatorOutput:
        ...
    def reflector(self, example: QAExample, attempt_id: int, judge: JudgeResult, wrong_answer: str) -> ReflectorOutput:
        ...

class MockRuntime:
    def actor(self, example: QAExample, attempt_id: int, agent_type: str, reflection_memory: list[str]) -> ActorOutput:
        start_time = time.perf_counter()
        
        is_correct = True
        if attempt_id == 1 and not reflection_memory:
            is_correct = False
            
        answer = example.gold_answer if is_correct else "Partial or incorrect answer based on context."
        
        latency = (time.perf_counter() - start_time) * 1000 + 100
        token_usage = len(example.question.split()) + len(answer.split()) * 2 + 50
        
        return ActorOutput(answer=answer, raw=answer, token_usage=token_usage, latency_ms=latency)

    def evaluator(self, example: QAExample, predicted_answer: str) -> EvaluatorOutput:
        start_time = time.perf_counter()
        
        is_match = normalize_answer(example.gold_answer) == normalize_answer(predicted_answer)
        score = 1 if is_match else 0
        reason = "Matches gold answer" if is_match else "Does not match gold answer"
        failure_mode = "none" if is_match else "wrong_final_answer"
        
        judge = JudgeResult(score=score, reason=reason, failure_mode=failure_mode, confidence=0.9)
        
        latency = (time.perf_counter() - start_time) * 1000 + 50
        token_usage = 80
        return EvaluatorOutput(judge=judge, raw=reason, token_usage=token_usage, latency_ms=latency)

    def reflector(self, example: QAExample, attempt_id: int, judge: JudgeResult, wrong_answer: str) -> ReflectorOutput:
        start_time = time.perf_counter()
        
        ref = ReflectionEntry(
            attempt_id=attempt_id,
            failure_reason=judge.reason,
            lesson="Need to read context more carefully.",
            next_strategy="Extract entities precisely before answering."
        )
        
        latency = (time.perf_counter() - start_time) * 1000 + 60
        token_usage = 120
        return ReflectorOutput(reflection=ref, raw=judge.reason, token_usage=token_usage, latency_ms=latency)

class LLMRuntime:
    def __init__(self):
        try:
            from openai import OpenAI
            self.client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", "dummy"))
            self.model = os.environ.get("REFLEXION_MODEL", "gpt-4o-mini")
            self.temperature = float(os.environ.get("REFLEXION_TEMPERATURE", "0.0"))
        except ImportError:
            self.client = None
            
    def _call_llm(self, messages: list[dict], response_format=None) -> tuple[str, int, float]:
        start = time.perf_counter()
        if not self.client:
            raise RuntimeError("OpenAI package not installed. Run pip install openai.")
            
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
        }
        if response_format:
            kwargs["response_format"] = response_format
            
        try:
            response = self.client.chat.completions.create(**kwargs)
            content = response.choices[0].message.content or ""
            tokens = response.usage.total_tokens if response.usage else len(content.split()) * 2
        except Exception as e:
            content = f'{{"score": 0, "reason": "{str(e)}", "failure_mode": "wrong_final_answer"}}' if response_format else str(e)
            tokens = 0
            
        latency = (time.perf_counter() - start) * 1000
        return content, tokens, latency

    def actor(self, example: QAExample, attempt_id: int, agent_type: str, reflection_memory: list[str]) -> ActorOutput:
        from .prompts import ACTOR_SYSTEM
        
        context_str = "\n".join([f"[{c.title}]: {c.text}" for c in example.context])
        memory_str = "\n".join(reflection_memory) if reflection_memory else "None"
        
        user_prompt = f"Question: {example.question}\n\nContext:\n{context_str}\n\nReflection Memory:\n{memory_str}\n\nProvide your reasoning and then output 'Final answer: <answer>'."
        
        raw, tokens, latency = self._call_llm([
            {"role": "system", "content": ACTOR_SYSTEM},
            {"role": "user", "content": user_prompt}
        ])
        
        answer = extract_final_answer(raw)
        return ActorOutput(answer=answer, raw=raw, token_usage=tokens, latency_ms=latency)

    def evaluator(self, example: QAExample, predicted_answer: str) -> EvaluatorOutput:
        from .prompts import EVALUATOR_SYSTEM
        
        user_prompt = f"Question: {example.question}\nGold Answer: {example.gold_answer}\nPredicted Answer: {predicted_answer}\n\nEvaluate the predicted answer against the gold answer. Return JSON matching the JudgeResult schema."
        
        raw, tokens, latency = self._call_llm([
            {"role": "system", "content": EVALUATOR_SYSTEM},
            {"role": "user", "content": user_prompt}
        ], response_format={"type": "json_object"})
        
        judge = safe_parse_json(
            raw, 
            JudgeResult, 
            {"score": 0, "reason": "JSON parse failed", "failure_mode": "wrong_final_answer", "confidence": 0.0}
        )
        return EvaluatorOutput(judge=judge, raw=raw, token_usage=tokens, latency_ms=latency)

    def reflector(self, example: QAExample, attempt_id: int, judge: JudgeResult, wrong_answer: str) -> ReflectorOutput:
        from .prompts import REFLECTOR_SYSTEM
        
        user_prompt = f"Question: {example.question}\nPredicted Answer (Wrong): {wrong_answer}\nEvaluator Feedback: {judge.reason}\n\nAnalyze why the previous attempt failed and provide a new strategy. Return JSON matching the ReflectionEntry schema."
        
        raw, tokens, latency = self._call_llm([
            {"role": "system", "content": REFLECTOR_SYSTEM},
            {"role": "user", "content": user_prompt}
        ], response_format={"type": "json_object"})
        
        ref = safe_parse_json(
            raw, 
            ReflectionEntry, 
            {"attempt_id": attempt_id, "failure_reason": "JSON parse failed", "lesson": "Parse error", "next_strategy": "Try again"}
        )
        ref.attempt_id = attempt_id
        return ReflectorOutput(reflection=ref, raw=raw, token_usage=tokens, latency_ms=latency)

def get_runtime(mode: str) -> RuntimeProtocol:
    mode = os.environ.get("REFLEXION_MODE", mode).lower()
    if mode == "llm":
        return LLMRuntime()
    return MockRuntime()
