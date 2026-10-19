"""Seal candidate settings from pinned releases, without reading spotting outcomes."""
import ast
import json
from pathlib import Path
import zipfile

from experiments.scripts.spotting_candidate_contract import ROOT, ARTIFACTS, REGISTRY, canonical_sha, sha

EASY_WHEEL_SHA='5be12f9b0e595d443c9c3d10b0542074b50f0ec2d98b141a109cd961fd1c177c'
PADDLE_WHEEL_SHA='05bfda60570b1cbeaf26907e4f6a7b26ce532b4058e2dd04c161e65b9103f3a6'


def package_identity(name,version,expected):
    filename=f'{name}-{version}-py3-none-any.whl'
    if sha(ARTIFACTS/filename)!=expected:
        raise ValueError('wheel identity mismatch')
    from hashlib import sha256
    with zipfile.ZipFile(ARTIFACTS/filename) as z:
        files={n:sha256(z.read(n)).hexdigest() for n in z.namelist() if n.startswith(name+'/') and
               (n.endswith('.py') or n.endswith(('character/en_char.txt','ppocr/utils/en_dict.txt')))}
    return dict(name=name,version=version,wheel_filename=filename,wheel_sha256=expected,file_sha256=files)


def easy_defaults():
    tree=ast.parse((ARTIFACTS/'sources/easyocr/easyocr.py').read_text(encoding='utf-8'))
    method=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='readtext')
    return dict(zip([n.arg for n in method.args.args][-len(method.args.defaults):],
                    [ast.literal_eval(n) for n in method.args.defaults]))


def paddle_defaults():
    tree=ast.parse((ARTIFACTS/'sources/paddleocr/tools/infer/utility.py').read_text(encoding='utf-8'))
    defaults={}
    for n in ast.walk(tree):
        if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='add_argument' and n.args:
            default=next((k.value for k in n.keywords if k.arg=='default'),None)
            if default is not None:
                try:defaults[ast.literal_eval(n.args[0]).removeprefix('--')]=ast.literal_eval(default)
                except ValueError:pass
    return defaults


def candidate(ident,package,config,models,preprocessing,grouping,deviations):
    return dict(candidate_id=ident,package=package,configuration=config,configuration_sha256=canonical_sha(config),
                model_sha256={p:sha(ARTIFACTS/'models'/p) for p in models},preprocessing=preprocessing,
                grouping=grouping,declared_deviations=deviations)


def main():
    easy=package_identity('easyocr','1.7.2',EASY_WHEEL_SHA)
    paddle=package_identity('paddleocr','2.8.1',PADDLE_WHEEL_SHA)
    easy_config=dict(constructor=dict(lang_list=['en'],gpu=False,detect_network='craft',recog_network='english_g2',
                                      download_enabled=False,detector=True,recognizer=True,verbose=False,
                                      quantize=True,cudnn_benchmark=False),call=easy_defaults())
    selected=('det_algorithm','det_limit_side_len','det_limit_type','det_box_type','det_db_thresh','det_db_box_thresh',
              'det_db_unclip_ratio','use_dilation','det_db_score_mode','rec_algorithm','rec_image_shape',
              'rec_image_inverse','max_text_length','use_space_char','ir_optim','use_tensorrt','precision',
              'use_angle_cls','enable_mkldnn','cpu_threads','rec_batch_num','use_gpu','use_onnx','show_log',
              'save_crop_res','return_word_box','max_batch_size')
    defaults=paddle_defaults()
    constructor={k:defaults[k] for k in selected}
    constructor.update(use_gpu=False,enable_mkldnn=True,cpu_threads=1,rec_batch_num=1,drop_score=0.0,show_log=False)
    paddle_config=dict(constructor=constructor,call=dict(cls=False,slice={}),
                       entrypoint='paddleocr.tools.infer.predict_system.TextSystem',
                       english_dictionary='paddleocr/ppocr/utils/en_dict.txt')
    candidates=[candidate('easyocr_craft_english_g2',easy,easy_config,
       ['easyocr/craft_mlt_25k.pth','easyocr/english_g2.pth'],
       dict(input='native file-path API: RGB detector, OpenCV grayscale recognizer',
            detector='aspect ratio, canvas<=2560, mag_ratio=1, pad to multiple32; RGB ImageNet mean/std',
            recognizer='native grouped crop, grayscale height64, aspect resize/padding, normalize [-1,1]; greedy',
            contrast_retry='native confidence<0.1 contrast-adjusted recognition pass retained, not a frame retry'),
       dict(policy='native group_text_box; paragraph=False; no external splitting/merging/NMS',
            slope_ths=0.1,ycenter_ths=0.5,height_ths=0.5,width_ths=0.5,add_margin=0.1,
            min_size='native max(box width,box height)>20'),
       ['CPU one-thread, one frame at a time; weights verified offline; English model explicit']),
       candidate('paddle_db_v3_rec_v4_keep_all',paddle,paddle_config,
       [f'paddleocr/{name}/{file}' for name in ('en_PP-OCRv3_det_infer','en_PP-OCRv4_rec_infer')
        for file in ('inference.pdmodel','inference.pdiparams','inference.pdiparams.info')],
       dict(input='OpenCV IMREAD_COLOR BGR, decoded original frame',
            detector='native DB resize maxside960, multiple32 rounding; mean[.485,.456,.406]/std[.229,.224,.225], scale1/255',
            recognizer='native perspective crop + tall-crop rotate if aspect>=1.5; 3x48x320 aspect-width batching/padding; normalize [-1,1]; CTC greedy',
            native_geometry='DB quad, unclip1.5, scorefast, max_candidates1000; native point-order/clip and <=3px box rejection retained'),
       dict(policy='one output per native DB region; no external paragraph/word split/merge, no slice',return_word_box=False),
       ['drop_score=0.0 replaces default0.5 so detection is not gated on recognition confidence',
        'enable_mkldnn=True and cpu_threads=1 enforce predictor math threads; rec_batch_num=1',
        'direct official TextSystem bypasses unused CLS downloads; angle classifier disabled'])]
    bindings={}
    for n in ('iiit-cvid-spotting-validation-261013-cohort.json','iiit-cvid-spotting-validation-261013-protocol.json',
              'iiit-cvid-spotting-validation-261013-freeze-verified-261014.json'):
        path='experiments/registry/datasets/'+n;bindings[path]=sha(ROOT/path)
    for path in ('experiments/outputs/iiit-cvid-spotting-validation-261013/ground-truth.jsonl','experiments/scripts/spotting_metrics.py'):
        bindings[path]=sha(ROOT/path)
    registry=dict(schema='iiit_cvid_spotting_candidates_v1',date='2026-10-14',
      selection_rule='two preselected OCR families inherited from recognition audit, not selected by spotting scores',
      status='weights_and_configuration_frozen_before_cohort_inference',cohort_binding=bindings,
      cpu_environment=dict(OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1',CUDA_VISIBLE_DEVICES=''),
      runtime_packages={'easyocr':'1.7.2','paddleocr':'2.8.1','paddlepaddle':'2.6.2','torch':'2.5.1+cpu',
                        'torchvision':'0.20.1+cpu','numpy':'1.26.4','scipy':'1.17.1','Pillow':'12.3.0',
                        'opencv-python':'4.6.0.66','opencv-contrib-python':'4.6.0.66','opencv-python-headless':'4.6.0.66',
                        'setuptools':'75.8.0','protobuf':'3.20.2'},
      input_rule='identical original frames, engine-native channel-specific decoding; no GT boxes/crops/lexicon for inference',
      scientific_limits=['native word/line grouping differences are part of packaged-system comparison, not recognizer accuracy',
                         'not equalized numerical precision: Easy native dynamic quantization; Paddle FP32 MKLDNN',
                         'no inference speed ranking; published native thresholds are not probability calibrated across engines',
                         'pretraining overlap unknown; exposed-validation released-label agreement only'],
      upstream_sources=['https://raw.githubusercontent.com/JaidedAI/EasyOCR/v1.7.2/easyocr/easyocr.py',
                        'https://raw.githubusercontent.com/PaddlePaddle/PaddleOCR/v2.8.1/tools/infer/utility.py',
                        'https://raw.githubusercontent.com/PaddlePaddle/PaddleOCR/v2.8.1/tools/infer/predict_system.py'],
      model_origins={n:dict(archive_sha256=sha(ARTIFACTS/n),url=url) for n,url in {
       'craft_mlt_25k.zip':'https://github.com/JaidedAI/EasyOCR/releases/download/pre-v1.1.6/craft_mlt_25k.zip',
       'en_PP-OCRv3_det_infer.tar':'https://paddleocr.bj.bcebos.com/PP-OCRv3/english/en_PP-OCRv3_det_infer.tar',
       'en_PP-OCRv4_rec_infer.tar':'https://paddleocr.bj.bcebos.com/PP-OCRv4/english/en_PP-OCRv4_rec_infer.tar'}.items()},
      candidates=candidates)
    data=(json.dumps(registry,sort_keys=True,ensure_ascii=False,indent=2)+'\n').encode()
    if REGISTRY.exists() and REGISTRY.read_bytes()!=data:
        raise ValueError('frozen candidate registry differs; use a new version')
    REGISTRY.write_bytes(data)
    print('Candidate registry SHA256:',sha(REGISTRY))


if __name__=='__main__':
    main()
