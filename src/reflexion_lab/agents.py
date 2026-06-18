from __future__ import annotations
from dataclasses import dataclass
from typing import Literal
from .runtime import get_runtime
from .schemas import AttemptTrace, QAExample, ReflectionEntry, RunRecord

def format_reflection(ref: ReflectionEntry) -> str:
    return f"Previous attempt failed because: {ref.failure_reason}\nLesson: {ref.lesson}\nNext strategy: {ref.next_strategy}"

@dataclass
class BaseAgent:
    agent_type: Literal["react", "reflexion"]
    max_attempts: int = 1
    
    def run(self, example: QAExample) -> RunRecord:
        runtime = get_runtime("mock") # Default, but inside get_runtime it checks env
        
        reflection_memory: list[str] = []
        reflections: list[ReflectionEntry] = []
        traces: list[AttemptTrace] = []
        final_answer = ""
        final_score = 0
        failure_mode = "wrong_final_answer"
        
        for attempt_id in range(1, self.max_attempts + 1):
            actor_out = runtime.actor(example, attempt_id, self.agent_type, reflection_memory)
            eval_out = runtime.evaluator(example, actor_out.answer)
            
            # Phase 4 logic: 2-tier evaluator
            from .utils import normalize_answer
            is_match = normalize_answer(example.gold_answer) == normalize_answer(actor_out.answer)
            if is_match:
                eval_out.judge.score = 1
                eval_out.judge.failure_mode = "none"
                eval_out.judge.reason = "Exact match"
            
            trace = AttemptTrace(
                attempt_id=attempt_id, 
                answer=actor_out.answer, 
                score=eval_out.judge.score, 
                reason=eval_out.judge.reason, 
                token_estimate=actor_out.token_usage + eval_out.token_usage, 
                latency_ms=int(actor_out.latency_ms + eval_out.latency_ms)
            )
            final_answer = actor_out.answer
            final_score = eval_out.judge.score
            
            if hasattr(eval_out.judge, "failure_mode"):
                failure_mode = eval_out.judge.failure_mode
                
            if eval_out.judge.score == 1:
                failure_mode = "none"
                traces.append(trace)
                break
            
            if self.agent_type == "reflexion" and attempt_id < self.max_attempts:
                ref_out = runtime.reflector(example, attempt_id, eval_out.judge, actor_out.answer)
                reflections.append(ref_out.reflection)
                trace.reflection = ref_out.reflection
                trace.token_estimate += ref_out.token_usage
                trace.latency_ms += int(ref_out.latency_ms)
                reflection_memory.append(format_reflection(ref_out.reflection))
                
            traces.append(trace)
            
        total_tokens = sum(t.token_estimate for t in traces)
        total_latency = sum(t.latency_ms for t in traces)
        
        return RunRecord(
            qid=example.qid, 
            question=example.question, 
            gold_answer=example.gold_answer, 
            agent_type=self.agent_type, 
            predicted_answer=final_answer, 
            is_correct=bool(final_score), 
            attempts=len(traces), 
            token_estimate=total_tokens, 
            latency_ms=total_latency, 
            failure_mode=failure_mode, 
            reflections=reflections, 
            traces=traces
        )

class ReActAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__(agent_type="react", max_attempts=1)

class ReflexionAgent(BaseAgent):
    def __init__(self, max_attempts: int = 3) -> None:
        super().__init__(agent_type="reflexion", max_attempts=max_attempts)
