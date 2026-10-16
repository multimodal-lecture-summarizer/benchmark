"""Frozen native-region adapters. Model loading and frame inference are separate."""
from importlib import import_module
import math
from pathlib import Path

from experiments.scripts.spotting_candidate_contract import ARTIFACTS


def adapt_regions(regions):
    """Preserve native coordinates, text and low-confidence/empty observations."""
    result = []
    for polygon, text, confidence in regions:
        if not isinstance(text,str) or not math.isfinite(float(confidence)):
            raise ValueError('malformed recognition observation')
        points = [[float(x),float(y)] for x,y in polygon]
        result.append(dict(polygon=points,text=text,recognition_confidence=float(confidence)))
    return result


def load_candidate(candidate, artifacts=ARTIFACTS):
    """Caller verifies source/model identity and thread environment before loading."""
    config = candidate['configuration']
    models = Path(artifacts)/'models'
    if candidate['candidate_id']=='easyocr_craft_english_g2':
        import torch
        import easyocr

        torch.set_num_threads(1)
        reader = easyocr.Reader(model_storage_directory=str(models/'easyocr'),**config['constructor'])
        if torch.get_num_threads()!=1 or reader.device!='cpu':
            raise ValueError('EasyOCR runtime differs from CPU/thread contract')
        runtime = dict(device=reader.device,threads=torch.get_num_threads(),quantize_requested=True,
                       quantized_recognizer_modules=sum('quantized' in type(m).__module__ for m in reader.recognizer.modules()))

        def predict(path):
            return adapt_regions(reader.readtext(str(path),**config['call']))

        return predict,runtime

    if candidate['candidate_id']!='paddle_db_v3_rec_v4_keep_all':
        raise ValueError('unknown candidate')
    # Direct TextSystem avoids PaddleOCR's unconditional download of unused CLS.
    import paddleocr

    module = import_module('paddleocr.paddleocr')
    system = import_module('paddleocr.tools.infer.predict_system')
    args = module.parse_args(mMain=False)
    for key,value in config['constructor'].items():
        setattr(args,key,value)
    args.det_model_dir = str(models/'paddleocr/en_PP-OCRv3_det_infer')
    args.rec_model_dir = str(models/'paddleocr/en_PP-OCRv4_rec_infer')
    args.rec_char_dict_path = str(Path(paddleocr.__file__).parent/'ppocr/utils/en_dict.txt')
    reader = system.TextSystem(args)
    threads = {name:getattr(reader,name).config.cpu_math_library_num_threads()
               for name in ('text_detector','text_recognizer')}
    if any(n!=1 for n in threads.values()) or reader.use_angle_cls or reader.drop_score!=0:
        raise ValueError('Paddle runtime differs from frozen contract')

    def predict(path):
        import cv2
        image = cv2.imread(str(path),cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError('image decode failed')
        boxes,recognitions,_ = reader(image,cls=False,slice={})
        if boxes is None and recognitions is None:
            return []
        if len(boxes)!=len(recognitions):
            raise ValueError('detector/recognizer count mismatch')
        return adapt_regions([(b,r[0],r[1]) for b,r in zip(boxes,recognitions)])

    return predict,dict(device='cpu',threads=threads,enable_mkldnn=True,drop_score=reader.drop_score,
                        angle_classifier_loaded=False)


def frame_record(frame_id, path, predictor):
    """Frame failure discards partial predictions, preserving the scoring denominator."""
    try:
        predictions = predictor(path)
        return dict(frame_id=frame_id,status='ok',error=None,predictions=predictions)
    except Exception as exc:
        return dict(frame_id=frame_id,status='error',error=f'{type(exc).__name__}: {exc}',predictions=[])
