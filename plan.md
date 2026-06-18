# Plan — Hoàn thiện Reflexion Agent Lab (100/100)

## Tổng quan vấn đề

Codebase hiện tại là một **scaffold chưa hoàn thiện** với nhiều `TODO` và `pass`, chỉ chạy được trên mock data 8 câu hỏi. Cần hoàn thiện toàn bộ hệ thống để đạt **100/100** theo autograder.

### Trạng thái hiện tại của codebase

| File | Trạng thái | Vấn đề chính |
|---|---|---|
| [schemas.py](file:///d:/vin_lab/Day16-2A202600939-KieuDucLong/src/reflexion_lab/schemas.py) | ❌ Chưa xong | `JudgeResult` và `ReflectionEntry` đều là `pass` |
| [agents.py](file:///d:/vin_lab/Day16-2A202600939-KieuDucLong/src/reflexion_lab/agents.py) | ❌ Chưa xong | Reflexion loop chưa implement, token/latency hardcode, phụ thuộc `qid` cho failure_mode |
| [prompts.py](file:///d:/vin_lab/Day16-2A202600939-KieuDucLong/src/reflexion_lab/prompts.py) | ❌ Chưa xong | Tất cả prompt đều là `[TODO]` placeholder |
| [mock_runtime.py](file:///d:/vin_lab/Day16-2A202600939-KieuDucLong/src/reflexion_lab/mock_runtime.py) | ⚠️ Cần refactor | Hardcode `qid`, không có abstraction runtime |
| [utils.py](file:///d:/vin_lab/Day16-2A202600939-KieuDucLong/src/reflexion_lab/utils.py) | ⚠️ Thiếu | Thiếu `extract_final_answer`, `safe_parse_json`, normalize chưa xử lý articles |
| [reporting.py](file:///d:/vin_lab/Day16-2A202600939-KieuDucLong/src/reflexion_lab/reporting.py) | ⚠️ Cần nâng cấp | Thiếu fields trong `examples`, `discussion` quá ngắn, thiếu `num_examples` trong meta |
| [run_benchmark.py](file:///d:/vin_lab/Day16-2A202600939-KieuDucLong/run_benchmark.py) | ⚠️ Cần nâng cấp | Thiếu CLI params `--mode`, `--model`, `--max-examples` |
| `runtime.py` | ❌ Chưa có | Chưa có LLM runtime adapter |
| `data/my_test_set.json` | ❌ Chưa có | Cần ≥100 examples |
| `tests/` | ❌ Gần rỗng | Chỉ có 1 test cơ bản |

### Phân tích autograder — Đường đến 100/100

Dựa trên [autograde.py](file:///d:/vin_lab/Day16-2A202600939-KieuDucLong/autograde.py):

```
CORE FLOW (80 điểm):
├── Schema completeness (30đ): report.json có đủ 6 keys
│   → meta, summary, failure_modes, examples, extensions, discussion
├── Experiment completeness (30đ):
│   ├── 10đ: summary có cả "react" và "reflexion"
│   ├── 10đ: meta.num_records >= 100
│   └── 10đ: len(examples) >= 20
└── Analysis depth (20đ):
    ├── 8đ: len(failure_modes) >= 3
    └── 12đ: len(discussion) >= 250 ký tự

BONUS (20 điểm):
└── 10đ mỗi extension (tối đa 20đ) từ set recognized:
    {structured_evaluator, reflection_memory, benchmark_report_json,
     mock_mode_for_autograding, adaptive_max_attempts, ...}
```

---

## Proposed Changes

Thứ tự implement theo dependency: Schema → Utils/Parsers → Prompts → Runtime → Agents → Reporting → Benchmark → Dataset → Tests

---

### Component 1: Schema Layer

#### [MODIFY] [schemas.py](file:///d:/vin_lab/Day16-2A202600939-KieuDucLong/src/reflexion_lab/schemas.py)

**Thay đổi:**

1. **`JudgeResult`** — Thay `pass` bằng đầy đủ fields:
   - `score: int` (0 hoặc 1)
   - `reason: str = ""`
   - `missing_evidence: list[str] = Field(default_factory=list)`
   - `spurious_claims: list[str] = Field(default_factory=list)`
   - `failure_mode: str = "wrong_final_answer"` (default an toàn)
   - `confidence: float = 0.5`

2. **`ReflectionEntry`** — Thay `pass` bằng đầy đủ fields:
   - `attempt_id: int`
   - `failure_reason: str = ""`
   - `lesson: str = ""`
   - `next_strategy: str = ""`

3. **`QAExample`** — Nới `difficulty` thành `str` thay vì `Literal` cố định, thêm `default="medium"` để xử lý dataset thiếu field.

4. **`RunRecord`** — Thêm `question` vào examples output nếu cần.

> [!IMPORTANT]
> Tất cả fields phụ phải có default để tránh crash khi LLM output thiếu field.

---

### Component 2: Utils & Parsers

#### [MODIFY] [utils.py](file:///d:/vin_lab/Day16-2A202600939-KieuDucLong/src/reflexion_lab/utils.py)

**Thêm:**

1. **`normalize_answer()`** — Mở rộng: remove articles (`a`, `an`, `the`), normalize Unicode, normalize yes/no.

2. **`extract_final_answer(text: str) -> str`** — Parse actor output:
   - Tìm `Final answer:` marker (case-insensitive).
   - Nếu không có, lấy dòng cuối non-empty.
   - Strip markdown, quotes, whitespace thừa.

3. **`safe_parse_json(text: str, model_class: type) -> BaseModel`** — Parse JSON từ LLM:
   - Parse trực tiếp.
   - Nếu fail, tìm `{...}` trong text bằng regex.
   - Nếu fail, tìm trong markdown code fence.
   - Validate bằng Pydantic.
   - Nếu tất cả fail, trả fallback object.

4. **`load_dataset()`** — Thêm error handling cho missing fields, duplicate qid.

---

### Component 3: Prompt Layer

#### [MODIFY] [prompts.py](file:///d:/vin_lab/Day16-2A202600939-KieuDucLong/src/reflexion_lab/prompts.py)

**Thay tất cả `[TODO]` bằng prompt production-ready:**

1. **`ACTOR_SYSTEM`**: 
   - Hướng dẫn chỉ dùng context, multi-hop reasoning step-by-step.
   - Cẩn thận entity drift, distractor, date, alias.
   - Dùng reflection memory như advice, không override evidence.
   - Output format: `Final answer: <answer>`.

2. **`EVALUATOR_SYSTEM`**:
   - So sánh predicted vs gold answer.
   - Chấp nhận minor formatting differences.
   - Không chấp nhận partial-hop, wrong entity.
   - Output JSON `JudgeResult` schema.

3. **`REFLECTOR_SYSTEM`**:
   - Phân tích nguyên nhân sai.
   - Không bịa đáp án, không copy gold answer.
   - Tạo lesson và next_strategy cụ thể.
   - Output JSON `ReflectionEntry` schema.

---

### Component 4: Runtime Layer

#### [MODIFY] [mock_runtime.py](file:///d:/vin_lab/Day16-2A202600939-KieuDucLong/src/reflexion_lab/mock_runtime.py)

**Refactor mock runtime:**
- Loại bỏ phụ thuộc `qid` trong `FIRST_ATTEMPT_WRONG` — thay bằng logic dựa trên context/question.
- Mock actor: dùng normalized match trên context để sinh answer.
- Mock evaluator: dùng `normalize_answer()` comparison.
- Mock reflector: sinh ReflectionEntry generic dựa trên judge result.
- Thêm mock token estimation (theo số từ) và latency estimation.

#### [NEW] [runtime.py](file:///d:/vin_lab/Day16-2A202600939-KieuDucLong/src/reflexion_lab/runtime.py)

**Runtime adapter pattern:**
- `RuntimeResult` dataclass: `content`, `token_usage`, `latency_ms`.
- `get_runtime(mode: str) -> module` — factory trả về mock hoặc llm runtime.
- LLM mode: gọi OpenAI-compatible API, parse response, đo token + latency.
- Config từ env vars: `REFLEXION_MODE`, `REFLEXION_MODEL`, `OPENAI_API_KEY`, `REFLEXION_TEMPERATURE`.

---

### Component 5: Agent Layer

#### [MODIFY] [agents.py](file:///d:/vin_lab/Day16-2A202600939-KieuDucLong/src/reflexion_lab/agents.py)

**Thay đổi lớn:**

1. **Reflexion Loop** (thay TODO dòng 31-35):
   ```python
   if self.agent_type == "reflexion" and attempt_id < self.max_attempts:
       ref = reflector(example, attempt_id, judge)
       reflections.append(ref)
       trace.reflection = ref
       reflection_memory.append(format_reflection(ref))
   ```

2. **Loại bỏ phụ thuộc `qid`**:
   - Xóa `FAILURE_MODE_BY_QID.get(example.qid, ...)`.
   - Dùng `judge.failure_mode` từ evaluator thay vào.

3. **Token/Latency thật**:
   - Đo bằng `time.perf_counter()` cho mỗi call.
   - Lấy token từ runtime response hoặc estimate bằng word count.

4. **Adaptive max_attempts** (bonus extension):
   - Map difficulty → max_attempts: easy=2, medium=3, hard=4.
   - Clamp bằng CLI `max_attempts`.

5. **Tách `ReActAgent` và `ReflexionAgent`** rõ ràng hơn:
   - `ReActAgent`: luôn 1 attempt, không gọi reflector.
   - `ReflexionAgent`: multi-attempt với reflection memory.

6. **Error handling**: wrap mỗi attempt trong try-except, fallback gracefully.

---

### Component 6: Evaluation Layer

> [!NOTE]
> Evaluator 2 tầng: deterministic match trước, LLM semantic evaluator sau.

Logic trong `mock_runtime.py` (mock mode) và `runtime.py` (LLM mode):
1. `normalize_answer()` match → score=1 ngay, không tốn LLM call.
2. Nếu không match → gọi LLM evaluator → `JudgeResult`.
3. Failure mode inference từ evaluator output.

---

### Component 7: Reporting Layer

#### [MODIFY] [reporting.py](file:///d:/vin_lab/Day16-2A202600939-KieuDucLong/src/reflexion_lab/reporting.py)

**Nâng cấp `build_report()`:**

1. **`meta`** — thêm: `num_examples`, `created_at`, `model`, `reflexion_attempts`, `dataset_name`.

2. **`summary`** — đổi key names cho nhất quán:
   - `num_records`, `accuracy`, `avg_attempts`, `avg_tokens`, `avg_latency_ms`.

3. **`failure_modes`** — đảm bảo ≥3 entries, thêm count=0 cho modes chưa xuất hiện.

4. **`examples`** — thêm fields: `question`, `token_estimate`, `latency_ms`, `traces` (list), `reflections` (list).

5. **`extensions`** — chỉ khai báo extensions đã implement thật.

6. **`discussion`** — viết phân tích ≥500 ký tự:
   - Reflexion vs ReAct improvement.
   - Failure modes phổ biến.
   - Khi nào reflection giúp / không giúp.
   - Trade-off token/latency.
   - Hạn chế và hướng cải thiện.

7. **`report.md`** — nâng cấp format markdown report.

---

### Component 8: Benchmark CLI

#### [MODIFY] [run_benchmark.py](file:///d:/vin_lab/Day16-2A202600939-KieuDucLong/run_benchmark.py)

**Thêm CLI params:**
- `--mode mock|llm` (default: `mock`, cũng đọc từ env `REFLEXION_MODE`).
- `--model <model-name>` (đọc từ env `REFLEXION_MODEL`).
- `--max-examples <n>` (giới hạn số examples).
- `--seed <int>` (reproducibility).
- `--temperature <float>`.

**Error handling:** wrap mỗi example trong try-except, log lỗi nhưng tiếp tục chạy.

**Progress bar:** dùng `rich.progress` cho UX tốt hơn.

---

### Component 9: Dataset

#### [NEW] [my_test_set.json](file:///d:/vin_lab/Day16-2A202600939-KieuDucLong/data/my_test_set.json)

**Tạo ≥120 QA examples** theo phân bố:

| Loại | Số lượng | Mục đích |
|---|---|---|
| 1-hop easy | 20 | Baseline accuracy |
| 2-hop bridge | 35 | Core multi-hop |
| Yes/No | 15 | Format diversity |
| Comparison | 15 | Reasoning complexity |
| Distractor-heavy | 20 | Robustness |
| Ambiguous entity | 15 | Entity drift testing |
| Hard 3-hop | 10 | Edge case |

**Hidden test readiness:** bao gồm entity drift, partial-hop, date confusion, alias, Unicode, v.v.

---

### Component 10: Test Suite

#### [MODIFY] [test_utils.py](file:///d:/vin_lab/Day16-2A202600939-KieuDucLong/tests/test_utils.py)

#### [NEW] [test_schemas.py](file:///d:/vin_lab/Day16-2A202600939-KieuDucLong/tests/test_schemas.py)
#### [NEW] [test_agents.py](file:///d:/vin_lab/Day16-2A202600939-KieuDucLong/tests/test_agents.py)
#### [NEW] [test_parsers.py](file:///d:/vin_lab/Day16-2A202600939-KieuDucLong/tests/test_parsers.py)
#### [NEW] [test_reporting.py](file:///d:/vin_lab/Day16-2A202600939-KieuDucLong/tests/test_reporting.py)
#### [NEW] [test_edge_cases.py](file:///d:/vin_lab/Day16-2A202600939-KieuDucLong/tests/test_edge_cases.py)

**Tests bao gồm:**
- Schema validation (JudgeResult, ReflectionEntry).
- `normalize_answer()` edge cases.
- `extract_final_answer()` các format khác nhau.
- `safe_parse_json()` JSON bình thường, fenced, thiếu field, hoàn toàn lỗi.
- ReActAgent: 1 attempt, không reflector.
- ReflexionAgent: multi-attempt, early stop, all wrong.
- `max_attempts=1` edge case.
- Report có đủ 6 keys.
- Hidden test simulation: unknown qid, missing difficulty, empty context, v.v.

---

## Verification Plan

### Automated Tests

```bash
# Unit tests
python -m pytest tests/ -v

# Mock benchmark (8 samples)
python run_benchmark.py --dataset data/hotpot_mini.json --out-dir outputs/smoke_test --mode mock

# Full benchmark (≥100 samples)
python run_benchmark.py --dataset data/my_test_set.json --out-dir outputs/final_mock --mode mock --reflexion-attempts 3

# Autograde
python autograde.py --report-path outputs/final_mock/report.json
# Expected: Auto-grade total: 100/100
```

### Manual Verification
- Kiểm tra `report.json` có đủ 6 top-level keys.
- Kiểm tra `meta.num_records >= 100`.
- Kiểm tra `examples` có ≥20 entries với đầy đủ traces.
- Kiểm tra `failure_modes` có ≥3 entries.
- Kiểm tra `discussion` ≥250 ký tự.
- Kiểm tra Reflexion accuracy ≥ ReAct accuracy.
- Kiểm tra reflection memory xuất hiện trong traces.

---

## Open Questions

> [!IMPORTANT]
> **LLM Mode**: Bạn có API key (OpenAI/Gemini/Ollama) để test LLM mode không? Nếu không, sẽ focus vào mock mode đạt 100/100 trước. LLM mode sẽ được implement sẵn nhưng test sau khi có key.

> [!IMPORTANT]
> **Dataset**: Bạn muốn tôi tạo dataset 120+ câu hỏi multi-hop bằng tiếng Anh (phong cách HotpotQA) hay có dataset riêng muốn dùng?

> [!NOTE]
> **Adaptive max_attempts**: PRD yêu cầu extension này. Tôi sẽ implement dạng opt-in (flag `--adaptive-attempts`) để không phá default behavior.
