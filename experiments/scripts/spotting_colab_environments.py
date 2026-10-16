"""Isolated Linux environments with durable wheel and installed-file seals."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from experiments.scripts.spotting_colab_artifacts import digest, sha
from experiments.scripts.spotting_colab_replay import replay_commands

BASE = ['pip==25.0.1', 'setuptools==75.8.0', 'wheel==0.45.1',
        'numpy==1.26.4', 'Pillow==11.1.0', 'shapely==2.0.7']


def worker_library_path(prepared):
    """Prefer sealed runtime wheels while preserving host GPU driver lookup."""
    paths = list(prepared.get('library_paths', []))
    paths.extend(os.environ.get('LD_LIBRARY_PATH', '').split(':'))
    # Empty entries mean the current directory to the linker; do not add them.
    return ':'.join(dict.fromkeys(str(path) for path in paths if path))


def run(command, **kwargs):
    return subprocess.run([str(x) for x in command], check=True, text=True, **kwargs)


def environment_snapshot(python):
    """Hash installed package files, not only their declared versions."""
    code = '''import importlib.metadata as m,json,hashlib,pathlib,sys
items={}
for d in m.distributions():
 files={}
 for f in d.files or []:
  p=pathlib.Path(d.locate_file(f))
  if p.is_file() and p.suffix not in ('.pyc',) and '.dist-info/RECORD' not in str(f):
   if str(f).startswith('..'): continue
   h=hashlib.sha256()
   with p.open('rb') as s:
    for b in iter(lambda:s.read(1048576),b''):h.update(b)
   files[str(f)]=h.hexdigest()
 items[d.metadata['Name'].lower()]={'version':d.version,'files':files}
print(json.dumps({'python':sys.version,'executable_sha256':hashlib.sha256(pathlib.Path(sys.executable).read_bytes()).hexdigest(),'packages':items},sort_keys=True))'''
    return json.loads(run([python, '-c', code], capture_output=True).stdout)


def _uv(work):
    """Bootstrap without host ensurepip; install tooling only into the target venv."""
    bootstrap = work/'bootstrap'
    python = bootstrap/'bin/python'
    if not python.exists():
        run([sys.executable, '-m', 'venv', '--without-pip', bootstrap])
    # A failed ensurepip attempt can leave bin/python but no pip/uv. Host pip's
    # --python option also supports such unseeded venvs without modifying Colab.
    probe = subprocess.run([str(python), '-m', 'uv', '--version'],
                           text=True, capture_output=True)
    if probe.returncode != 0:
        run([sys.executable, '-m', 'pip', '--python', python,
             'install', '--no-deps', 'uv==0.8.22'])
    version = run([python, '-m', 'uv', '--version'], capture_output=True).stdout.strip()
    if version != 'uv 0.8.22':
        raise ValueError('bootstrap uv identity mismatch')
    return [python, '-m', 'uv']


def prepare_environment(candidate, work_root):
    if sys.platform != 'linux':
        raise ValueError('Colab environment acquisition requires Linux; local preparation is not a T4 verification')
    work = Path(work_root).resolve()
    directory = work/'environments'/candidate['candidate_id']
    seal_path = directory/'environment-seal.json'
    python = directory/'venv/bin/python'
    requirements = BASE + candidate['packages']
    python_version = '3.10.16'
    if candidate['environment'] == 'scoring':
        python_version = '3.11.11'
    if candidate['environment'] == 'testr':
        python_version = '3.8.20'
        requirements = ['pip==24.3.1','setuptools==59.5.0','wheel==0.45.1','numpy==1.23.5',
                        'Pillow==10.4.0','shapely==2.0.7','torch==1.10.1+cu113',
                        'torchvision==0.11.2+cu113','opencv-python==4.6.0.66','scipy==1.10.1',
                        'matplotlib==3.7.5','timm==0.4.12','yacs==0.1.8','PyYAML==6.0.2']
    if candidate['environment'] == 'torch':
        requirements += ['torch==2.5.1+cu121','torchvision==0.20.1+cu121','opencv-python-headless==4.10.0.84']
    elif candidate['environment'] == 'paddle_legacy':
        requirements += ['opencv-python==4.6.0.66','opencv-contrib-python==4.6.0.66','opencv-python-headless==4.6.0.66']
        # Paddle2.6.2 does not declare native CUDA/cuDNN pip dependencies. Modern
        # Colab hosts may supply cuDNN9 only, so retain cuDNN8 in this venv.
        requirements += ['nvidia-cuda-runtime-cu11==11.8.89','nvidia-cuda-nvrtc-cu11==11.8.89',
                         'nvidia-cudnn-cu11==8.9.6.50','nvidia-cublas-cu11==11.11.3.6',
                         'nvidia-cufft-cu11==10.9.0.58','nvidia-curand-cu11==10.3.0.86',
                         'nvidia-cusolver-cu11==11.4.1.48','nvidia-cusparse-cu11==11.7.5.86',
                         'nvidia-nccl-cu11==2.20.5']
    elif candidate['environment'] == 'paddle_modern':
        requirements += ['paddlex==3.7.0']
    specification = dict(python=python_version, requirements=requirements,
                         indexes=['https://pypi.org/simple','https://download.pytorch.org/whl/cu121',
                                  'https://www.paddlepaddle.org.cn/packages/stable/cu118/'])
    cache_setting = os.environ.get('SPOTTING_CACHE_ROOT')
    cache = Path(cache_setting).resolve()/'environments'/candidate['candidate_id'] if cache_setting else None
    if cache and (cache/'environment-seal.json').exists() and not seal_path.exists():
        cached = json.loads((cache/'environment-seal.json').read_text())
        if cached['specification'] != specification:
            raise ValueError('persistent environment cache specification mismatch')
        directory.mkdir(parents=True,exist_ok=True)
        for name, expected in cached['wheel_sha256'].items():
            if sha(cache/'wheels'/name) != expected:
                raise ValueError('persistent wheel cache altered')
        resolved = directory/'requirements-resolved.txt'
        resolved.write_text(cached['resolved_requirements'])
        create, install = replay_commands(_uv(work),work,directory,python_version,
                                          cache/'wheels',resolved,requirements)
        run(create)
        run(install)
        if digest(environment_snapshot(python)) != cached['installed_digest']:
            raise ValueError('offline reconstruction differs from original environment')
        shutil.copytree(cache/'wheels',directory/'wheels',dirs_exist_ok=True)
        if candidate['environment']=='testr':
            for name in ('testr','detectron2'):
                shutil.copytree(cache/name,directory/name,dirs_exist_ok=True)
        shutil.copy2(cache/'environment-seal.json',seal_path)
    if seal_path.exists():
        seal = json.loads(seal_path.read_text())
        if seal['specification'] != specification or digest(environment_snapshot(python)) != seal['installed_digest']:
            raise ValueError('existing environment changed; do not silently repair a sealed run')
        for name, expected in seal['wheel_sha256'].items():
            if sha(directory/'wheels'/name) != expected:
                raise ValueError('wheel cache changed')
        return str(python), seal
    directory.mkdir(parents=True, exist_ok=True)
    uv = _uv(work)
    run(uv + ['venv','--python',python_version,'--seed',directory/'venv'])
    wheels = directory/'wheels'; wheels.mkdir(exist_ok=True)
    command = [python,'-m','pip','wheel','--wheel-dir',wheels] + requirements
    if candidate['environment'] == 'torch':
        command += ['--extra-index-url','https://download.pytorch.org/whl/cu121']
    if candidate['environment'] == 'testr':
        command += ['--extra-index-url','https://download.pytorch.org/whl/cu113']
    if candidate['environment'].startswith('paddle'):
        command += ['--extra-index-url','https://www.paddlepaddle.org.cn/packages/stable/cu118/']
    run(command)
    for name, expected in candidate.get('package_wheel_sha256',{}).items():
        if not (wheels/name).is_file() or sha(wheels/name)!=expected:
            raise ValueError('frozen anchor package wheel differs from original')
    # All distribution bytes are retained; installation is offline from these exact wheels.
    run([python,'-m','pip','install','--no-index','--find-links',wheels] + requirements)
    sources = {}
    if candidate['environment'] == 'testr':
        nvcc = run(['nvcc','--version'],capture_output=True).stdout
        if 'release 11.3' not in nvcc:
            raise ValueError('TESTR author stack requires CUDA toolkit11.3; incompatible Colab nvcc blocks custom-op build')
        for name, url, revision in [
            ('detectron2','https://github.com/facebookresearch/detectron2.git','d1e04565d3bec8719335b88be9e9b961bf3ec464'),
            ('testr','https://github.com/mlpc-ucsd/TESTR.git',candidate['source_revision'])]:
            checkout = directory/name
            if not checkout.exists():
                run(['git','clone',url,checkout])
                run(['git','-C',checkout,'checkout','--detach',revision])
            if run(['git','-C',checkout,'rev-parse','HEAD'],capture_output=True).stdout.strip()!=revision:
                raise ValueError('TESTR build source revision mismatch')
            run([python,'-m','pip','wheel','--no-build-isolation','--wheel-dir',wheels,checkout])
            run([python,'-m','pip','install','--no-index','--find-links',wheels,checkout.name if name=='detectron2' else 'AdelaiDet'])
            sources[name] = {'revision':revision,'files':{p.relative_to(checkout).as_posix():sha(p)
                              for p in checkout.rglob('*') if p.is_file() and '.git' not in p.parts and p.suffix in ('.py','.yaml','.cpp','.cu','.h')}}
    run([python,'-m','pip','check'])
    frozen = run([python,'-m','pip','freeze','--all'],capture_output=True).stdout
    (directory/'requirements-resolved.txt').write_text(frozen)
    hashes = {p.name:sha(p) for p in sorted(wheels.glob('*.whl'))}
    snapshot = environment_snapshot(python)
    seal = dict(specification=specification, resolved_requirements=frozen,
                wheel_sha256=hashes, installed_digest=digest(snapshot), installed=snapshot,sources=sources)
    seal_path.write_text(json.dumps(seal,sort_keys=True,indent=2))
    if cache:
        if (cache/'environment-seal.json').exists():
            raise ValueError('refuse overwrite of sealed persistent environment cache')
        cache.mkdir(parents=True,exist_ok=True)
        shutil.copytree(wheels,cache/'wheels',dirs_exist_ok=True)
        if candidate['environment']=='testr':
            for name in ('testr','detectron2'):
                shutil.copytree(directory/name,cache/name,dirs_exist_ok=True)
        shutil.copy2(seal_path,cache/'environment-seal.json')
    return str(python), seal


def prepare_scoring_environment(work_root):
    """Python3.11 retains the frozen scorer's Unicode14 normalization database."""
    python,_ = prepare_environment(dict(candidate_id='scoring',environment='scoring',
                                        packages=['matplotlib==3.10.1']),work_root)
    return python


def provision_tesseract():
    binary = shutil.which('tesseract')
    if not binary:
        # Colab's system package supplies the CPU executable only. Its exact bytes and
        # linked libraries are sealed, and every subsequent worker rechecks them.
        run(['apt-get','update','-qq'])
        run(['apt-get','install','-y','tesseract-ocr'])
        binary = shutil.which('tesseract')
    version = run([binary,'--version'],capture_output=True).stdout.splitlines()[0]
    if not version.startswith('tesseract 5.'):
        raise ValueError('Tesseract5 required')
    libraries = {}
    for line in run(['ldd',binary],capture_output=True).stdout.splitlines():
        for token in line.split():
            if token.startswith('/') and Path(token).is_file():
                libraries[str(Path(token).resolve())] = sha(token)
    return binary, dict(version=version,binary_sha256=sha(binary), libraries=libraries)
