"""Portable, closed-run archives; validate paths before extraction."""

from contextlib import ExitStack
from pathlib import Path,PurePosixPath
import os
import shutil
import stat
import tempfile
import zipfile

from dishmook.storage import run_lock


def archive_checkpoint(directory, output):
    directory=Path(directory).resolve(); output=Path(output).resolve()
    if directory==output or directory in output.parents:
        raise ValueError("Write the archive outside the checkpoint directory")
    if not list(directory.rglob("state.sqlite3")):
        raise ValueError("No checkpoint database found")
    output.parent.mkdir(parents=True,exist_ok=True)
    with ExitStack() as stack:
        # Lock controllers in outer-before-inner order; never archive a changing run.
        lock_dirs={directory,*(p.parent for p in directory.rglob("run.lock"))}
        for folder in sorted(lock_dirs,key=lambda p:(len(p.parts),str(p))):
            stack.enter_context(run_lock(folder))
        fd,temp=tempfile.mkstemp(dir=output.parent,suffix=".zip")
        os.close(fd)
        try:
            with zipfile.ZipFile(temp,"w",compression=zipfile.ZIP_DEFLATED) as z:
                for path in sorted(directory.rglob("*")):
                    if path.is_symlink():
                        raise ValueError("Checkpoint archives do not follow symlinks")
                    if path.is_file() and path.name!="run.lock":
                        z.write(path,path.relative_to(directory).as_posix())
            os.replace(temp,output)
        finally:
            if Path(temp).exists(): Path(temp).unlink()
    return str(output)


def restore_checkpoint(archive,destination):
    destination=Path(destination).resolve()
    if destination.exists():
        raise ValueError("Restore into a new directory")
    destination.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(archive) as z:
        infos=z.infolist()
        names=set()
        if sum(i.file_size for i in infos)>2*1024**3:
            raise ValueError("Checkpoint archive exceeds the 2-GiB restoration limit")
        for info in infos:
            name=PurePosixPath(info.filename)
            if name.is_absolute() or ".." in name.parts or "\\" in info.filename or ":" in info.filename or info.filename in names:
                raise ValueError("Unsafe archive member path")
            if stat.S_ISLNK(info.external_attr>>16):
                raise ValueError("Symlink archive member is not allowed")
            names.add(info.filename)
        if not any(PurePosixPath(n).name=="state.sqlite3" for n in names):
            raise ValueError("Archive has no run checkpoint")
        temp=Path(tempfile.mkdtemp(dir=destination.parent))
        try:
            z.extractall(temp)
            os.replace(temp,destination)
        finally:
            if temp.exists(): shutil.rmtree(temp)
    return str(destination)
