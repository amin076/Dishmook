"""Generate the first ~100 Qwen conjectures without sending anything to Gareen.

Five parents mirror the earlier ChatGPT experiment. Output is JSONL so it can
be inspected first and later consumed by a Gareen adapter.
"""
from __future__ import annotations
import argparse, json
from pathlib import Path
from dishmook.conjectures import ConjectureRequest
from dishmook.qwen_backend import QwenConjectureBackend

PARENTS = [
    ("T5_ZERO_PLUS_X", "∀x. 0 + x = x"),
    ("T6_SUCC_ADD", "∀x∀y. S(x) + y = S(x + y)"),
    ("T7_ADD_COMMUTATIVE", "∀x∀y. x + y = y + x"),
    ("T8_ADD_ASSOCIATIVE", "∀x∀y∀z. (x + y) + z = x + (y + z)"),
    ("T14_MUL_ASSOCIATIVE", "∀x∀y∀z. (x * y) * z = x * (y * z)"),
]

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    p.add_argument("--per-parent", type=int, default=20)
    p.add_argument("--output", default="outputs/qwen_conjectures_100.jsonl")
    args=p.parse_args()
    backend=QwenConjectureBackend(args.model)
    out=Path(args.output); out.parent.mkdir(parents=True, exist_ok=True)
    total=0
    with out.open("w", encoding="utf-8") as fh:
        for parent_id, statement in PARENTS:
            req=ConjectureRequest(parent_id=parent_id,parent_statement=statement,count=args.per_parent,strategy="neighborhood")
            batch=backend.generate_conjectures(req)
            for i,c in enumerate(batch.candidates,1):
                row={"parent_id":parent_id,"parent_statement":statement,"index":i,
                     "statement":c.statement,"mutation_kind":c.mutation_kind,
                     "rationale":c.rationale,"claimed_distance":c.claimed_distance,
                     "model_id":batch.model_id,"status":"unverified"}
                fh.write(json.dumps(row,ensure_ascii=False)+"\n"); total+=1
            print(f"{parent_id}: {len(batch.candidates)}")
    print(f"TOTAL={total}")
    print(f"OUTPUT={out}")

if __name__=="__main__":
    main()
