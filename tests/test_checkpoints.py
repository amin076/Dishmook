import zipfile

import pytest

from dishmook.campaign import CampaignSpec,prepare_campaign,resume_campaign,metrics
from dishmook.checkpoints import archive_checkpoint,restore_checkpoint
from dishmook.domain import Problem
from dishmook.storage import run_lock


def test_portable_campaign_restore(tmp_path):
    root=tmp_path/"source"
    spec=CampaignSpec(problem=Problem(problem_id="p",title="T",statement="S"),agent_count=10)
    run_id=prepare_campaign(root,spec)
    before=resume_campaign(root,run_id,max_tasks=3)
    archive=archive_checkpoint(root,tmp_path/"checkpoint.zip")
    destination=tmp_path/"restored"
    restore_checkpoint(archive,destination)
    result=resume_campaign(destination,run_id)
    assert metrics(result)["completed_tasks"]==10
    assert result["jobs"][:3]==before["jobs"][:3]


def test_live_checkpoint_cannot_be_archived(tmp_path):
    root=tmp_path/"source"
    run_id=prepare_campaign(root,CampaignSpec(problem=Problem(problem_id="p",title="T",statement="S"),agent_count=1))
    with run_lock(root/run_id):
        with pytest.raises(ValueError,match="active"):
            archive_checkpoint(root,tmp_path/"blocked.zip")


@pytest.mark.parametrize("name",["../outside","/absolute","C:/outside","a\\..\\outside"])
def test_unsafe_archive_is_rejected(tmp_path,name):
    archive=tmp_path/"bad.zip"
    with zipfile.ZipFile(archive,"w") as z:
        z.writestr(name,"bad")
        z.writestr("state.sqlite3","fake")
    with pytest.raises(ValueError,match="Unsafe"):
        restore_checkpoint(archive,tmp_path/"output")
    assert not (tmp_path/"output").exists()
