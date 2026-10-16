"""Rebind the authoritative v2 notebook to its current portable bundle."""
import ast
import json
import re
from experiments.scripts.spotting_colab_bundle import ROOT, build as build_bundle
from experiments.scripts.spotting_colab_state import sha

REGISTRY = 'experiments/registry/datasets/iiit-cvid-spotting-colab-t4-candidates-261015-v2.json'
NOTEBOOK = ROOT/'experiments/notebooks/iiit-cvid-spotting-colab-t4-v2.ipynb'
BUNDLE = ROOT/'experiments/outputs/iiit-cvid-spotting-colab-t4-inputs-v2.zip'


def build():
    notebook = json.loads(NOTEBOOK.read_text(encoding='utf-8'))
    bundle = build_bundle(BUNDLE)
    replaced = 0
    for cell in notebook['cells']:
        source = ''.join(cell['source'])
        if cell['cell_type']=='code':
            source,count = re.subn(r"EXPECTED_BUNDLE_SHA256 = '[a-f0-9]{64}'", "EXPECTED_BUNDLE_SHA256 = '"+bundle['sha256']+"'",source)
            replaced += count
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='download_script' for t in node.targets):
                    ast.parse(ast.literal_eval(node.value))
            cell.update(execution_count=None,outputs=[])
        cell['source'] = source.splitlines(True)
    if replaced!=1:
        raise ValueError('v2 notebook must bind exactly one bundle hash')
    notebook['metadata']['colab']['name'] = NOTEBOOK.name
    NOTEBOOK.write_text(json.dumps(notebook,ensure_ascii=False,indent=1)+'\n',encoding='utf-8')
    result = dict(notebook=str(NOTEBOOK),notebook_sha256=sha(NOTEBOOK),bundle=bundle,
                  full_comparison_executed=False,required_candidates=6,
                  pgnet_train_qualification='audited_passed_T4_9_frames',testr_included=False)
    print(json.dumps(result,indent=2))
    return result


if __name__=='__main__':
    build()
