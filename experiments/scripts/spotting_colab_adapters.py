"""Native full-frame adapters; model imports happen only inside isolated workers."""
import csv
import io
from pathlib import Path
import subprocess

from experiments.scripts.spotting_candidate_adapters import adapt_regions


def _cuda_torch():
    import torch
    if not torch.cuda.is_available() or 'T4' not in torch.cuda.get_device_name(0):
        raise ValueError('required NVIDIA T4 CUDA device unavailable')
    torch.set_num_threads(1)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    torch.backends.cudnn.benchmark = False
    return torch, dict(device=torch.cuda.get_device_name(0), cuda=torch.version.cuda,
                      cudnn=torch.backends.cudnn.version(), precision='fp32', tf32=False)


def _easy(candidate, prepared):
    import easyocr
    torch, runtime = _cuda_torch()
    config = candidate['configuration']
    reader = easyocr.Reader(model_storage_directory=str(Path(prepared['models'])/'easyocr'),
                            **config['constructor'])
    if any('quantized' in type(m).__module__ for m in reader.recognizer.modules()):
        raise ValueError('GPU recognizer unexpectedly quantized')
    runtime['quantize'] = False
    return lambda path: adapt_regions(reader.readtext(str(path), **config['call'])), runtime


def _legacy(candidate, prepared):
    from importlib import import_module
    import paddle
    import paddleocr
    import cv2
    if not paddle.is_compiled_with_cuda():
        raise ValueError('Paddle CPU build cannot satisfy T4 profile')
    paddle.set_device('gpu:0')
    args = import_module('paddleocr.paddleocr').parse_args(mMain=False)
    for key, value in candidate['configuration']['constructor'].items():
        setattr(args, key, value)
    models = Path(prepared['models'])/'paddleocr'
    args.det_model_dir = str(models/'en_PP-OCRv3_det_infer')
    args.rec_model_dir = str(models/'en_PP-OCRv4_rec_infer')
    args.rec_char_dict_path = str(Path(paddleocr.__file__).parent/'ppocr/utils/en_dict.txt')
    reader = import_module('paddleocr.tools.infer.predict_system').TextSystem(args)
    if reader.use_angle_cls or reader.drop_score != 0:
        raise ValueError('legacy Paddle effective settings mismatch')
    def predict(path):
        image = cv2.imread(str(path))
        if image is None:
            raise ValueError('image decode failed')
        boxes, texts, _ = reader(image, cls=False, slice={})
        if boxes is None and texts is None:
            return []
        if len(boxes) != len(texts):
            raise ValueError('legacy Paddle output mismatch')
        return adapt_regions([(box, text[0], text[1]) for box, text in zip(boxes, texts)])
    return predict, dict(device=paddle.device.cuda.get_device_name(0), cuda=paddle.version.cuda(),
                         precision='fp32', enable_mkldnn=False, drop_score=reader.drop_score)


def tsv_regions(tsv):
    """Exclude hierarchy rows only. Empty recognized words remain observations."""
    result = []
    for row in csv.DictReader(io.StringIO(tsv), delimiter='\t', quoting=csv.QUOTE_NONE):
        if row['level'] != '5':
            continue
        x, y, w, h = [float(row[key]) for key in ('left', 'top', 'width', 'height')]
        result.append(([[x,y],[x+w,y],[x+w,y+h],[x,y+h]], row['text'], float(row['conf'])/100))
    return adapt_regions(result)


def _tesseract(candidate, prepared):
    config = candidate['configuration']
    def predict(path):
        command = [prepared['tesseract'], str(path), 'stdout', '--tessdata-dir',
                   str(Path(prepared['models'])/'tessdata'), '-l', config['language'],
                   '--oem', str(config['oem']), '--psm', str(config['psm']), '-c','tessedit_create_tsv=1']
        result = subprocess.run(command, check=True, capture_output=True, text=True, encoding='utf-8')
        return tsv_regions(result.stdout)
    return predict, dict(device='cpu', precision='native', binary_identity=prepared['binary_identity'])


def _doctr(candidate, prepared):
    torch, runtime = _cuda_torch()
    from doctr.io import DocumentFile
    from doctr.models import fast_base, parseq, ocr_predictor
    config = dict(candidate['configuration'])
    det = fast_base(pretrained=False, pretrained_backbone=False, assume_straight_pages=False)
    rec = parseq(pretrained=False, pretrained_backbone=False)
    from experiments.scripts.spotting_colab_doctr import load_parseq_checkpoint
    for model, name in [(det,'fast'), (rec,'parseq')]:
        state = torch.load(Path(prepared['models'])/'doctr'/f'{name}.pt', map_location='cpu', weights_only=True)
        if name == 'parseq':
            runtime['parseq_checkpoint_compatibility'] = load_parseq_checkpoint(model, state)
        else:
            model.load_state_dict(state, strict=True)
    det.postprocessor.bin_thresh = config.pop('bin_thresh')
    det.postprocessor.box_thresh = config.pop('box_thresh')
    config.pop('det_arch'); config.pop('reco_arch')
    reader = ocr_predictor(det_arch=det, reco_arch=rec, pretrained=False, **config).cuda().eval()
    runtime['model_cfg'] = {'det': det.cfg, 'rec': rec.cfg}
    def predict(path):
        with torch.inference_mode():
            page = reader(DocumentFile.from_images(str(path))).pages[0]
        height, width = page.dimensions
        rows = []
        for block in page.blocks:
            for line in block.lines:
                for word in line.words:
                    geometry = word.geometry
                    if len(geometry) != 4:
                        raise ValueError('expected native rotated quadrilateral')
                    rows.append(([[float(x)*width,float(y)*height] for x,y in geometry], word.value, word.confidence))
        return adapt_regions(rows)
    return predict, runtime


def _modern(candidate, prepared):
    import paddle
    from paddleocr import PaddleOCR
    if not paddle.is_compiled_with_cuda():
        raise ValueError('Paddle GPU build required')
    config = dict(candidate['configuration'])
    config.update(text_detection_model_dir=str(Path(prepared['models'])/'pp6/det'),
                  text_recognition_model_dir=str(Path(prepared['models'])/'pp6/rec'))
    reader = PaddleOCR(**config)
    def predict(path):
        results = list(reader.predict(str(path)))
        if len(results) != 1:
            raise ValueError('expected one Paddle result per input')
        data = results[0]
        if hasattr(data, 'json'):
            data = data.json
        if isinstance(data, dict) and 'res' in data:
            data = data['res']
        boxes, texts, scores = [data[key] for key in ('rec_polys','rec_texts','rec_scores')]
        if not len(boxes) == len(texts) == len(scores):
            raise ValueError('Paddle output count mismatch')
        return adapt_regions(zip(boxes,texts,scores))
    return predict, dict(device=paddle.device.cuda.get_device_name(0), cuda=paddle.version.cuda(), precision='fp32')


def _testr(candidate, prepared):
    torch, runtime = _cuda_torch()
    import cv2
    from adet.config import get_cfg
    from detectron2.engine import DefaultPredictor
    from adet.utils.visualizer import TextVisualizer
    config = get_cfg()
    config.merge_from_file(str(Path(prepared['testr_source'])/candidate['configuration']['config']))
    config.MODEL.WEIGHTS = str(Path(prepared['models'])/'testr/model.pth')
    config.MODEL.DEVICE = 'cuda'
    config.MODEL.TRANSFORMER.INFERENCE_TH_TEST = candidate['configuration']['threshold']
    config.freeze()
    if not config.MODEL.TRANSFORMER.USE_POLYGON or config.MODEL.BATEXT.CUSTOM_DICT:
        raise ValueError('TESTR native polygon/no-custom-lexicon contract mismatch')
    reader = DefaultPredictor(config)
    runtime['effective_config'] = config.dump()
    def predict(path):
        image = cv2.imread(str(path))
        if image is None:
            raise ValueError('image decode failed')
        with torch.no_grad():
            result = reader(image)['instances'].to('cpu')
        # Reuse the author's decoder verbatim, including unknown-character handling.
        decoder = TextVisualizer(image[:,:,::-1],metadata=None,instance_mode=0,cfg=config)
        polygons, recs, scores = result.polygons.numpy(), result.recs, result.scores.tolist()
        return adapt_regions([(polygon.reshape(-1,2),decoder._decode_recognition(rec),score)
                              for polygon,rec,score in zip(polygons,recs,scores)])
    return predict,runtime


def load_colab_candidate(candidate, prepared):
    if candidate['adapter'] == 'pgnet':
        from experiments.scripts.spotting_colab_pgnet import load_pgnet
        return load_pgnet(candidate, prepared)
    adapters = {'easyocr':_easy, 'paddle_legacy':_legacy, 'tesseract':_tesseract,
                'doctr':_doctr, 'paddle_modern':_modern,'testr':_testr}
    return adapters[candidate['adapter']](candidate, prepared)
