from __future__ import annotations
import json
import re
import unicodedata
from pathlib import Path
from typing import Iterable, TypeVar, Type
from pydantic import BaseModel

from .schemas import QAExample, RunRecord

T = TypeVar("T", bound=BaseModel)

def normalize_answer(text: str) -> str:
    if not isinstance(text, str):
        text = str(text)
    # Unicode normalize
    text = unicodedata.normalize("NFD", text).encode("ascii", "ignore").decode("utf-8")
    text = text.strip().lower()
    # Remove articles
    text = re.sub(r"\b(a|an|the)\b", " ", text)
    # Remove punctuation
    text = re.sub(r"[^a-z0-9\s]", "", text)
    # Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()
    
    if text in ["yes", "y", "true"]:
        return "yes"
    if text in ["no", "n", "false"]:
        return "no"
        
    return text

def extract_final_answer(text: str) -> str:
    # Look for marker
    match = re.search(r"(?i)final\s*answer\s*:(.*)", text, re.DOTALL)
    if match:
        answer_block = match.group(1).strip()
        lines = [line.strip() for line in answer_block.split("\n") if line.strip()]
        if lines:
            ans = lines[0]
            ans = re.sub(r"^[\*\-\>\s]+", "", ans) # Strip bullet points
            ans = ans.strip("\"'")
            return ans
    
    # Fallback to last non-empty line
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    if lines:
        ans = lines[-1]
        ans = re.sub(r"^[\*\-\>\s]+", "", ans)
        ans = ans.strip("\"'")
        return ans
    return ""

def safe_parse_json(text: str, model_class: Type[T], fallback_kwargs: dict) -> T:
    try:
        data = json.loads(text)
        # Coerce failure_mode if needed for JudgeResult
        if "failure_mode" in data:
            valid_modes = ["none", "entity_drift", "incomplete_multi_hop", "wrong_final_answer", "looping", "reflection_overfit"]
            if data["failure_mode"] not in valid_modes:
                data["failure_mode"] = "wrong_final_answer"
        if "score" in data:
            if data["score"] not in [0, 1]:
                data["score"] = 0
        return model_class.model_validate(data)
    except Exception:
        pass
        
    # Try finding fenced json
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(1))
            if "failure_mode" in data:
                valid_modes = ["none", "entity_drift", "incomplete_multi_hop", "wrong_final_answer", "looping", "reflection_overfit"]
                if data["failure_mode"] not in valid_modes:
                    data["failure_mode"] = "wrong_final_answer"
            if "score" in data:
                if data["score"] not in [0, 1]:
                    data["score"] = 0
            return model_class.model_validate(data)
        except Exception:
            pass
            
    # Try finding any curly braces
    match = re.search(r"\{.*?\}", text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(0))
            if "failure_mode" in data:
                valid_modes = ["none", "entity_drift", "incomplete_multi_hop", "wrong_final_answer", "looping", "reflection_overfit"]
                if data["failure_mode"] not in valid_modes:
                    data["failure_mode"] = "wrong_final_answer"
            if "score" in data:
                if data["score"] not in [0, 1]:
                    data["score"] = 0
            return model_class.model_validate(data)
        except Exception:
            pass
            
    return model_class(**fallback_kwargs)

def load_dataset(path: str | Path) -> list[QAExample]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Dataset path does not exist: {p}")
        
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        raise ValueError(f"Invalid JSON file: {p}")
        
    examples = []
    seen_qids = set()
    for item in raw:
        if "qid" not in item:
            continue # skip invalid item
        
        # Deduplicate qids
        original_qid = item["qid"]
        qid = original_qid
        counter = 1
        while qid in seen_qids:
            qid = f"{original_qid}_{counter}"
            counter += 1
            
        item["qid"] = qid
        seen_qids.add(qid)
            
        if "difficulty" not in item:
            item["difficulty"] = "medium"
            
        try:
            examples.append(QAExample.model_validate(item))
        except Exception:
            pass # skip invalid items
            
    return examples

def save_jsonl(path: str | Path, records: Iterable[RunRecord]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(record.model_dump_json() + "\n")
