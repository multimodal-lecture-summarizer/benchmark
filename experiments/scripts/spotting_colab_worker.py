"""Subprocess entry point. Never load model dependencies in the notebook kernel."""
import argparse
import json
import os
from pathlib import Path
import subprocess

from experiments.scripts.spotting_colab_artifacts import digest, sha
from experiments.scripts.spotting_colab_candidates import verify_prepared
from experiments.scripts.spotting_colab_adapters import load_colab_candidate


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--job',required=True)
    args = parser.parse_args()
    job = json.loads(Path(args.job).read_text(encoding='utf-8'))
    for name in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS'):
        os.environ[name] = '1'
    os.environ['DOCTR_BACKEND'] = 'torch'
    os.environ['USE_TORCH'] = '1'
    os.environ['USE_TF'] = '0'
    os.environ['PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK'] = 'True'
    candidate, prepared = job['candidate'],job['prepared']
    verify_prepared(candidate,prepared)
    predictor,runtime = load_colab_candidate(candidate,prepared)
    if candidate['adapter'] != 'tesseract':
        gpu = subprocess.run(['nvidia-smi','--query-gpu=name,driver_version,compute_cap',
                              '--format=csv,noheader'],check=True,capture_output=True,text=True).stdout.strip()
        if 'T4' not in gpu:
            raise ValueError('required T4 GPU unavailable')
        runtime['gpu_driver'] = gpu
    runtime.update(environment_digest=prepared['environment']['installed_digest'],
                   model_sha256=prepared['model_sha256'],candidate_sha256=digest(candidate),
                   worker_sources={path.name:sha(path) for path in Path(__file__).parent.glob('spotting_colab*.py')})
    from experiments.scripts.spotting_colab_execution import execute_worker_job
    execute_worker_job(job,predictor,runtime)


if __name__=='__main__':
    main()
