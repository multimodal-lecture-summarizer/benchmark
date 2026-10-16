"""Acquire declared artifacts without accepting changed bytes or unsafe archives."""
import hashlib
import json
from pathlib import Path
import shutil
import tarfile
import urllib.request
import zipfile


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':')).encode()).hexdigest()


def acquire(spec, root):
    """A missing expected digest is a blocking condition, never trust on first use."""
    if not spec.get('sha256'):
        raise ValueError('artifact is not locked: ' + spec['path'])
    root = Path(root).resolve()
    path = (root / spec['path']).resolve()
    if not path.is_relative_to(root):
        raise ValueError('artifact escapes root')
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.partial')
        with urllib.request.urlopen(spec['url'], timeout=120) as source, temporary.open('wb') as target:
            shutil.copyfileobj(source, target)
        if sha(temporary) != spec['sha256']:
            temporary.unlink()
            raise ValueError('download digest mismatch: ' + spec['path'])
        temporary.replace(path)
    if sha(path) != spec['sha256']:
        raise ValueError('artifact digest mismatch: ' + spec['path'])
    return path


def extract(archive, destination):
    """Extract regular files only; links and traversal are rejected before writes."""
    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as bundle:
            for member in bundle.infolist():
                target = (destination / member.filename).resolve()
                if not target.is_relative_to(destination) or (member.external_attr >> 16) & 0o170000 == 0o120000:
                    raise ValueError('unsafe ZIP member')
            bundle.extractall(destination)
    else:
        with tarfile.open(archive) as bundle:
            members = bundle.getmembers()
            for member in members:
                if not (destination / member.name).resolve().is_relative_to(destination) or not (member.isfile() or member.isdir()):
                    raise ValueError('unsafe TAR member')
            bundle.extractall(destination, members=members)


def verify_files(root, expected):
    root = Path(root).resolve()
    for relative, wanted in expected.items():
        target = (root / relative).resolve()
        if not target.is_relative_to(root) or not target.is_file() or sha(target) != wanted:
            raise ValueError('model/source identity mismatch: ' + relative)
