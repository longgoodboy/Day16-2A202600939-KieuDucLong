# Steps — Chi tiết từng bước triển khai (100/100)

> Checklist thực thi theo thứ tự dependency. Mỗi step có deliverable rõ ràng.

---

## Milestone 1 — Contract Completion (Schema + Prompts + Utils)

> **Mục tiêu:** Code scaffold không còn TODO/pass. Import package không lỗi.

### Step 1.1: Hoàn thiện `schemas.py`

- [ ] Thay `pass` trong `JudgeResult` bằng đầy đủ 6 fields:
  ```python
  class JudgeResult(BaseModel):
      score: int                                    # 0 hoặc 1
      reason: str = ""
      missing_evidence: list[str] = Field(default_factory=list)
      spurious_claims: list[str] = Field(default_factory=list)
      failure_mode: str = "wrong_final_answer"      # default an toàn
      confidence: float = 0.5                        # 0.0 - 1.0
  ```
- [ ] Thay `pass` trong `ReflectionEntry` bằng đầy đủ 4 fields:
  ```python
  class ReflectionEntry(BaseModel):
      attempt_id: int
      failure_reason: str = ""
      lesson: str = ""
      next_strategy: str = ""
  ```
- [ ] Nới lỏng `QAExample.difficulty` thành `str` với default `"medium"` (chống hidden test có difficulty lạ).
- [ ] Verify: `from src.reflexion_lab.schemas import JudgeResult, ReflectionEntry` không lỗi.
- [ ] Verify: `JudgeResult(score=0)` tạo object thành công với defaults.

**Done khi:** Không còn `pass` trong schema, Pydantic validation OK.

---

### Step 1.2: Mở rộng `utils.py` — Parsers & Normalization

- [ ] Nâng cấp `normalize_answer()`:
  - Lowercase, strip.
  - Remove punctuation.
  - Remove articles: `a`, `an`, `the`.
  - Normalize whitespace.
  - Normalize Unicode (unicodedata.normalize).
  - Normalize yes/no → `yes` / `no`.
- [ ] Thêm `extract_final_answer(text: str) -> str`:
  - Tìm `Final answer:` (case-insensitive).
  - Fallback: lấy dòng cuối non-empty.
  - Strip markdown formatting, quotes.
- [ ] Thêm `safe_parse_json(text: str, model_class: type[T]) -> T`:
  - Try `json.loads(text)` trực tiếp.
  - Nếu fail: tìm `{...}` bằng regex.
  - Nếu fail: tìm trong markdown code fence ` ```json ... ``` `.
  - Validate bằng `model_class.model_validate()`.
  - Fallback: trả default instance với `score=0, reason="parse_error"`.
- [ ] Cải thiện `load_dataset()`: handle missing fields, validate per-item, skip invalid.

**Done khi:** Tất cả parsers unit test pass.

---

### Step 1.3: Viết Prompts

- [ ] Viết `ACTOR_SYSTEM`:
  - Role: "You are a multi-hop question answering agent."
  - Chỉ dùng context provided.
  - Step-by-step reasoning.
  - Cẩn thận entity drift, distractor.
  - Dùng reflection memory nếu có.
  - Output: `Final answer: <answer>`.
- [ ] Viết `EVALUATOR_SYSTEM`:
  - Role: "You are a strict answer evaluator."
  - So sánh predicted vs gold.
  - Chấp nhận minor formatting.
  - Không chấp nhận partial-hop, wrong entity.
  - Output: JSON theo JudgeResult schema (liệt kê tất cả fields).
- [ ] Viết `REFLECTOR_SYSTEM`:
  - Role: "You are a reflection agent."
  - Phân tích lỗi cụ thể.
  - Không copy gold answer.
  - Tạo lesson & next_strategy.
  - Output: JSON theo ReflectionEntry schema.

**Done khi:** Tất cả prompts rõ ràng, structured, có output format cụ thể.

---

## Milestone 2 — Runtime & Agent Layer

> **Mục tiêu:** Mock mode chạy ổn định, LLM mode sẵn sàng. Agent logic hoàn chỉnh.

### Step 2.1: Refactor Mock Runtime

- [ ] Loại bỏ `FIRST_ATTEMPT_WRONG` dict (phụ thuộc qid).
- [ ] Loại bỏ `FAILURE_MODE_BY_QID` dict (phụ thuộc qid).
- [ ] Mock `actor_answer()`:
  - Attempt 1 (ReflexionAgent, không có reflection): trả partial answer hoặc wrong answer dựa trên context.
  - Attempt 1 (ReActAgent): tương tự.
  - Attempt 2+ (có reflection memory): trả gold answer.
  - Logic: dùng normalized match trên context text, **không** dùng qid.
- [ ] Mock `evaluator()`:
  - Dùng `normalize_answer()` comparison.
  - Trả `JudgeResult` đầy đủ fields.
  - Suy ra `failure_mode` từ answer comparison (entity drift, incomplete_multi_hop, etc.).
- [ ] Mock `reflector()`:
  - Trả `ReflectionEntry` generic dựa trên `JudgeResult.reason`.
- [ ] Mock token estimation: `len(text.split()) * 1.3` (rough tokenizer).
- [ ] Mock latency estimation: random within realistic range hoặc computation-based.

**Done khi:** Mock mode chạy không phụ thuộc qid.

---

### Step 2.2: Tạo Runtime Adapter

- [ ] Tạo `src/reflexion_lab/runtime.py`:
  ```python
  class RuntimeResult:
      content: str
      token_usage: int
      latency_ms: float
  ```
- [ ] `get_runtime(mode: str)`:
  - `mode="mock"` → return mock functions.
  - `mode="llm"` → return LLM functions.
- [ ] LLM mode functions:
  - `llm_actor()`: gọi API với ACTOR_SYSTEM prompt, context, question, reflection_memory.
  - `llm_evaluator()`: gọi API với EVALUATOR_SYSTEM prompt.
  - `llm_reflector()`: gọi API với REFLECTOR_SYSTEM prompt.
- [ ] LLM call wrapper:
  - Đo latency bằng `time.perf_counter()`.
  - Lấy token usage từ response.
  - Error handling: timeout, API error → fallback.
- [ ] Config từ env vars: `REFLEXION_MODE`, `REFLEXION_MODEL`, `OPENAI_API_KEY`, `REFLEXION_TEMPERATURE`.
- [ ] Thêm `openai` vào `requirements.txt`.

**Done khi:** `get_runtime("mock")` và `get_runtime("llm")` đều trả về callable functions.

---

### Step 2.3: Hoàn thiện Agent Logic

- [ ] Implement Reflexion loop trong `agents.py`:
  ```python
  if self.agent_type == "reflexion" and attempt_id < self.max_attempts:
      ref = reflector(example, attempt_id, judge)
      reflections.append(ref)
      trace.reflection = ref
      memory_text = f"Previous attempt {attempt_id} failed: {ref.failure_reason}\nLesson: {ref.lesson}\nNext strategy: {ref.next_strategy}"
      reflection_memory.append(memory_text)
  ```
- [ ] Xóa phụ thuộc `FAILURE_MODE_BY_QID` — dùng `judge.failure_mode`.
- [ ] Thay token/latency hardcoded bằng runtime measurement.
- [ ] Import từ runtime adapter thay vì trực tiếp từ mock_runtime.
- [ ] Thêm `format_reflection(ref: ReflectionEntry) -> str` helper.
- [ ] Ensure:
  - `record.attempts == len(record.traces)`.
  - `record.is_correct` = final evaluator score.
  - `record.reflections` chỉ có ở ReflexionAgent.
  - Không leak `gold_answer` vào actor.

**Done khi:** ReActAgent chạy 1 attempt, ReflexionAgent chạy multi-attempt với reflection.

---

### Step 2.4: Implement Adaptive Max Attempts (Bonus Extension)

- [ ] Logic:
  ```python
  def get_adaptive_attempts(difficulty: str, max_attempts: int) -> int:
      base = {"easy": 2, "medium": 3, "hard": 4}.get(difficulty, 3)
      return min(base, max_attempts)
  ```
- [ ] Opt-in flag: chỉ apply khi `--adaptive-attempts` hoặc default on.
- [ ] Không phá `max_attempts` CLI parameter.
- [ ] Ghi nhận trong report discussion.

**Done khi:** Extension hoạt động, khai báo trong report.

---

## Milestone 3 — Evaluation Quality

> **Mục tiêu:** Evaluator 2 tầng, Reflection memory ảnh hưởng thật.

### Step 3.1: Implement 2-tier Evaluator

- [ ] Tier 1 (Deterministic): `normalize_answer(predicted) == normalize_answer(gold)` → score=1, skip LLM.
- [ ] Tier 2 (LLM Semantic): gọi LLM evaluator khi Tier 1 không match.
- [ ] Failure mode inference:
  - `none` → score=1.
  - `entity_drift` → answer chứa entity khác nhưng liên quan.
  - `incomplete_multi_hop` → answer chỉ là intermediate hop.
  - `wrong_final_answer` → default cho score=0.
  - `looping` → detect repeated answers across attempts.
  - `reflection_overfit` → reflection dẫn đến answer tệ hơn.
- [ ] Mock evaluator implement đầy đủ failure mode logic.

**Done khi:** Evaluator structured, failure mode hợp lệ.

---

### Step 3.2: Verify Reflection Memory Impact

- [ ] Trace attempt 2+ phải chứa reflection memory trong input.
- [ ] ReflexionAgent accuracy ≥ ReActAgent trên dev set.
- [ ] Reflection count ≤ `attempts - 1`.
- [ ] Không có global memory leak giữa examples (memory reset mỗi example).

**Done khi:** Trace cho thấy reflection được dùng, accuracy cải thiện.

---

## Milestone 4 — Reporting & Benchmark

> **Mục tiêu:** Report đạt 100/100 autograder.

### Step 4.1: Nâng cấp Reporting

- [ ] `meta` thêm: `num_examples`, `created_at`, `model`, `reflexion_attempts`, `dataset_name`.
- [ ] `summary` chuẩn hóa keys: `num_records`, `accuracy`, `avg_attempts`, `avg_tokens`, `avg_latency_ms`.
- [ ] `failure_modes` đảm bảo ≥3 entries (thêm count=0 cho modes chưa xuất hiện).
- [ ] `examples` thêm: `question`, `token_estimate`, `latency_ms`, `traces`, `reflections`.
- [ ] `examples` có ≥20 entries (lấy đủ từ cả react + reflexion runs).
- [ ] `extensions` chỉ list extensions đã implement thật (≥2 cái).
- [ ] `discussion` viết ≥500 ký tự phân tích:
  - Reflexion cải thiện gì.
  - Failure modes phổ biến.
  - Trade-off token/latency.
  - Hạn chế.
  - Hướng cải thiện.
- [ ] Nâng cấp `report.md` format.

**Done khi:** `report.json` parse được, có đủ 6 keys, tất cả acceptance criteria pass.

---

### Step 4.2: Nâng cấp Benchmark CLI

- [ ] Thêm params: `--mode`, `--model`, `--max-examples`, `--seed`, `--temperature`, `--adaptive-attempts`.
- [ ] Đọc config từ env vars nếu CLI không truyền.
- [ ] Progress bar dùng `rich.progress`.
- [ ] Error handling per-example (try-except, log error, tiếp tục).
- [ ] Mode reflection trong report meta.

**Done khi:** CLI chạy được với tất cả params.

---

### Step 4.3: Tạo Dataset ≥120 Examples

- [ ] Tạo `data/my_test_set.json` với ≥120 QA examples.
- [ ] Phân bố:
  - 20 câu 1-hop easy.
  - 35 câu 2-hop bridge.
  - 15 câu yes/no.
  - 15 câu comparison.
  - 20 câu distractor-heavy.
  - 15 câu ambiguous entity.
  - 10 câu hard 3-hop.
- [ ] Mỗi example có: `qid`, `difficulty`, `question`, `gold_answer`, `context` (≥2 passages).
- [ ] Bao gồm edge cases: entity drift, date confusion, alias, Unicode, distractor passages.
- [ ] Validate toàn bộ dataset load được bằng `load_dataset()`.

**Done khi:** Dataset ≥120 examples, load thành công, đa dạng loại câu hỏi.

---

## Milestone 5 — Testing & Hardening

> **Mục tiêu:** Không crash trên edge cases. Hidden test ready.

### Step 5.1: Viết Unit Tests

- [ ] `test_schemas.py`:
  - `JudgeResult` validation (score=0/1, defaults).
  - `ReflectionEntry` validation.
  - `JudgeResult` với JSON thiếu field.
  - `QAExample` với difficulty lạ.
- [ ] `test_parsers.py`:
  - `extract_final_answer()` — nhiều format: có marker, không marker, multi-line, markdown.
  - `safe_parse_json()` — JSON clean, fenced, thiếu field, hoàn toàn lỗi.
  - `normalize_answer()` — articles, punctuation, Unicode, yes/no.
- [ ] `test_agents.py`:
  - ReAct: 1 attempt, không reflector.
  - Reflexion: multi-attempt, early stop khi đúng.
  - Reflexion: tất cả sai.
  - `max_attempts=1`.
  - Actor không nhận gold_answer.
- [ ] `test_reporting.py`:
  - Report có đủ 6 keys.
  - `meta.num_records` chính xác.
  - `failure_modes` ≥3.
  - `discussion` ≥250 chars.

**Done khi:** `pytest tests/ -v` all pass.

---

### Step 5.2: Hidden Test Simulation

- [ ] Test với unknown qid (không trong mock data).
- [ ] Test với missing difficulty field.
- [ ] Test với empty context `[]`.
- [ ] Test với long context (>10 passages).
- [ ] Test với invalid LLM JSON output.
- [ ] Test với actor output không có `Final answer:`.
- [ ] Test với evaluator output score ngoài range.
- [ ] Test với reflection output thiếu field.
- [ ] Test với Unicode trong question/answer.
- [ ] Test với duplicated qid trong dataset.

**Done khi:** Không crash trên bất kỳ edge case nào.

---

### Step 5.3: Final Verification Run

- [ ] Chạy mock benchmark với full dataset:
  ```bash
  python run_benchmark.py --dataset data/my_test_set.json --out-dir outputs/final_mock --mode mock --reflexion-attempts 3
  ```
- [ ] Chạy autograde:
  ```bash
  python autograde.py --report-path outputs/final_mock/report.json
  ```
- [ ] Verify output: `Auto-grade total: 100/100`.
- [ ] Verify files tồn tại:
  - `outputs/final_mock/react_runs.jsonl`
  - `outputs/final_mock/reflexion_runs.jsonl`
  - `outputs/final_mock/report.json`
  - `outputs/final_mock/report.md`
- [ ] Verify Reflexion accuracy ≥ ReAct accuracy trong report.
- [ ] Review `report.json` manually:
  - `meta.num_records >= 100`.
  - `len(examples) >= 20`.
  - `len(failure_modes) >= 3`.
  - `len(discussion) >= 250`.
  - `extensions` có ≥2 entries.

**Done khi:** 100/100 confirmed, tất cả output files hợp lệ. 🎯

---

## Quick Reference — Autograder Checklist

```
✅ report.json có key "meta"                    → 5/30 schema
✅ report.json có key "summary"                  → 5/30 schema  
✅ report.json có key "failure_modes"             → 5/30 schema
✅ report.json có key "examples"                  → 5/30 schema
✅ report.json có key "extensions"                → 5/30 schema
✅ report.json có key "discussion"                → 5/30 schema
✅ summary có "react" và "reflexion"              → 10/30 experiment
✅ meta.num_records >= 100                        → 10/30 experiment
✅ len(examples) >= 20                            → 10/30 experiment
✅ len(failure_modes) >= 3                        → 8/20 analysis
✅ len(discussion) >= 250                         → 12/20 analysis
✅ extensions ∩ recognized >= 2                   → 20/20 bonus
─────────────────────────────────────────────────────
                                          TOTAL: 100/100
```
