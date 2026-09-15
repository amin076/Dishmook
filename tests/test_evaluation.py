import json

import pytest

from dishmook.evaluation import assess,cases,experiment,paired_interval,select_model


def test_independent_answer_checks():
    for case in cases():
        assert assess(case,{"answer":case["expected"]})["passed"]
        assert not assess(case,{"answer":"not an answer"})["passed"]
        assert not assess(case,{})["passed"]
    numeric=next(c for c in cases() if c["validator"]=="numeric")
    for bad in [True,float("nan"),float("inf")]:
        assert not assess(numeric,{"answer":bad})["passed"]


def test_code_validator_does_not_execute(tmp_path):
    case=next(c for c in cases() if c["validator"]=="python_ast")
    target=tmp_path/"unsafe"
    answer=f"open({str(target)!r},'w').write('unsafe')"
    assert not assess(case,{"answer":answer})["passed"]
    assert not target.exists()


def test_case_cluster_bootstrap_and_pairing():
    records=[]
    for c in ["a","b","c"]:
        for seed in [1,2]:
            records.extend([{"case_id":c,"seed":seed,"profile":"single","score":0},
                            {"case_id":c,"seed":seed,"profile":"agents_5","score":1}])
    result=paired_interval(records,"agents_5")
    assert result["case_count"]==3
    assert result["mean_difference"]==1
    assert result["ci95"]==[1,1]
    assert paired_interval([],"agents_5")["ci95"] is None


def test_fake_comparison_does_not_claim_scientific_accuracy(tmp_path):
    summary=experiment(tmp_path,seeds=[7],case_ids=["fall","energy"],profiles=["single","agents_5"],max_new_campaigns=1)
    assert summary["status"]=="partial"
    final=experiment(tmp_path,seeds=[7],case_ids=["fall","energy"],profiles=["single","agents_5"])
    assert final["campaign_count"]==4
    assert final["profiles"]["agents_5"]["accuracy"] is None
    assert final["comparisons"]["agents_5"]["ci95"] is None
    data=json.loads((tmp_path/"experiment.json").read_text())
    # Expected answers are evaluator metadata, never included in agent problem documents.
    import sqlite3
    child=next((tmp_path/"campaigns").glob("*/tasks/task-000/state.sqlite3"))
    with sqlite3.connect(child) as db:
        state=json.loads(db.execute("SELECT payload FROM state").fetchone()[0])
        assert "expected" not in state["spec"]["problem"]
    with pytest.raises(ValueError):
        select_model([tmp_path/"results.json",tmp_path/"results.json"])
    with pytest.raises(ValueError):
        experiment(tmp_path,seeds=[8],case_ids=["fall","energy"],profiles=["single","agents_5"])
