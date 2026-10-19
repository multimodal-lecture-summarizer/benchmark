"""Fingerprint effective module/native binaries, including overlapping cv2 wheels."""
import base64
import hashlib
from importlib import metadata, util
from pathlib import Path
import sys

from experiments.scripts.spotting_candidate_contract import canonical_sha, sha
from experiments.scripts.spotting_runtime_binding import VENV, require


def installed_binary_snapshot():
    """Read binary bytes before importing either engine; compare again after load."""
    files={}
    for name in ('numpy','scipy','PIL','cv2','torch','torchvision','paddle'):
        spec=util.find_spec(name)
        require(spec is not None and spec.origin, 'missing locked backend: '+name)
        root=Path(spec.origin).resolve().parent
        require(root.is_relative_to(VENV.resolve()), 'backend outside isolated venv: '+name)
        for path in sorted(root.rglob('*')):
            if path.is_file() and path.suffix.lower() in ('.pyd','.dll'):
                files[path.relative_to(VENV).as_posix()]=sha(path)
    return files


def interpreter_identity():
    paths=[Path(sys.executable),Path(sys.base_prefix)/'python.exe',Path(sys.base_prefix)/'python311.dll']
    require(all(p.is_file() for p in paths), 'interpreter binary missing')
    import platform
    return dict(python=sys.version,platform=platform.platform(),prefix=sys.prefix,base_prefix=sys.base_prefix,
                binaries={str(p):sha(p) for p in paths})


def native_fingerprint():
    packages=['numpy','scipy','PIL','cv2','torch','torchvision','paddle']
    roots={}
    for name in packages:
        module=sys.modules.get(name)
        if module is None:
            continue
        path=Path(module.__file__).resolve()
        require(path.is_relative_to(VENV.resolve()), 'native dependency outside isolated venv: '+name)
        roots[name]=path.parent
    files={}
    for root in set(roots.values()):
        for path in sorted(root.rglob('*')):
            if path.is_file() and path.suffix.lower() in ('.pyd','.dll'):
                files[path.relative_to(VENV).as_posix()]=sha(path)
    require(files, 'no effective native binaries found')
    import cv2
    binary=next(p for p in roots['cv2'].glob('*.pyd'))
    encoded=base64.urlsafe_b64encode(bytes.fromhex(sha(binary))).decode().rstrip('=')
    providers={}
    for package in ('opencv-python','opencv-python-headless','opencv-contrib-python'):
        distribution=metadata.distribution(package)
        recorded=[p for p in distribution.files if str(p).replace('\\','/')=='cv2/'+binary.name]
        providers[package]=bool(recorded and recorded[0].hash and recorded[0].hash.mode=='sha256' and recorded[0].hash.value==encoded)
    require(any(providers.values()), 'effective cv2 binary matches no locked wheel RECORD')
    modules={}
    for name in packages:
        if name in sys.modules:
            module=sys.modules[name]
            modules[name]=dict(path=str(Path(module.__file__).resolve()),version=getattr(module,'__version__',None))
    return dict(files=files,file_count=len(files),fingerprint_sha256=canonical_sha(files),modules=modules,
        cv2=dict(version=cv2.__version__,binary=str(binary),binary_sha256=sha(binary),record_matches=providers,
                 build_info_sha256=hashlib.sha256(cv2.getBuildInformation().encode()).hexdigest()),
        limit='hashes installed native files for effective imported package roots; not attestation of every DLL loaded by Windows')
