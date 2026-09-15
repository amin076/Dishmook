"""Campaign and evaluation commands, kept separate from the original CLI."""

import json
from pathlib import Path

COMMANDS={"campaign","campaign-resume","evaluate","prepare-model","select-model","gpu-preflight","archive-checkpoint","restore-checkpoint"}


def register(sub):
    launch=sub.add_parser("campaign",help="Prepare/run a staged multi-agent campaign")
    launch.add_argument("--spec",type=Path,required=True)
    launch.add_argument("--campaign-id")
    launch.add_argument("--runs-dir",type=Path,default=Path("runs/campaigns"))
    launch.add_argument("--max-tasks",type=int)
    launch.add_argument("--prepare-only",action="store_true")
    cont=sub.add_parser("campaign-resume",help="Resume a saved campaign")
    cont.add_argument("campaign_id")
    cont.add_argument("--runs-dir",type=Path,default=Path("runs/campaigns"))
    cont.add_argument("--max-tasks",type=int)
    evaluate=sub.add_parser("evaluate",help="Run/resume the known-answer experiment matrix")
    evaluate.add_argument("--model",type=Path)
    evaluate.add_argument("--output-dir",type=Path,required=True)
    evaluate.add_argument("--seeds",type=int,nargs="+",default=[7,19,41])
    evaluate.add_argument("--cases",nargs="+")
    evaluate.add_argument("--profiles",nargs="+")
    evaluate.add_argument("--output-budget",type=int,default=16384)
    evaluate.add_argument("--max-new-campaigns",type=int)
    model=sub.add_parser("prepare-model",help="Prepare an explicit pinned local model configuration")
    model.add_argument("name")
    model.add_argument("--catalog",type=Path,default=Path("configs/model_candidates.json"))
    model.add_argument("--models-dir",type=Path,default=Path("models"))
    model.add_argument("--download",action="store_true")
    model.add_argument("--output",type=Path,required=True)
    select=sub.add_parser("select-model",help="Select only from completed real GPU evidence")
    select.add_argument("results",type=Path,nargs="+")
    select.add_argument("--output",type=Path,required=True)
    sub.add_parser("gpu-preflight",help="Check local GPU availability without provisioning anything")
    archive=sub.add_parser("archive-checkpoint",help="Archive closed run databases and reports")
    archive.add_argument("directory",type=Path)
    archive.add_argument("output",type=Path)
    restore=sub.add_parser("restore-checkpoint",help="Restore a checkpoint into a new directory")
    restore.add_argument("archive",type=Path)
    restore.add_argument("destination",type=Path)


def load(path):
    with path.open("rb") as stream:
        data=stream.read(1024*1024+1)
    if len(data)>1024*1024:
        raise ValueError("Configuration is too large")
    return json.loads(data)


def dispatch(args):
    if args.command=="archive-checkpoint":
        from dishmook.checkpoints import archive_checkpoint
        return {"archive":archive_checkpoint(args.directory,args.output)},0
    if args.command=="restore-checkpoint":
        from dishmook.checkpoints import restore_checkpoint
        return {"restored":restore_checkpoint(args.archive,args.destination)},0
    if args.command in {"campaign","campaign-resume"}:
        from dishmook.campaign import CampaignSpec,metrics,prepare_campaign,resume_campaign
        if args.command=="campaign":
            spec=CampaignSpec.model_validate(load(args.spec))
            campaign_id=prepare_campaign(args.runs_dir,spec,args.campaign_id)
            if args.prepare_only:
                return {"campaign_id":campaign_id,"status":"prepared"},0
        else:
            campaign_id=args.campaign_id
        state=resume_campaign(args.runs_dir,campaign_id,max_tasks=args.max_tasks)
        return {"campaign_id":campaign_id,"status":state["status"],"metrics":metrics(state)},(1 if state["status"] in {"completed_with_failures","blocked"} else 0)
    if args.command=="evaluate":
        from dishmook.evaluation import experiment
        from dishmook.runtime_models import ModelConfig
        model=ModelConfig.model_validate(load(args.model)) if args.model else ModelConfig()
        result = experiment(args.output_dir,model,seeds=args.seeds,case_ids=args.cases,profiles=args.profiles,
                            output_budget=args.output_budget,max_new_campaigns=args.max_new_campaigns)
        return result, (1 if result["status"] == "blocked" else 0)
    if args.command=="prepare-model":
        from dishmook.provision import prepare_model
        model=prepare_model(args.name,args.catalog,args.models_dir,download=args.download)
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(model.model_dump_json(indent=2)+"\n")
        return {"model_id":model.model_id,"revision":model.revision,"config":str(args.output)},0
    if args.command=="select-model":
        from dishmook.evaluation import select_model
        report=select_model(args.results)
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(report,indent=2)+"\n")
        return report,0
    from dishmook.provision import preflight
    output=preflight()
    return output,0 if output["ready"] else 1
