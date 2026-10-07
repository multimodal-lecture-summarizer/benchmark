"""Build the executable, output-bearing pre-split EDA notebook."""

from __future__ import annotations

from pathlib import Path

import nbformat as nbf


ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "experiments/notebooks/diagnostics/full-corpus-pre-split-eda.ipynb"


def md(value: str):
    return nbf.v4.new_markdown_cell(value.strip())


def code(value: str):
    return nbf.v4.new_code_cell(value.strip())


def main() -> None:
    cells = [
        md("""
# EDA toàn bộ dữ liệu cục bộ trước khi chia tập nghiên cứu

Chạy trên **toàn bộ annotation/metadata đang materialized** của TED-LIUM, IIIT-CVID,
EduViQA, SlideVQA, VidChapters, YTSeg, Yale, MIT001 và TVSum. Split gốc của nhà phát hành
chỉ là thuộc tính nguồn; notebook **chưa tạo split nghiên cứu mới**.

Quét toàn bộ 270.323 dòng TED-LIUM, 5.475 frame/XML và 137.745 crop của IIIT-CVID,
toàn bộ danh sách annotation JSON/Parquet có trên máy, cùng metadata container của tất cả
video cục bộ. Không chạy mô hình. Không giải mã 53 GB waveform, mọi frame của video,
hoặc pickle 2 GB không đáng tin cậy. Những phần này được ghi là giới hạn, không gọi là đã kiểm tra.

Theo yêu cầu phân tích trước khi chia tập, thống kê tổng hợp có đọc trường reference trong
split gốc tên `test`. Vì vậy không được mô tả split gốc này là hoàn toàn chưa xem nhãn
trong một phép chọn cohort về sau.
"""),
        code("""
from pathlib import Path
import hashlib, json, sys
import pandas as pd
import matplotlib.pyplot as plt
from IPython.display import display

ROOT = next((p for p in [Path.cwd(), *Path.cwd().parents]
             if (p / 'experiments/datasets').is_dir()), None)
if ROOT is None:
    raise FileNotFoundError('Run inside the benchmark repository')
sys.path.insert(0, str(ROOT))
from experiments.scripts.component_eda_audio import analyze_audio
from experiments.scripts.component_eda_visual import analyze_visual
from experiments.scripts.full_corpus_eda_visual_duplicates import screen_visual_duplicates
from experiments.scripts.full_corpus_eda_catalog import analyze_catalog
OUT = ROOT / 'experiments/outputs/full_corpus_eda_261003'
OUT.mkdir(parents=True, exist_ok=True)
def save(name, value):
    path = OUT / (name + '.json')
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\\n', encoding='utf-8')
    return path
print('Repository:', ROOT)
print('EDA output:', OUT)
"""),
        md("## 1. Kiểm kê tất cả dataset và media cục bộ"),
        code("""
catalog = analyze_catalog(ROOT)
save('catalog', catalog)
inventory = pd.DataFrame([
    {'dataset': name, 'files': item['files'], 'GiB': round(item['bytes']/2**30, 3),
     'top_extensions': ', '.join(f'{k}:{v}' for k,v in
                                sorted(item['extensions'].items(), key=lambda kv:-kv[1])[:4])}
    for name,item in catalog['inventory'].items()
]).sort_values('dataset')
display(inventory)
print('Total local GiB:', round(sum(x['bytes'] for x in catalog['inventory'].values())/2**30,2))
print('Inventory policy:', catalog['inventory_policy'])
"""),
        code("""
other = [
 {'dataset':'EduViQA', 'annotation_units':catalog['eduviqa']['qa_pairs'],
  'local_videos':catalog['eduviqa']['media']['materialized_videos'],
  'reference':'Q&A; evidence provenance unresolved'},
 {'dataset':'SlideVQA', 'annotation_units':sum(x['qa_pairs'] for x in catalog['slidevqa']['splits']),
  'local_videos':0, 'reference':'Q&A; slide images missing'},
 {'dataset':'VidChapters', 'annotation_units':sum(catalog['vidchapters']['annotation_id_counts'].values()),
  'local_videos':catalog['vidchapters']['media']['materialized_videos'],
  'reference':'chapter payload is an untrusted 2 GB pickle, not parsed'},
 {'dataset':'YTSeg', 'annotation_units':catalog['ytseg']['annotation_rows'],
  'local_videos':catalog['ytseg']['media']['materialized_videos'],
  'reference':'creator chapters; not scene cuts'},
 {'dataset':'Yale', 'annotation_units':None, 'local_videos':catalog['yale']['media']['materialized_videos'],
  'reference':'qualification media, GT and rights need adjudication'},
 {'dataset':'MIT001', 'annotation_units':catalog['mit001']['gt_segments'],
  'local_videos':catalog['mit001']['actual_videos'],
  'reference':'chapter segments; 9 videos need review'},
 {'dataset':'TVSum', 'annotation_units':None, 'local_videos':0,
  'reference':'no materialized local media/annotations'},
]
display(pd.DataFrame(other))
print('EduViQA QA per video:',catalog['eduviqa']['qa_per_video'])
print('EduViQA question/answer words:',catalog['eduviqa']['question_words'],
      catalog['eduviqa']['answer_words'])
print('EduViQA transcript words:',catalog['eduviqa']['transcript_words'],
      'blank:',catalog['eduviqa']['blank_transcripts'],
      'repeat questions:',catalog['eduviqa']['repeated_questions_within_video'])
print('SlideVQA decks across native splits:',catalog['slidevqa']['deck_overlap'])
display(pd.DataFrame(catalog['slidevqa']['splits']))
print('VidChapters native ID counts:',catalog['vidchapters']['annotation_id_counts'])
print('YTSeg chapter count quantiles:',catalog['ytseg']['chapters_per_video'])
print('YTSeg zero-chapter rows:',catalog['ytseg']['rows_without_chapters'],
      'duplicate video ID rows:',catalog['ytseg']['annotation_rows']-catalog['ytseg']['unique_annotation_video_ids'])
"""),
        md("## 2. TED-LIUM: toàn bộ Arrow train/validation/test"),
        code("""
audio = analyze_audio(ROOT)
save('tedlium3', audio)
columns = ['source_split','rows','valid_asr_rows','gap_rows','ignore_marker_rows',
           'unique_speakers','unique_source_files','segment_duration_sum_seconds',
           'merged_source_coverage_seconds','adjacent_interval_overlaps']
display(pd.DataFrame(audio['source_rows'])[columns])
display(pd.DataFrame(audio['cross_split_overlap']))
display(pd.DataFrame([
 {'split':row['source_split'], 'gender_codes':row['gender_code_counts'],
  'missing_speaker':row['missing_speaker_rows'],
  'missing_source':row['missing_source_file_rows'],
  'bad_timing':row['unparseable_or_nonpositive_timing_rows'],
  'repeated_reference_groups':row['repeated_reference_groups'],
  'rows_in_repeated_reference_groups':row['rows_in_repeated_reference_groups']}
 for row in audio['source_rows']
]))
for row in audio['source_rows']:
    print(row['source_split'],'top speakers:',row['top_speakers'],
          'segments/speaker:',row['segments_per_speaker_quantiles'])
print('Historical D2:', audio['historical_d2_units'], audio['historical_freeze_status'])
print('Readiness candidate:', audio['readiness_selected'], 'retained:', audio['readiness_retained'],
      'eligible:', audio['readiness_selection_eligible'])
"""),
        code("""
quantiles=[]
for row in audio['source_rows']:
    for label,key in [('duration_seconds','duration_quantiles_seconds'),
                      ('reference_words','reference_word_quantiles'),
                      ('words_per_second','wps_quantiles')]:
        quantiles.append({'split':row['source_split'],'variable':label,**row[key]})
display(pd.DataFrame(quantiles))
fig,axes=plt.subplots(1,2,figsize=(12,4))
for row in audio['source_rows']:
    count=row['duration_histogram']
    axes[0].plot(range(len(count)),[v/sum(count) for v in count],marker='o',label=row['source_split'])
    count=row['reference_word_histogram']
    axes[1].plot(range(len(count)),[v/sum(count) for v in count],marker='o',label=row['source_split'])
axes[0].set_xticks(range(8),['<1','1–2','2–5','5–10','10–20','20–30','30–60','≥60'],rotation=45)
axes[1].set_xticks(range(7),['<5','5–10','10–20','20–40','40–80','80–160','≥160'],rotation=45)
axes[0].set_title('Độ dài segment theo split gốc');axes[1].set_title('Số từ nhãn ASR hợp lệ')
for ax in axes:ax.set_ylabel('Tỷ lệ trong split');ax.legend();ax.grid(alpha=.2)
plt.tight_layout();display(fig);plt.close(fig)
"""),
        md("""
**Đọc bảng ASR:** `ignore_time_segment_in_scoring` và `inter_segment_gap` là ký hiệu không chấm ASR.
Tổng thời lượng segment có chồng lấn, vì vậy dùng `merged_source_coverage_seconds` để
mô tả vùng thời gian được phủ; nó vẫn không chứng minh toàn bộ 53 GB audio đã giải mã.
"""),
        md("## 3. IIIT-CVID: toàn bộ frame/XML và crop/nhãn"),
        code("""
visual = analyze_visual(ROOT)
save('iiit_cvid', visual)
display(pd.DataFrame([
 {k:row[k] for k in ['source_split','frames','xml_files','courses','videos','text_lines',
                     'text_words','blank_text_lines','invalid_boxes','xml_size_mismatches']}
 for row in visual['frames']
]))
display(pd.DataFrame([
 {k:row[k] for k in ['source_split','crop_files','label_rows','unique_label_paths',
                     'missing_labeled_images','blank_labels','unique_label_strings',
                     'non_ascii_labels','numeric_labels']}
 for row in visual['crops']
]))
display(pd.DataFrame(visual['source_split_overlap']))
"""),
        code("""
fig,axes=plt.subplots(1,2,figsize=(11,4))
for row in visual['frames']:
    axes[0].bar(row['source_split'],row['frames'],label=row['source_split'])
    axes[1].bar(row['source_split'],row['text_lines']/row['frames'])
axes[0].set_title('Số frame có XML'); axes[1].set_title('Dòng chữ / frame')
for ax in axes:ax.grid(axis='y',alpha=.2)
plt.tight_layout();display(fig);plt.close(fig)
for row in visual['frames']:
    print(row['source_split'],'frame/course:',row['frames_per_course'],
          'line/frame quantiles:',row['lines_per_frame_quantiles'],
          'geometry:',row['width_quantiles'],row['height_quantiles'])
    if row['invalid_box_frames']:
        print('  Invalid boxes:',row['invalid_box_frames'])
    if row['xml_size_mismatch_examples']:
        print('  XML size mismatch examples:',row['xml_size_mismatch_examples'][:10])
for row in visual['crops']:
    print(row['source_split'],'crop label length:',row['label_length_quantiles'],
          'top labels:',row['top_labels'][:8],
          'crop dimensions:',row['top_image_dimensions'][:5])
"""),
        md("## 4. Kiểm tra trùng ảnh trên toàn bộ 5.475 frame"),
        code("""
duplicates = screen_visual_duplicates(ROOT)
save('iiit_cvid_duplicates', duplicates)
display(pd.DataFrame([{k:v for k,v in duplicates.items()
                       if k not in ('near_cross_split_examples','exact_cross_split_examples',
                                    'interpretation')}]))
display(pd.DataFrame(duplicates['near_cross_split_examples']))
print(duplicates['interpretation'])
"""),
        md("""
**Diễn giải trùng ảnh:** SHA-256 nhận diện bản sao byte chính xác. dHash khoảng cách Hamming ≤6
chỉ nêu cặp cần xem lại; slide có bố cục giống nhau có thể khác nội dung. Không tự loại
frame chỉ dựa trên dHash.
"""),
        md("## 5. Quyết định sau EDA, trước khi chia tập"),
        code("""
decisions = pd.DataFrame([
 {'endpoint':'ASR','dataset':'TED-LIUM','decision':'dùng để thiết kế benchmark',
  'reason':'270.323 segment; lọc 398 nhãn không chấm; chia theo nguồn/diễn giả; chưa kiểm tra toàn bộ waveform'},
 {'endpoint':'OCR','dataset':'IIIT-CVID','decision':'dùng để thiết kế benchmark',
  'reason':'frame/XML và crop có nhãn đầy đủ; box/XML size bất thường và dHash cần phân xử'},
 {'endpoint':'scene cut / keyframe / caption','dataset':'các nguồn video cục bộ',
  'decision':'chưa có GT đúng tác vụ',
  'reason':'chapter/QA/transition thuật toán không thay nhãn scene, keyframe, caption độc lập'},
 {'endpoint':'QA','dataset':'EduViQA / SlideVQA','decision':'khảo sát riêng',
  'reason':'EduViQA có 883 QA trên 20 video; SlideVQA 14.484 QA nhưng thiếu ảnh slide'},
])
display(decisions)
print('No research split or model ranking was created by this notebook.')
"""),
        code("""
scripts = ['experiments/scripts/component_eda_audio.py',
           'experiments/scripts/component_eda_visual.py',
           'experiments/scripts/full_corpus_eda_visual_duplicates.py',
           'experiments/scripts/full_corpus_eda_catalog.py']
artifacts = ['catalog.json','tedlium3.json','iiit_cvid.json','iiit_cvid_duplicates.json']
provenance = ['experiments/datasets/tedlium3/provenance.json',
              'experiments/datasets/iiit_cvid/provenance.json',
              'experiments/datasets/slidevqa/provenance.json',
              'experiments/datasets/tedlium3/train/state.json',
              'experiments/datasets/tedlium3/validation/state.json',
              'experiments/datasets/tedlium3/test/state.json']
receipt = {
 'status':'executed_full_local_corpus_eda_with_declared_limits',
 'source_splits_analyzed':['train','validation','test'],
 'research_split_created':False, 'model_inference_run':False,
 'native_test_reference_aggregates_accessed':True,
 'script_sha256':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in scripts},
 'source_metadata_sha256':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in provenance},
 'artifact_sha256':{name:hashlib.sha256((OUT/name).read_bytes()).hexdigest() for name in artifacts},
 'artifact_root':str(OUT),
}
save('eda_receipt',receipt)
display(pd.DataFrame([{'artifact':k,'sha256':v} for k,v in receipt['artifact_sha256'].items()]))
print('Receipt saved:',OUT/'eda_receipt.json')
"""),
        md("""
### Giới hạn và câu hỏi còn mở

- TED-LIUM: metadata/nhãn đã quét toàn bộ; chưa giải mã 53 GB waveform hoặc kiểm tra trùng âm thanh.
- IIIT-CVID: toàn bộ frame/XML và header crop đã đọc; chưa giải mã đầy đủ từng crop hay xác nhận thủ công các cặp dHash.
- VidChapters: ID JSON đã đếm toàn bộ, nhưng `chapters.pkl` 2 GB chưa giải tuần tự an toàn; chỉ 8 video cục bộ.
- Video khác: metadata container đã đọc, chưa giải mã mọi frame. TVSum rỗng, SlideVQA thiếu ảnh.
- Phải quyết định nghiên cứu dùng split mới theo talk/course/video; các split gốc đã được dùng cho EDA nhãn tổng hợp.
"""),
    ]
    notebook = nbf.v4.new_notebook(cells=cells, metadata={
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}
    })
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    nbf.write(notebook, TARGET)
    print(TARGET)


if __name__ == "__main__":
    main()
