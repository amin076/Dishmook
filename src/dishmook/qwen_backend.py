"""Optional local Qwen backend for mathematical conjecture generation.

The heavy ML dependencies are intentionally optional. Phase-0 FakeModelBackend
continues to work without torch/transformers.
"""
from __future__ import annotations
import json
from typing import Any
from dishmook.conjectures import ConjectureBatch, ConjectureCandidate, ConjectureRequest

SYSTEM = """You are a mathematical conjecture generator, not a proof authority.
Given a verified parent theorem, propose nearby mathematical conjectures.
Prefer small meaningful mutations. Do not claim truth or proof.
Return JSON only with key 'candidates'. Each candidate must contain:
statement, mutation_kind, rationale, claimed_distance."""

class QwenConjectureBackend:
    def __init__(self, model_id: str = "Qwen/Qwen2.5-7B-Instruct", *, pipeline: Any | None = None):
        self.model_id = model_id
        if pipeline is not None:
            self._pipeline = pipeline
            return
        try:
            from transformers import pipeline as hf_pipeline
        except ImportError as exc:
            raise RuntimeError(
                "Qwen backend requires optional ML dependencies. "
                "Install Dishmook with the 'qwen' extra."
            ) from exc
        self._pipeline = hf_pipeline(
            "text-generation",
            model=model_id,
            device_map="auto",
            model_kwargs={"torch_dtype": "auto"},
        )

    def generate_conjectures(self, request: ConjectureRequest) -> ConjectureBatch:
        context = "\n".join(f"- {x}" for x in request.context_theorems[:20]) or "(none)"
        prompt = f"""Parent ID: {request.parent_id}
Parent theorem:
{request.parent_statement}

Strategy: {request.strategy}
Requested conjectures: {request.count}
Optional verified context:
{context}

Generate diverse conjectures. Prefer claimed_distance=1 unless a larger jump is
mathematically useful. Avoid merely renaming variables or wrapping the same
identity in trivial zero/one operations."""

        messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}]
        output = self._pipeline(
            messages,
            max_new_tokens=min(4096, 160 * request.count),
            do_sample=True,
            temperature=0.8,
            top_p=0.95,
        )
        text = self._extract_text(output)
        payload = self._parse_json(text)
        candidates = []
        seen = set()
        for raw in payload.get("candidates", []):
            statement = str(raw.get("statement", "")).strip()
            if not statement or statement in seen:
                continue
            seen.add(statement)
            candidates.append(ConjectureCandidate(
                parent_id=request.parent_id,
                statement=statement,
                mutation_kind=str(raw.get("mutation_kind", "unknown")),
                rationale=str(raw.get("rationale", "model-generated conjecture")),
                claimed_distance=int(raw.get("claimed_distance", 1)),
            ))
            if len(candidates) >= request.count:
                break
        return ConjectureBatch(model_id=self.model_id, candidates=candidates)

    @staticmethod
    def _extract_text(output: Any) -> str:
        item = output[0]["generated_text"]
        if isinstance(item, list):
            return str(item[-1].get("content", ""))
        return str(item)

    @staticmethod
    def _parse_json(text: str) -> dict:
        text = text.strip()
        if text.startswith("~~~"):
            text = text.strip("~")
            if text.lstrip().startswith("json"):
                text = text.lstrip()[4:].lstrip()
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end < start:
            raise ValueError("Qwen did not return a JSON object")
        return json.loads(text[start:end + 1])
