"""Build the actual all-split CVID EDA notebook; execution is a separate command."""
from pathlib import Path
import inspect

import nbformat as nbf

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT/'experiments/notebooks/diagnostics/iiit-cvid-all-splits-eda.ipynb'


def build():
    cells = []
    def md(text): cells.append(nbf.v4.new_markdown_cell(inspect.cleandoc(text)))
    def code(text): cells.append(nbf.v4.new_code_cell(inspect.cleandoc(text)))

    md('''# CVID — EDA toàn bộ train / validation / test
    Quét trực tiếp ZIP đã khóa hash; không chạy OCR, không sửa GT và không khóa cohort test.
    Bao phủ toàn bộ frame, object XML và crop; các review trực quan được kiểm tra identity/hash trước khi hiển thị.
    Test đã được quan sát trong EDA. Kết quả hỗ trợ đánh giá theo nhãn phát hành; không chứng nhận nhãn hoàn hảo, video/người viết độc lập hoặc test mù.
    ''')
    code('''from pathlib import Path
    import sys, json, itertools
    import pandas as pd
    from IPython.display import display, Markdown, Image, HTML
    options = [Path.cwd(), Path.cwd()/'benchmark', *Path.cwd().parents]
    ROOT = next(p for p in options if (p/'experiments/scripts/cvid_eda_scan.py').is_file())
    sys.path.insert(0,str(ROOT))
    from experiments.scripts.cvid_eda_scan import scan
    from experiments.scripts.cvid_eda_common import OUT, sha, validate_artifacts, normalize_text
    from experiments.scripts.cvid_eda_plots import *
    from experiments.scripts.cvid_eda_notebook_support import table, figure, gallery, video_metadata, verify_reviews, finish
    pd.set_option('display.max_colwidth',None)
    snapshot = {p.relative_to(ROOT).as_posix():sha(p) for p in (ROOT/'experiments/registry/datasets').glob('iiit-cvid-spotting-*.json')}
    print('Existing spotting artifacts bound:',len(snapshot),'| No model inference/imports or dependency installation')
    ''')
    md('''## 1. Thu thập và đối chiếu toàn bộ nguồn
    Cell sau thực sự giải mã toàn bộ frame/crop và đọc mọi XML. Hash pixel RGB + kích thước + nhãn tương thích được đối chiếu trong từng source group, có kiểm tra multiplicity.
    Nhãn XML giữ nguyên. Thay `/` thành `-` chỉ là phép đối chiếu với crop index, không phải normalization của spotting.
    ''')
    code('''receipt = scan()
    validate_artifacts(receipt)
    assert (receipt['frames'],receipt['objects'],receipt['decoded_crops']) == (5475,137745,137745)
    assert receipt['read_failures']==receipt['unmatched_objects']==0
    print(json.dumps({k:v for k,v in receipt.items() if k not in ('artifacts','scripts')},indent=2))
    data = load_tables()
    f,o,c,meta = [data[k] for k in ('frames','objects','crops','courses')]
    assert len(c)==c.crop_id.nunique() and len(o)==o.object_id.nunique()
    assert c.assigned_object_id.nunique()==len(o)
    from experiments.scripts.cvid_eda_galleries import prepare_galleries
    gallery_receipt = prepare_galleries()
    ''')
    md('''## 2. Accounting và thành phần split
    ZIP và train index cùng có 3.171 frame train, trong khi paper ghi 3.170; không tự loại một frame để ép khớp paper.
    Mỗi object là một annotation text/word do nguồn phát hành; không mặc định là một dòng chữ hay một mẫu độc lập.
    ''')
    code('''counts = pd.DataFrame({'frames':f.groupby('split').size(),'xml_objects':o.groupby('split').size(),
        'nonblank_gt':o.groupby('split').transcription_nonblank.sum(),'decoded_crops':c.groupby('split').size(),
        'courses':f.groupby('split').course.nunique(),'folder_video_groups':f.groupby('split').source_group.nunique()}).reindex(SPLITS).reset_index()
    table(counts,'split-accounting')
    figure(plot_counts(data),'01-accounting')
    ''')
    code('''table(meta,'all-course-metadata')
    course_counts = f.groupby(['split','course','medium']).agg(frames=('frame_id','size'),objects=('objects','sum'),video_groups=('source_group','nunique')).reset_index()
    table(course_counts,'course-concentration')
    figure(plot_courses(data),'02-courses-and-concentration')
    ''')
    code('''table(f.groupby('split')[['objects','width','height']].describe().round(2).reset_index(),'frame-distribution-summary')
    table(f.groupby(['split','source_group']).agg(frames=('frame_id','size'),objects=('objects','sum')).reset_index(),'all-video-group-counts',preview=18)
    figure(plot_density(data),'03-text-density')
    figure(plot_modalities(data),'04-course-medium')
    ''')
    md('''## 3. Độ phân giải, hình học và annotation bất thường
    Medium là metadata cấp khóa học; `Mixed` giữ nguyên, không suy diễn thành nhãn từng frame.
    KEEP/REPAIR/HOLD là kết quả kiểm tra cấu trúc, không chứng nhận transcription đúng về ngữ nghĩa.
    ''')
    code('''table(f.groupby(['split','width','height']).size().reset_index(name='frames'),'all-resolution-strata')
    figure(plot_resolution(data),'05-frame-resolution')
    decisions = pd.crosstab(f.split,f.decision).reindex(SPLITS).reset_index()
    table(decisions,'frame-quality-decisions')
    table(o[~o.geometry_valid][['object_id','text','xmin','ymin','xmax','ymax','frame_id']],'all-invalid-boxes')
    table(f[f.xml_size_mismatch][['frame_id','xml_width','xml_height','width','height','decision']],'all-metadata-size-mismatches')
    figure(plot_boxes(data),'06-box-geometry')
    ''')
    code('''gallery('geometry-contact-sheets')
    eligible = f[f.decision!='HOLD'].groupby('split').agg(frames=('frame_id','size'),objects=('objects','sum')).reindex(SPLITS).reset_index()
    table(eligible,'mechanically-eligible-not-frozen')
    display(Markdown('Metadata repair chỉ dùng kích thước PNG trong derived records. Không clip box. Test còn 1.754 frame / 40.063 object về hình học; chưa khóa cohort.'))
    ''')
    md('''## 4. Crop/frame correspondence và transcription
    `unique` là đối ứng duy nhất theo pixel + nhãn trong source group. `equivalent_ambiguous` có nhiều object trùng pixel/nhãn: allocation chỉ phục vụ kiểm multiplicity, không chứng minh object ID mà tác giả định dùng.
    ''')
    code('''table(c.groupby(['split','correspondence']).size().reset_index(name='crops'),'crop-correspondence-counts')
    table(c[c.correspondence!='unique'][['crop_id','text','xml_text','equivalence_class_size','assigned_object_id','correspondence']],'all-ambiguous-correspondence')
    figure(plot_crops(data),'07-crop-resolution-and-correspondence')
    ''')
    code('''table(o.groupby('split')[['characters','box_height','box_height_rel','area_rel','aspect_ratio']].describe().round(4).reset_index(),'object-feature-summary')
    table(o.sort_values(['characters','object_id'],ascending=[False,True])[['object_id','text','normalized_text','characters']].head(24),'longest-xml-label-examples')
    figure(plot_text(data),'08-transcription-length-and-composition')
    ''')
    code('''diff = c[c.raw_label_differs].copy()
    diff['xml_normalized'] = diff.xml_text.map(normalize_text)
    diff['crop_normalized'] = diff.text.map(normalize_text)
    diff['slash_rewrite_explains'] = diff.xml_normalized.str.replace('/','-',regex=False)==diff.crop_normalized
    assert len(diff)==238 and diff.slash_rewrite_explains.all()
    table(diff[['crop_id','assigned_object_id','xml_text','text','xml_normalized','crop_normalized','slash_rewrite_explains']],'all-238-crop-xml-label-differences')
    table(diff.groupby('split').size().reset_index(name='label_differences'),'transcription-source-differences-by-split')
    print('Spotting GT remains raw XML. Recognition results retain their original crop-index references.')
    figure(plot_vocabulary(data),'09-vocabulary-overlap')
    ''')
    md('''## 5. Chất lượng ảnh — proxy và gallery
    Grayscale SD và Laplacian variance là mô tả cường độ/cạnh, chưa hiệu chuẩn theo độ đọc được hoặc OCR accuracy. Không dùng các proxy để loại test frame hay chọn model.
    Các gallery QC ở dưới có đủ mẫu cho 24 khóa học, gồm các vùng chữ nhỏ/trung bình/lớn theo quy tắc đã khai báo trước review.
    ''')
    code('''table(c.groupby('split')[['gray_std','laplacian_variance','width','height']].describe().round(3).reset_index(),'crop-image-proxy-summary')
    figure(plot_quality(data),'10-intensity-and-edge-proxies')
    ''')
    md('''## 6. Trùng lặp và review toàn bộ hàng đợi gần trùng
    Exact duplicate của frame và lặp crop/word là hai hiện tượng khác nhau. Từ/crop giống nhau không tự chứng minh trùng video.
    Tất cả 469 cặp dHash<=6 đã được xem trực quan; quyết định chỉ giải quyết hàng đợi này, không chứng nhận recall của phép sàng lọc hoặc độc lập nguồn.
    ''')
    code('''assert not f.image_sha256.duplicated().any() and not f.pixel_key.duplicated().any()
    duplicates = c.groupby('pixel_key').agg(crops=('crop_id','size'),splits=('split','nunique'),label_variants=('normalized_text','nunique')).reset_index()
    table(duplicates[duplicates.crops>1],'all-exact-crop-pixel-repeat-groups',preview=24)
    pairs,semantic = verify_reviews(f,o)
    rows = f[['frame_id','split','dhash']].to_dict('records')
    screened = {tuple(sorted((a['frame_id'],b['frame_id']))) for i,a in enumerate(rows) for b in rows[i+1:]
        if a['split']!=b['split'] and (int(a['dhash'],16)^int(b['dhash'],16)).bit_count()<=6}
    assert screened=={tuple(sorted((r.left,r.right))) for r in pairs.itertuples()}
    table(pairs.groupby('decision').size().reset_index(name='pairs'),'visual-pair-review-summary')
    table(pairs[['pair_id','left','right','decision','rationale','uncertainty']],'all-469-pair-adjudications')
    ''')
    code("gallery('pair-contact-sheets')")
    md('''## 7. Diagnostic semantic GT QC
    Quy tắc chọn: 3 object mỗi khóa học, gần quantile 10/50/90% của box-height/frame-height, tie-break theo object ID, không thay thế mẫu. Review toàn bộ 72 crop và context bằng hai lượt Codex vision; không phải human gold hay mẫu ngẫu nhiên để ước lượng error rate toàn dataset.
    `apparent_disagreement` và `uncertain` giữ nguyên GT, không tự tạo nhãn mới hoặc loại frame. Annotation recall không được chứng nhận: paper loại equations/symbols và các ví dụ cho thấy logo/interface được chọn không đồng nhất.
    ''')
    code('''table(semantic[['sample_id','object_id','split','course','xml_text','decision','rationale','context_completeness']],'all-72-semantic-reviews')
    table(semantic.groupby(['split','decision']).size().reset_index(name='sampled_objects'),'semantic-review-counts')
    table(semantic[semantic.decision!='visually_consistent_at_review_resolution'],'semantic-flags-requiring-gt-policy')
    gallery('semantic-contact-sheets')
    display(Image(filename=str(OUT/'semantic-focused-review.png')))
    ''')
    md('''## 8. Provenance, writer overlap và test exposure
    Nguồn phương pháp: [paper tác giả, Section III và Table II](https://cdn.iiit.ac.in/cdn/cvit.iiit.ac.in/images/ConferencePapers/2018/localizing-recognizing-text.pdf).
    Khóa học tách biệt không tự chứng minh người viết tách biệt. Tên file media không tự là source-video URL.
    Các receipt lịch sử cho thấy test đã được đọc trong EDA; OCR comparison được kiểm tra có phạm vi validation crops. Chưa chứng minh mọi model run lịch sử đã được kiểm kê; EDA exposure không tự chứng minh test-based tuning.
    ''')
    code('''videos = video_metadata()
    assert len(videos)==811 and videos.complete_name.ne('').all()
    table(videos,'all-811-video-metadata')
    overlap = meta[meta.Instructor.str.contains('Erik Demaine',case=False,regex=False)]
    table(overlap,'declared-instructor-overlap-train-val')
    separation=[]
    for a,b in itertools.combinations(SPLITS,2):
        separation.append(dict(left=a,right=b,shared_course_ids=len(set(f[f.split==a].course)&set(f[f.split==b].course)),
            shared_group_ids=len(set(f[f.split==a].source_group)&set(f[f.split==b].source_group))))
    table(pd.DataFrame(separation),'release-identifier-separation')
    display(Markdown('811 nhóm có local media filename; chưa có authenticated per-video mapping. Course URLs và metadata chỉ hỗ trợ course-level linkage. Erik Demaine được khai báo ở train/1, train/5, val/6. Không tuyên bố writer-disjoint.'))
    ''')
    md('''## 9. Kết luận, khả năng dùng test và artifacts
    EDA kỹ thuật bao phủ toàn bộ dữ liệu và đã hoàn thành review hàng đợi/mẫu QC. Native test phù hợp để thiết kế endpoint course-held-out theo nhãn phát hành.
    **Chưa khóa cohort test:** cần khai báo cách xử lý semantic flags và annotation scope; chưa xác minh độc lập video/người viết, lịch sử model test-use đầy đủ hay pretrained overlap. Không gộp train/val vào final test, không chọn thresholds/weights từ test observations.
    ''')
    code('''summary = finish(receipt,pairs,semantic,snapshot)
    print(json.dumps({k:v for k,v in summary.items() if k not in ('artifacts','code_sha256','existing_spotting_freeze_sha256')},indent=2,ensure_ascii=False))
    export_rows = pd.DataFrame(summary['artifacts'])
    display(HTML(export_rows[['path','sha256']].to_html(index=False,escape=True)))
    print('Full CSV/GZIP ledgers:',OUT)
    print('No source/spotting-freeze mutations; no OCR inference; no test cohort freeze.')
    ''')
    nb = nbf.v4.new_notebook(cells=cells,metadata=dict(kernelspec=dict(display_name='Python 3',language='python',name='python3'),
        language_info=dict(name='python',version='3.11'),cvid_scope='all_train_val_test_eda_no_model_inference'))
    nbf.validate(nb)
    for i,cell in enumerate(nb.cells):
        if cell.cell_type=='code': compile(cell.source,f'cvid-eda-cell-{i}','exec')
    TARGET.parent.mkdir(parents=True,exist_ok=True); nbf.write(nb,TARGET)
    return TARGET


if __name__=='__main__':
    print(build())
