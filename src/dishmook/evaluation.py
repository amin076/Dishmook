"""Known-answer scoring, resumable experiment matrices and cautious paired comparisons."""

import ast
from collections import defaultdict
import csv
import hashlib
from importlib.resources import files
import json
import math
from pathlib import Path
import random
import statistics

from dishmook.campaign import CampaignSpec, final_result, metrics, prepare_campaign, resume_campaign
from dishmook.domain import Problem
from dishmook.runtime import canonical, now
from dishmook.runtime_models import ModelConfig

PROFILES=[("single",1,False),("self_reflection",1,True),("agents_5",5,False),
          ("agents_10",10,False),("agents_20",20,False),("agents_50",50,False)]


def cases():
    return json.loads(files("dishmook").joinpath("data/known_answer.json").read_text())


def assess(case, candidate):
    answer=(candidate or {}).get("answer")
    passed=False
    if case["validator"]=="numeric":
        try:
            if isinstance(answer,bool) or answer is None:
                raise ValueError
            value=float(answer)
            passed=math.isfinite(value) and math.isclose(value,float(case["expected"]),rel_tol=case.get("rtol",1e-6),abs_tol=1e-9)
        except (ValueError,TypeError,OverflowError):
            pass
    elif case["validator"]=="exact":
        passed=isinstance(answer,str) and answer.strip().lower()==case["expected"].strip().lower()
    elif case["validator"]=="python_ast":
        # Parse a bounded string; never execute generated code.
        if isinstance(answer,str) and len(answer)<=2048:
            try:
                passed=ast.dump(ast.parse(answer))==ast.dump(ast.parse(case["expected"]))
            except (SyntaxError,ValueError,RecursionError):
                pass
    else:
        raise ValueError("Unknown independent validator")
    return {"passed":passed,"validator":case["validator"],"case_id":case["problem"]["problem_id"],
            "scope":"answer field only; reasoning and citations are not independently verified"}


def paired_interval(records, profile, baseline="single", seed=7):
    pairs=defaultdict(dict)
    for row in records:
        if row["score"] is not None:
            pairs[(row["case_id"],row["seed"])][row["profile"]]=row["score"]
    clusters=defaultdict(list)
    for (case_id,_), values in pairs.items():
        if profile in values and baseline in values:
            clusters[case_id].append(values[profile]-values[baseline])
    values=[statistics.mean(group) for group in clusters.values()]
    if len(values)<2:
        return {"mean_difference":None,"ci95":None,"case_count":len(values),"status":"insufficient_paired_cases"}
    rng=random.Random(seed)
    draws=sorted(statistics.mean(rng.choices(values,k=len(values))) for _ in range(1000))
    return {"mean_difference":statistics.mean(values),"ci95":[draws[24],draws[974]],
            "case_count":len(values),"status":"exploratory_case_cluster_bootstrap"}


def _experiment(root, model=None, *, seeds=(7,19,41), case_ids=None, profiles=None,
               output_budget=16384, max_new_campaigns=None):
    root=Path(root)
    root.mkdir(parents=True,exist_ok=True)
    model=model or ModelConfig()
    chosen=[c for c in cases() if case_ids is None or c["problem"]["problem_id"] in case_ids]
    if not chosen or (case_ids is not None and len(chosen)!=len(set(case_ids))):
        raise ValueError("Unknown or empty case selection")
    active=[p for p in PROFILES if profiles is None or p[0] in profiles]
    if not active or (profiles is not None and len(active)!=len(set(profiles))):
        raise ValueError("Unknown experiment profile")
    seeds=list(seeds)
    if not seeds or len(set(seeds))!=len(seeds) or any(isinstance(s,bool) or not isinstance(s,int) or not 0<=s<2**32 for s in seeds):
        raise ValueError("Use distinct valid seeds")
    protocol={"version":2,"model":model.model_dump(),"seeds":seeds,"cases":chosen,"profiles":active,
              "total_output_tokens":output_budget,"total_input_tokens":1048576,"max_rounds":0}
    protocol_path=root/"experiment.json"
    if protocol_path.exists():
        if canonical(json.loads(protocol_path.read_text()))!=canonical(protocol):
            raise ValueError("Experiment directory already belongs to a different protocol")
    else:
        protocol_path.write_text(json.dumps(protocol,indent=2)+"\n")
    records=[]
    newly_run=0
    stopped=False
    blocked=False
    for case in chosen:
        for seed in seeds:
            for name,count,reflection in active:
                if blocked:
                    continue
                run_id="exp-"+hashlib.sha256(f"{case['problem']['problem_id']}:{seed}:{name}".encode()).hexdigest()[:24]
                folder=root/"campaigns"/run_id
                if not folder.exists():
                    if max_new_campaigns is not None and newly_run>=max_new_campaigns:
                        stopped=True
                        continue
                    spec=CampaignSpec(problem=Problem.model_validate(case["problem"]),model=model,agent_count=count,
                                      self_reflection=reflection,seed=seed,total_output_tokens=output_budget)
                    prepare_campaign(root/"campaigns",spec,run_id)
                    newly_run+=1
                state=resume_campaign(root/"campaigns",run_id)
                final=final_result(state)
                checked=assess(case,(final or {}).get("candidate"))
                m=metrics(state)
                records.append({"case_id":case["problem"]["problem_id"],"seed":seed,"profile":name,
                                "campaign_id":run_id,"status":state["status"],
                                "score":int(checked["passed"]) if model.backend!="fake" else None,
                                "schema_success":bool(final and final.get("claim")),"assessment":checked,**m})
                if state["status"]=="blocked":
                    blocked=True
    failures=sum(r["status"] != "completed" for r in records)
    summary={"status":"blocked" if blocked else "partial" if stopped else "completed_with_failures" if failures else "completed",
             "failed_campaigns":failures,"generated_at":now(),"backend":model.backend,
             "model":model.model_dump(),"dataset_sha256":hashlib.sha256(canonical(chosen).encode()).hexdigest(),
             "protocol_sha256":hashlib.sha256(canonical(protocol).encode()).hexdigest(),"campaign_count":len(records),
             "scientific_conclusion":"No scientific inference from Fake Backend." if model.backend=="fake" else
               "Exploratory known-answer evaluation; no general scientific superiority established.",
             "comparisons":{p[0]:paired_interval(records,p[0]) for p in active if p[0]!="single"},"profiles":{}}
    for name,_,_ in active:
        rows=[r for r in records if r["profile"]==name]
        summary["profiles"][name]={"campaigns":len(rows),"accuracy":statistics.mean(r["score"] for r in rows) if rows and model.backend!="fake" else None,
                                   "schema_success_rate":statistics.mean(r["schema_success"] for r in rows) if rows else None,
                                   "accepted_answer_accuracy":statistics.mean(r["score"] for r in rows if r["schema_success"]) if model.backend!="fake" and any(r["schema_success"] for r in rows) else None,
                                   "charged_output_tokens":sum(r["charged_output_tokens"] for r in rows)}
    (root/"results.json").write_text(json.dumps({"summary":summary,"records":records},indent=2)+"\n")
    fields=["case_id","seed","profile","status","score","schema_success","charged_output_tokens","known_input_tokens","known_output_tokens","wall_seconds","peak_vram_bytes"]
    with (root/"results.csv").open("w",newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=fields,extrasaction="ignore");writer.writeheader();writer.writerows(records)
    (root/"report.md").write_text("# Dishmook evaluation\n\n"+summary["scientific_conclusion"]+
        "\n\nAll profiles have the same total input/output ceilings; actual tokens and runtime differ. "
        "Bootstrap intervals cluster by case, averaging seeds within each case. This small original test set "
        "is not a comprehensive benchmark. Code answers are compared as ASTs without execution.\n\n"+
        "```json\n"+json.dumps(summary["profiles"],indent=2)+"\n```\n")
    return summary


def experiment(root, model=None, **kwargs):
    from dishmook.storage import run_lock
    root=Path(root)
    root.mkdir(parents=True,exist_ok=True)
    with run_lock(root):
        return _experiment(root,model,**kwargs)


def select_model(result_paths):
    candidates=[]
    common=None
    for path in result_paths:
        data=json.loads(Path(path).read_text()); summary=data["summary"]; rows=data["records"]
        model=summary["model"]
        if summary["status"]!="completed" or model["backend"]!="huggingface" or model["device"]!="cuda" or model["quantization"]!="nf4":
            raise ValueError("Selection requires completed real CUDA/NF4 evidence for every candidate")
        protocol=json.loads((Path(path).parent/"experiment.json").read_text())
        signature=canonical({k:v for k,v in protocol.items() if k!="model"})
        if common is not None and signature!=common:
            raise ValueError("Model benchmarks must use the same cases, seeds and budgets")
        common=signature
        if not rows or any(r["peak_vram_bytes"] is None or r["peak_vram_bytes"]>16*1024**3 for r in rows):
            raise ValueError("Missing or over-16-GiB VRAM evidence")
        candidates.append({"model":model,"accuracy":statistics.mean(r["score"] for r in rows),
                           "wall_seconds":sum(r["wall_seconds"] for r in rows),"source":str(path)})
    if len({c["model"]["model_id"] for c in candidates})<2:
        raise ValueError("At least two distinct real models are required")
    ranked=sorted(candidates,key=lambda c:(-c["accuracy"],c["wall_seconds"]))
    winner=ranked[0] if ranked[0]["accuracy"]>0 and ranked[0]["accuracy"]>ranked[1]["accuracy"] else None
    return {"status":"provisional_selection" if winner else "inconclusive", "winner":winner,"candidates":ranked,
            "limitation":"Empirical choice on this fixed small benchmark, not a claim of best scientific model."}
