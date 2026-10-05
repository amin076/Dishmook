import json
from dishmook.conjectures import ConjectureRequest
from dishmook.qwen_backend import QwenConjectureBackend

class StubPipeline:
    def __call__(self, *args, **kwargs):
        payload = {"candidates": [
            {"statement": "forall x y, x + y = y + x", "mutation_kind": "commute", "rationale": "swap operands", "claimed_distance": 1},
            {"statement": "forall x y, x + y = y + x", "mutation_kind": "duplicate", "rationale": "duplicate", "claimed_distance": 1},
            {"statement": "forall x y z, (x+y)+z = x+(y+z)", "mutation_kind": "generalize", "rationale": "add structure", "claimed_distance": 1}
        ]}
        return [{"generated_text": [{"role": "assistant", "content": json.dumps(payload)}]}]

def test_qwen_backend_parses_and_deduplicates_candidates():
    backend = QwenConjectureBackend("stub-qwen", pipeline=StubPipeline())
    batch = backend.generate_conjectures(ConjectureRequest(parent_id="T1", parent_statement="forall x, x+0=x", count=5))
    assert batch.status == "unverified"
    assert len(batch.candidates) == 2
    assert all(x.parent_id == "T1" for x in batch.candidates)
