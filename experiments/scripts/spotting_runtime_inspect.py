"""Inspect actual native reader state; do not run images or change model state."""
import inspect
from pathlib import Path

from experiments.scripts.spotting_candidate_contract import ARTIFACTS, canonical_sha, sha
from experiments.scripts.spotting_runtime_binding import require


def inspect_easy(reader, candidate, predictor):
    import torch
    import easyocr.config as native
    config=candidate['configuration']
    require(inspect.getclosurevars(predictor).nonlocals['config']==config, 'EasyOCR call configuration mismatch')
    inspect.signature(reader.readtext).bind('not-an-input-image',**config['call'])
    expected=native.recognition_models['gen2']['english_g2']['characters']
    require(reader.character==expected and reader.converter.character==['[blank]']+list(expected), 'EasyOCR character/decoder mismatch')
    require(reader.device=='cpu' and torch.get_num_threads()==1 and not reader.download_enabled, 'EasyOCR device/threads/download mismatch')
    require(reader.detect_network=='craft' and reader.model_lang=='english' and native.imgH==64, 'EasyOCR architecture/preprocess mismatch')
    require(Path(reader.model_storage_directory).resolve()==(ARTIFACTS/'models/easyocr').resolve(), 'EasyOCR model storage mismatch')
    modules={name:type(m).__module__+'.'+type(m).__name__ for name,m in reader.recognizer.named_modules()
             if '.quantized.dynamic.' in type(m).__module__ and type(m).__name__ in ('LSTM','Linear')}
    require({'LSTM','Linear'} <= {name.rsplit('.',1)[1] for name in modules.values()}, 'EasyOCR real recognizer quantization missing')
    require(not reader.detector.training and not reader.recognizer.training, 'EasyOCR native eval state mismatch')
    require(all(p.device.type=='cpu' for m in (reader.detector,reader.recognizer) for p in m.parameters()), 'EasyOCR parameter device mismatch')
    return dict(device=reader.device,intraop_threads=torch.get_num_threads(),interop_threads=torch.get_num_interop_threads(),
        detector_class=type(reader.detector).__module__+'.'+type(reader.detector).__name__,
        recognizer_class=type(reader.recognizer).__module__+'.'+type(reader.recognizer).__name__,
        detector_training=reader.detector.training,recognizer_training=reader.recognizer.training,
        recognizer_dynamic_quantized_layers=modules,
        detector_quantized_modules=sum('quantized' in type(m).__module__ for m in reader.detector.modules()),
        native_quantize_attribute=reader.quantize,character_count=len(expected),characters_sha256=canonical_sha(expected),
        torch_quantized_engine=torch.backends.quantized.engine,
        recognizer_height=native.imgH,call_config=config['call'],configuration_sha256=canonical_sha(config),
        parameter_dtypes=sorted({str(p.dtype) for m in (reader.detector,reader.recognizer) for p in m.parameters()}),
        inference_behavior='readtext signature/config and pinned source inspected; preprocessing/grouping not exercised on an image')


def inspect_paddle(reader,candidate):
    constructor=candidate['configuration']['constructor']
    for key,value in constructor.items():
        require(getattr(reader.args,key)==value, 'Paddle constructor not applied: '+key)
    require(not reader.use_angle_cls and not hasattr(reader,'text_classifier') and reader.drop_score==0., 'Paddle CLS/drop_score mismatch')
    detector,recognizer=reader.text_detector,reader.text_recognizer
    post=detector.postprocess_op
    actual={key:getattr(post,key) for key in ('thresh','box_thresh','unclip_ratio','score_mode','box_type','max_candidates','min_size')}
    require(actual==dict(thresh=.3,box_thresh=.6,unclip_ratio=1.5,score_mode='fast',box_type='quad',max_candidates=1000,min_size=3), 'Paddle DB thresholds/quad mismatch')
    require(post.dilation_kernel is None and detector.det_algorithm=='DB' and not detector.use_onnx, 'Paddle detector algorithm/dilation mismatch')
    pre=detector.preprocess_op
    require([type(o).__name__ for o in pre]==['DetResizeForTest','NormalizeImage','ToCHWImage','KeepKeys'], 'Paddle preprocessing operators mismatch')
    require(pre[0].limit_side_len==960 and pre[0].limit_type=='max' and pre[0].resize_type==0, 'Paddle detector resize mismatch')
    import numpy as np
    require(np.allclose(pre[1].mean.reshape(-1),[.485,.456,.406]) and np.allclose(pre[1].std.reshape(-1),[.229,.224,.225])
            and np.isclose(pre[1].scale,1/255), 'Paddle normalization mismatch')
    require(recognizer.rec_image_shape==[3,48,320] and recognizer.rec_batch_num==1 and recognizer.rec_algorithm=='SVTR_LCNet', 'Paddle recognition geometry/batch mismatch')
    require(not recognizer.return_word_box and not recognizer.use_onnx, 'Paddle recognizer grouping/backend mismatch')
    dictionary=Path(reader.args.rec_char_dict_path)
    require(sha(dictionary)==candidate['package']['file_sha256']['paddleocr/ppocr/utils/en_dict.txt'], 'Paddle actual dictionary mismatch')
    expected=['blank']+dictionary.read_text(encoding='utf-8').splitlines()+[' ']
    require(list(recognizer.postprocess_op.character)==expected, 'Paddle actual decoder characters mismatch')
    predictors={}
    for name,model in [('text_detector','en_PP-OCRv3_det_infer'),('text_recognizer','en_PP-OCRv4_rec_infer')]:
        cfg=getattr(reader,name).config
        require(not cfg.use_gpu() and cfg.mkldnn_enabled() and cfg.cpu_math_library_num_threads()==1 and cfg.ir_optim()
                and not cfg.tensorrt_engine_enabled() and not cfg.mkldnn_int8_enabled(), 'Paddle effective CPU/MKLDNN/precision mismatch')
        paths={}
        for method,filename in [('prog_file','inference.pdmodel'),('params_file','inference.pdiparams')]:
            path=Path(getattr(cfg,method)()).resolve()
            require(path==(ARTIFACTS/'models/paddleocr'/model/filename).resolve(), 'Paddle actual predictor model path mismatch')
            paths[filename]=dict(path=str(path),sha256=sha(path))
        predictors[name]=dict(use_gpu=cfg.use_gpu(),mkldnn_enabled=cfg.mkldnn_enabled(),
            threads=cfg.cpu_math_library_num_threads(),ir_optim=cfg.ir_optim(),int8_enabled=cfg.mkldnn_int8_enabled(),models=paths)
    return dict(device='cpu',predictors=predictors,constructor_applied=constructor,db_postprocess=actual,
        detector_resize=dict(limit_side_len=pre[0].limit_side_len,limit_type=pre[0].limit_type),
        normalize=dict(mean=pre[1].mean.reshape(-1).tolist(),std=pre[1].std.reshape(-1).tolist(),scale=float(pre[1].scale)),
        recognition_shape=recognizer.rec_image_shape,recognition_batch=recognizer.rec_batch_num,
        decoder_class=type(recognizer.postprocess_op).__name__,dictionary_sha256=sha(dictionary),characters_sha256=canonical_sha(expected),
        character_count=len(expected),drop_score=reader.drop_score,angle_classifier_loaded=False,
        configuration_sha256=canonical_sha(candidate['configuration']),call_config=candidate['configuration']['call'],
        inference_behavior='effective native state and pinned call/source inspected; crop/CTC/grouping behavior not exercised on an image')


def inspect_reader(candidate,predictor):
    reader=inspect.getclosurevars(predictor).nonlocals['reader']
    if candidate['candidate_id']=='easyocr_craft_english_g2':
        return inspect_easy(reader,candidate,predictor)
    return inspect_paddle(reader,candidate)
