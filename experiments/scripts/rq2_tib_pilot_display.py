"""Human-readable pilot evidence, rendered directly in notebook output."""
import json
from pathlib import Path


def _table(headers, rows):
    def cell(value):
        if value is None:
            return 'chưa đo'
        if isinstance(value, float):
            return f'{value:.4f}'
        return str(value).replace('|', '\\|').replace('\n', ' ')
    return '\n'.join(['| '+' | '.join(map(cell, headers))+' |',
        '| '+' | '.join('---' for _ in headers)+' |',
        *['| '+' | '.join(map(cell, row))+' |' for row in rows]])


def pilot_report(receipt, *, forecast=None, dispatch_path=None):
    """Keep unattempted IDs and unknown costs visible; never infer model results."""
    selected = receipt['design']['selected']
    observed = {r['id']:r for r in receipt.get('rows', [])}
    rows = [{**s, **observed.get(s['id'], {'status':'not_attempted', 'arms':{}})} for s in selected]
    profile = receipt.get('identity', {}).get('profile', {})
    sections = ['# Báo cáo pilot TIB RQ2/RQ4',
        '**Development — chưa freeze cohort; điểm pilot không dùng để chọn mẫu S3 thắng.**',
        'Phạm vi: creator-abstract agreement trên văn bản; không chứng minh factuality hoặc lợi ích đa phương thức.',
        '## 1. Cấu hình và mẫu số',
        _table(['Thông tin', 'Giá trị'], [
            ['Pool ứng viên', receipt['design'].get('expected_full_pool_count')],
            ['Selected / observed / label-valid / media-valid / evaluated / failed',
             ' / '.join(str(receipt.get('counts', {}).get(k, 'chưa đo')) for k in
                        ('selected','observed','label_valid','media_valid','evaluated','failed'))],
            ['Evaluated ở trên', 'đã có paired ROUGE; xem coverage từng metric bên dưới'],
            ['Media-valid', '0: không audit media, không cần media cho claim text-only'],
            ['Label-valid', 'screen cấu trúc creator abstract; không phải factual GT đã xác minh'],
            ['Generator', profile.get('model')], ['Tokenizer', profile.get('tokenizer')],
            ['Cấu hình sinh', json.dumps(receipt.get('identity', {}).get('config', {}), ensure_ascii=False)],
            ['Package versions', json.dumps(profile.get('packages', {}), ensure_ascii=False)],
            ['GPU / map batch', f"{profile.get('gpu_name', 'chưa đo')} / {profile.get('map_batch_size', 'chưa đo')}"],
            ['Khởi tạo generator/data/notebook (giây)', receipt.get('initialization_seconds')],
            ['Khởi tạo semantic scorer (giây)', receipt.get('metric_initialization_seconds')],
            ['Cùng hardware giữa hai giai đoạn', receipt.get('metric_hardware_matches_generation')],
            ['Code SHA-256', receipt.get('identity', {}).get('code', {}).get('sha256')],
            ['Chọn mẫu theo nguồn SHA-256', receipt['design'].get('selection_source_sha256')]]),
        'Output caps trung gian/cuối được phân bổ bằng nhau; token thực dùng có thể khác. Retry tự động = 0. '
        'Deadline là soft stop giữa dispatch; resume/manual retry giữ lịch sử và chặn forecast đồng nhất.',
        '## 2. Coverage từng arm — mẫu số luôn là toàn bộ mẫu đã chọn',
        _table(['Arm', 'Thành công', 'Thất bại', 'Chưa hoàn tất/không chạy', 'Tổng selected'],
            [[a, sum(r.get('arms', {}).get(a, {}).get('status')=='completed' for r in rows),
              sum(r.get('arms', {}).get(a, {}).get('status')=='failed' for r in rows),
              sum(r.get('arms', {}).get(a, {}).get('status') not in ('completed','failed') for r in rows),
              len(selected)] for a in ('S1','S3')]),
        '## 3. Thời gian theo mẫu (giây)',
        _table(['ID','Nhóm','Token nguồn','Trạng thái','S1 wall','S3 wall','Shared prep','Chấm điểm','Checkpoint','Resume'],
            [[r['id'],r['length_stratum'],r['source_tokens'],r['status'],
              *[r.get('arms',{}).get(a,{}).get('wall_seconds') for a in ('S1','S3')],
              *[r.get(k) for k in ('shared_preparation_seconds','scoring_seconds','checkpoint_seconds','resumed')]] for r in rows])]
    resources, errors = [], []
    for r in rows:
        for a in ('S1','S3'):
            arm = r.get('arms', {}).get(a, {})
            known = arm.get('usage_complete') is True
            def tokens(key):
                value = arm.get(key)
                return value if known or value is None else f'>= {value} (chỉ phần đã biết)'
            def gib(key):
                value = arm.get(key)
                return value/(1024**3) if value is not None else None
            resources.append([r['id'],a,arm.get('chunk_count'),arm.get('segmentation_seconds'),
                arm.get('generation_seconds'),tokens('prompt_tokens'),tokens('output_tokens'),
                arm.get('generation_request_count'),arm.get('reported_attempt_count'),
                gib('peak_gpu_allocated_bytes'),gib('peak_gpu_reserved_bytes')])
            if arm.get('error'):
                errors.append([r['id'],a,arm.get('error_type'),arm['error']])
        for key in ('error','evaluation_error'):
            if r.get(key):
                errors.append([r['id'],'record',key,r[key]])
    sections += ['## 4. Token, dispatch và bộ nhớ từng arm',
        _table(['ID','Arm','Chunks','Phân đoạn s','Sinh s','Prompt tokens','Output tokens','Dispatch','Attempts trả về','Peak allocated GiB','Peak reserved GiB'], resources),
        'Token ở lần lỗi có thể chỉ là phần đã ghi nhận; không coi phần chưa biết là 0. '
        'VRAM là peak tuyệt đối của từng arm, không cộng hai peak. Prompt token không gồm compute do padding.',
        _table(['ID','Thứ tự arm','Common map output cap','Final output cap','Common prompt cap'],
            [[r['id'], ' → '.join(r.get('arm_order', [])), r.get('common_map_output_budget'),
              r.get('common_final_output_budget'),r.get('common_cumulative_prompt_budget')] for r in rows]),
        '## 5. Metric theo mẫu và paired delta S3−S1']
    metric_means = []
    for name, key in (('ROUGE-L F1','rouge'),('BERTScore F1','bertscore'),('Source SBERTScore','sbertscore')):
        scored = []
        values = []
        for r in rows:
            score = r.get('scores', {}) if key=='rouge' else r.get('semantic_scores', {}).get(key, {})
            if all(score.get(a) is not None for a in ('S1','S3','S3_minus_S1')):
                scored.append(score)
            values.append([r['id'],score.get('S1'),score.get('S3'),score.get('S3_minus_S1')])
        sections += [f'### {name} — paired scored {len(scored)}/{len(selected)}',
                     _table(['ID','S1','S3','S3−S1'], values)]
        metric_means.append([name,len(scored),len(selected),
            *[sum(s[k] for s in scored)/len(scored) if scored else None for k in ('S1','S3','S3_minus_S1')]])
    sections += [_table(['Metric','Paired scored','Selected','Macro S1','Macro S3','Mean delta'],metric_means),
        'ROUGE-L: Unicode word LCS, casefold, không stemming, F1 macro theo record. '
        'Metric thiếu không gán 0; mỗi metric có mẫu số riêng. Đây là mô tả pilot, không CI hoặc kết luận thắng. '
        'Source SBERTScore không phải phần trăm factuality.', '## 6. Lỗi và lần gọi thất bại']
    if dispatch_path and Path(dispatch_path).exists():
        for line in Path(dispatch_path).read_text(encoding='utf-8').splitlines():
            try:
                d = json.loads(line)
            except ValueError:
                errors.append(['dispatch log','unknown','parse_error','Dòng log không đầy đủ; không suy ra chi phí còn thiếu'])
                continue
            if d.get('status') in ('failed','empty_output'):
                errors.append([d.get('id'),d.get('arm'),d.get('status'),d.get('error','Output rỗng')])
    sections.append(_table(['ID','Arm/phạm vi','Loại','Chi tiết'],errors) if errors else 'Không có lỗi được ghi nhận trong receipt/log hiện có.')
    sections.append('## 7. Dự báo ngân sách 12 giờ')
    if not forecast or not forecast.get('credible_forecast'):
        sections += ['**Chưa đủ bằng chứng để dự báo hoặc chọn quy mô benchmark.**',
            _table(['Blocker'], [[b] for b in (forecast or {}).get('blockers', ['chưa tính forecast'])])]
    else:
        low, high = forecast['observed_scenario_range_seconds']
        sections += [_table(['Thông tin','Giá trị'],[
            ['Dự báo cho số mẫu',sum(forecast['population_by_stratum'].values())],
            ['Ước lượng (giờ)',forecast['predicted_seconds']/3600],
            ['Kịch bản min–max (giờ)',f'{low/3600:.2f} – {high/3600:.2f}'],
            ['Hệ số dự phòng',forecast['safety_factor']],
            ['Kịch bản cao nằm trong 12 giờ',forecast['within_budget']]]),
            _table(['Nhóm','Số mẫu mục tiêu','Chi phí trung bình cả hai arm + scoring + overhead (s/mẫu)'],
                [[s,n,forecast['planning_means_seconds'][s]] for s,n in forecast['population_by_stratum'].items()]),
            'Min–max là kịch bản quan sát, không phải khoảng tin cậy. Bao gồm khởi tạo, cả hai arm, '
            'chấm điểm, prep và checkpoint; cấu hình/lần lặp bổ sung cần đo riêng.']
    sections += ['## Thông tin cần gửi lại',
        '**Lưu notebook sau khi chạy với toàn bộ output, hoặc copy báo cáo này vào chat. Không cần mở/gửi JSON riêng.** '
        'Checkpoint JSON chỉ phục vụ resume và truy nguyên. Sau review mới chốt cohort/protocol; '
        'không tự chọn ID theo điểm, loại mẫu dài/lỗi, hay đưa 9 mẫu development vào đánh giá chính thức.']
    return '\n\n'.join(sections)


def show_pilot_report(receipt, *, forecast=None, dispatch_path=None):
    from IPython.display import Markdown, display
    report = pilot_report(receipt, forecast=forecast, dispatch_path=dispatch_path)
    display(Markdown(report))
    return report
