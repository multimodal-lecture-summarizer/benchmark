# YTSeg `xsO2Ip6eiaY`: đối chiếu quyền slide với video

**Ngày:** 2026-09-29. **Nguồn:** MP4 gốc MIT 16.687 Lecture 16 đã kiểm full-file ở [receipt media](./ytseg-260929-1543-reserve-b-media-receipt.json): 59.842.706 byte, SHA-256 `bfd2f8627a5b87590cf69322c6907556b1f0e7b6c22071fb2de01c48f43e9a75`. [Slide PDF chính thức](https://ocw.mit.edu/courses/16-687-private-pilot-ground-school-january-iap-2019/e4b23d5e512a88e29d0bb952d401f0e1_MIT16_687IAP19_Lec16.pdf) ghi một số hình `Source: Public Domain`; phần văn bản trích xuất không có câu `excluded from our Creative Commons license`. Điều đó chưa xác nhận quyền của **mọi nội dung video**.

## Phép kiểm và kết quả

Dùng FFmpeg lấy một frame mỗi 30 giây từ **0 đến 1440 giây** của video 1.474 giây, xếp 49 frame vào contact sheet cục bộ ignored (`experiments/datasets/ytseg_qualification/rights_audit/xsO2Ip6eiaY-30s-contact.png`, SHA-256 `8c89052561e79a8ef69eaf51f8519cd6453cea5e4f69247e9dd783f88fa9a244`). Xem thêm frame nguyên cỡ tại 210, 240, 840, 1230, 1260 giây. Contact sheet/khung hình **không nằm trong gói báo cáo phát hành**.

| Mốc | Quan sát trực tiếp | Hệ quả quyền |
|---:|---|---|
| 210 s | Slide `Get on the Step` có liên kết YouTube | Liên kết riêng chưa chứng minh clip được phát hoặc có quyền cho clip |
| 240 s | Trong MP4 xuất hiện cảnh máy bay đang bay trên nước từ một cửa sổ video, ngoài nội dung slide PDF tĩnh | Cần nguồn và quyền đoạn video này; không thể suy từ nhãn Public Domain ở hình khác trong PDF |
| 840 s | Slide có thêm các liên kết video minh họa | Không tự suy các video được nhúng đều đã cấp phép |
| 1260 s | Trình duyệt hiển thị trang sản phẩm SeaRey kèm nhiều ảnh máy bay | Cần phạm vi quyền ảnh/giao diện trang; không được tự xem như tài sản do MIT cấp phép |

**Quyết định:** `publisher_terms_conditional` cho phần OCW thuộc phạm vi; `hold_full_video_research_component_scope` với phép xử lý toàn video đa phương thức đã chốt; `hold_redistribution` riêng. PDF không có câu loại trừ trong text **không** đủ để nâng resource lên `pass`. Phép lấy mẫu 30 giây có thể bỏ sót nội dung ngắn, nên các mốc này là bằng chứng có thành phần cần giải quyết, không phải kiểm kê đầy đủ.

## Câu hỏi chưa giải quyết

1. Nguồn và điều khoản của đoạn seaplane video tại khoảng 240 giây và ảnh/trang SeaRey khoảng 1260 giây là gì?
2. Có bằng chứng nào từ MIT OCW hoặc chủ sở hữu cho phép xử lý các thành phần đó trong nghiên cứu đa phương thức phi thương mại không?
