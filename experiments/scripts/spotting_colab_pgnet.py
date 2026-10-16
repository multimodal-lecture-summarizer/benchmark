"""Official PGNet joint spotting, native polygon/text output without invented scores."""
from importlib import import_module
from pathlib import Path

from experiments.scripts.spotting_colab_artifacts import sha


def pgnet_regions(polygons, texts):
    if polygons is None or texts is None or len(polygons) != len(texts):
        raise ValueError('PGNet polygon/text count mismatch')
    result = []
    for polygon, text in zip(polygons, texts):
        if not isinstance(text, str):
            raise ValueError('PGNet transcription must be a string')
        result.append(dict(polygon=[[float(x), float(y)] for x, y in polygon], text=text))
    return result


def load_pgnet(candidate, prepared):
    import cv2
    import paddle
    import paddleocr
    if not paddle.is_compiled_with_cuda():
        raise ValueError('PGNet profile requires Paddle CUDA build')
    paddle.set_device('gpu:0')
    dictionary = Path(paddleocr.__file__).parent / 'ppocr/utils/ic15_dict.txt'
    if sha(dictionary) != candidate['decoder_sha256']:
        raise ValueError('PGNet dictionary identity mismatch')
    # Use the package's argument defaults (and their sealed source) without
    # consuming notebook/worker CLI flags or importing the high-level OCR pipeline.
    utility = import_module('paddleocr.tools.infer.utility')
    args = utility.init_args().parse_args([])
    for key, value in candidate['configuration'].items():
        setattr(args, key, value)
    args.e2e_model_dir = str(Path(prepared['models']) / 'pgnet/e2e_server_pgnetA_infer')
    args.e2e_char_dict_path = str(dictionary)
    reader = import_module('paddleocr.tools.infer.predict_e2e').TextE2E(args)
    if not reader.predictor.get_input_names() or len(reader.output_tensors) != 4:
        raise ValueError('PGNet exported graph does not expose the expected joint heads')
    runtime = dict(device=paddle.device.cuda.get_device_name(0), cuda=paddle.version.cuda(),
                   precision='fp32', joint_heads=['f_border', 'f_char', 'f_direction', 'f_score'],
                   decoder_sha256=sha(dictionary), configuration=candidate['configuration'],
                   native_postprocess='PGPostProcess fast totaltext; native TextE2E clipping preserved',
                   input_names=reader.predictor.get_input_names(),
                   output_names=reader.predictor.get_output_names())
    def predict(path):
        image = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError('PGNet image decode failed')
        polygons, texts, _ = reader(image)
        return pgnet_regions(polygons, texts)
    return predict, runtime
