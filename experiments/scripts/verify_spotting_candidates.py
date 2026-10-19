"""Verify candidate freeze and optionally load both models, without frame inference."""
import argparse
import json
from pathlib import Path
import platform
import subprocess
import sys

from experiments.scripts.spotting_candidate_contract import (
    ROOT, REGISTRY, RUNTIME_LOCK, configure_environment, load_registry, sha, verify_candidate,
)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--load-models',action='store_true')
    parser.add_argument('--receipt',type=Path,default=ROOT/'experiments/outputs/spotting-candidates-261014/verification.json')
    args=parser.parse_args()
    registry=load_registry()
    configure_environment(registry)
    rows=[]
    for candidate in registry['candidates']:
        identity=verify_candidate(candidate,registry,installed=args.load_models)
        if args.load_models:
            from experiments.scripts.spotting_candidate_adapters import load_candidate
            _,runtime=load_candidate(candidate)
            identity['loaded_runtime']=runtime
        rows.append(identity)
        print('Verified',candidate['candidate_id'],flush=True)
    receipt=dict(schema='spotting_candidate_verification_v1',registry_sha256=sha(REGISTRY),
                 candidate_count=len(rows),candidates=rows,model_loading_verified=args.load_models,
                 frame_inference_executed=False,python=platform.python_version(),platform=platform.platform(),
                 runtime_lock_sha256=sha(RUNTIME_LOCK),
                 implementation_sha256={n:sha(Path(__file__).with_name(n)) for n in
                  ('spotting_candidate_contract.py','spotting_candidate_adapters.py','verify_spotting_candidates.py')})
    if args.load_models:
        receipt['installed_packages']=subprocess.check_output([sys.executable,'-m','pip','freeze'],text=True).splitlines()
    args.receipt.parent.mkdir(parents=True,exist_ok=True)
    # This operational check receipt is separate from immutable candidate registry.
    args.receipt.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print('Frame inference executed: False')


if __name__=='__main__':
    main()
