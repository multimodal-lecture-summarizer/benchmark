"""Build the real full-test spotting notebook and pre-outcome gallery membership."""
import inspect
import json
import math
from pathlib import Path

import nbformat as nbf

from experiments.scripts.spotting_comparison_io_v2 import OUT,write_once
from experiments.scripts.spotting_runtime_binding import ROOT,TEST,NAME,read_json

PATH=ROOT/'experiments/notebooks/iiit-cvid-test-spotting-comparison.ipynb'


def gallery_plan():
    frames=[f for f in read_json(TEST/(NAME+'-cohort.json'))['frames'] if f['selected']]
    selected=[]
    for course in sorted({f['course'] for f in frames}):
        rows=[f for f in frames if f['course']==course];counts=sorted(f['object_count'] for f in rows)
        used=set()
        for q in (.25,.75):
            index=(len(counts)-1)*q;lo=math.floor(index);hi=math.ceil(index)
            value=counts[lo]+(counts[hi]-counts[lo])*(index-lo)
            row=min((f for f in rows if f['frame_id'] not in used),key=lambda f:(abs(f['object_count']-value),f['frame_id']))
            used.add(row['frame_id']);selected.append(dict(frame_id=row['frame_id'],course=course,rule=f'object_count_q{q}',target=value))
    flags=read_json(TEST/(NAME+'-influence.json'))['excluded_frame_ids']
    plan=dict(rule='pre-outcome course/object-count q25/q75, nearest value then frame ID, without replacement; add fixed semantic-flag frames',
        selected=selected,semantic_flag_frames=flags,frame_ids=list(dict.fromkeys([r['frame_id'] for r in selected]+flags)))
    write_once(OUT/'gallery-plan.json',plan)


def build():
    gallery_plan();cells=[]
    def md(text): cells.append(nbf.v4.new_markdown_cell(inspect.cleandoc(text)))
    def code(text):
        value=inspect.cleandoc(text);compile(value,'<spotting-notebook>','exec');cells.append(nbf.v4.new_code_cell(value))
    md('''# CVID — so sánh spotting trên toàn bộ test đã khóa
    **1.754 frame / 40.063 XML objects**, hai candidate đã khóa weights/config/threshold/grouping.
    Đây là end-to-end localization + transcription theo nhãn phát hành, không phải query-retrieval mAP hay leaderboard chính thức.
    Test đã được EDA; annotation chọn lọc và nhãn nghi sai giữ nguyên. Precision/recall phản ánh agreement với release.
    Notebook thực sự chạy inference; checkpoint/receipt phân biệt mới chạy, resume, lỗi và timeout. Không tune theo điểm test.
    Run v1 dừng kỹ thuật sau 222 checkpoint EasyOCR vì Windows launcher/worker khác PID; chưa chấm điểm.
    V2 sửa supervision, chạy mới toàn bộ cohort; không ghép hoặc chọn prediction từ v1. Bằng chứng v1 được giữ nguyên và liên kết trong contract.
    ''')
    code('''from pathlib import Path
    import sys, json
    from IPython.display import display, Markdown
    ROOT=next(p for p in [Path.cwd(),Path.cwd()/'benchmark',*Path.cwd().parents] if (p/'experiments/scripts/run_spotting_comparison_v2.py').exists())
    sys.path.insert(0,str(ROOT))
    OUT=ROOT/'experiments/outputs/cvid-test-spotting-261014-v2'
    contract=json.loads((ROOT/'experiments/registry/datasets/iiit-cvid-test-spotting-analysis-261014-v2.json').read_text())
    display(Markdown('## Protocol và execution contract đã khai báo trước'))
    print(json.dumps(contract,ensure_ascii=False,indent=2))
    ''')
    md('''## 1. Chạy đủ frame cho cả hai candidate
    Chạy tuần tự trong venv đã khóa, mỗi candidate dùng process riêng. **Cell này không có notebook timeout.**
    Forward cap 600 giây/frame; timeout được ghi failure/FN, không thay cấu hình để retry. Process crash để các frame chưa commit ở trạng thái pending có thể resume; không giả lập đã infer.
    ''')
    code('''from experiments.scripts.run_spotting_comparison_v2 import run_all
    inference=run_all()
    print(json.dumps({k:v for k,v in inference.items() if k!='snapshot'},ensure_ascii=False,indent=2))
    ''')
    md('''## 2. Chấm cùng prediction và tất cả độ nhạy đã khóa
    Pooled micro Hmean là chính; không dùng mean frame F1. Mỗi failure giữ đủ GT dưới dạng FN.
    Độ nhạy: IoU>.75, case-sensitive, và bỏ nguyên 3 frame có cờ EDA (1.751 frame / 40.023 objects).
    Bootstrap paired B−A spotting Hmean: 2.000 draws, seed20261014, course và folder clusters; exploratory với chỉ 7 course. Không suy ra detection CI.
    ''')
    code('''from experiments.scripts.spotting_comparison_analysis import run_analysis
    analysis=run_analysis()
    print(json.dumps({k:v for k,v in analysis.items() if k not in ('artifacts','implementation')},ensure_ascii=False,indent=2))
    ''')
    code('''from experiments.scripts.spotting_comparison_plots import *
    from experiments.scripts.spotting_comparison_notebook import table, figure, galleries, finish_display
    data=load_tables(OUT)
    table(data['metrics'],'metrics-all-variants')
    figure(plot_primary(data),'01-primary-spotting-detection')
    figure(plot_counts(data),'02-counts-tp-fp-fn')
    ''')
    code('''table(data['metrics'][['variant','candidate_id','metric','selected_frames','gt_objects','successful_frames','failed_frames','empty_success_frames','invalid_predictions','empty_transcriptions']],'coverage-and-failures')
    table(data['failure_ledger'],'complete-failure-ledger')
    figure(plot_coverage(data),'03-coverage-failure-empty-invalid')
    ''')
    code('''table(data['course_metrics'],'all-course-metrics')
    figure(plot_course(data),'04-course-concentration-and-scores')
    ''')
    code('''table(data['source_group_metrics'][data['source_group_metrics'].variant.eq('primary')],'all-primary-folder-group-metrics')
    display(Markdown('Full CSV có tất cả source groups cho cả bốn variants; bảng trên hiển thị đầy đủ primary, không cắt hàng.'))
    ''')
    code('''figure(plot_sensitivity(data),'05-fixed-sensitivities')
    table(data['bootstrap'],'paired-spotting-uncertainty')
    figure(plot_uncertainty(data),'06-paired-cluster-uncertainty')
    ''')
    code('''figure(plot_frame_pairs(data),'07-paired-frame-diagnostics')
    display(Markdown('Frame Hmean chỉ để trực quan phân bố/paired differences; chỉ số chính luôn pool TP/FP/FN. Matching detection và spotting độc lập, không phải phân rã cộng lỗi recognition.'))
    ''')
    code('''figure(plot_costs(data),'08-observed-frame-costs')
    display(Markdown('CPU-only, native precision/grouping khác nhau. Thời gian gồm decode + forward cho frame; hashing/loading/verification ghi riêng trong receipts. Không kết luận model nào nhanh hơn. Peak RSS là process-lifetime peak, không phải peak riêng của frame; GPU memory không áp dụng.'))
    ''')
    md('''## 3. Đầy đủ frame IDs, GT và prediction text
    Bảng sau chứa đủ 1.754 IDs và toàn bộ raw text arrays của GT/EasyOCR/PaddleOCR; không cắt chuỗi hoặc ẩn hàng.
    Polygons/confidence và full failure/traceback/cost records có trong JSONL/checkpoints; full scores từng frame/variant trong CSV gzip.
    ''')
    code('''table(data['all_frame_text'],'all-1754-ids-and-full-texts')
    ''')
    md('''## 4. Trực quan pixels gốc, GT và prediction
    Gallery định trước: hai frame mỗi course gần q25/q75 object count, tie frame ID; thêm ba frame có cờ GT.
    Gallery diagnostic sau kết quả lấy sáu |B−A frame Hmean| lớn nhất, ghi rõ lựa chọn; không dùng để đổi cohort/GT/config.
    Màu GT/prediction là annotation overlay, không sửa pixels input dùng cho inference. Full text bên cạnh giữ được nội dung dù chữ trong ảnh nhỏ.
    ''')
    code('''gallery_receipt=galleries(data,OUT)
    ''')
    md('''## 5. Receipt và giới hạn kết luận
    Extra visible text chưa annotate vẫn là FP theo release. Không chứng nhận exhaustive OCR, gold sạch, writer/video độc lập, test mù, pretraining độc lập hay production winner.
    So sánh packaged systems gồm native grouping/precision; Hmean thấp có thể liên quan ghép dòng/từ và annotation coverage, không chỉ đọc sai chữ.
    ''')
    code('''display_receipt=finish_display(OUT,analysis,gallery_receipt)
    print(json.dumps(display_receipt,ensure_ascii=False,indent=2))
    ''')
    notebook=nbf.v4.new_notebook(cells=cells,metadata=dict(kernelspec=dict(display_name='Python 3',language='python',name='python3')))
    nbf.validate(notebook);PATH.parent.mkdir(parents=True,exist_ok=True);nbf.write(notebook,PATH)
    return PATH


if __name__=='__main__': print(build())
