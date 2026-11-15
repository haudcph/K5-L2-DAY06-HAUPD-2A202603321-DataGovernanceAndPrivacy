# Metric contract (khai báo bắt buộc — chốt ở phút 30, trước khi chạy eval)

| Mục | Khai báo của nhóm |
|---|---|
| Track | T02 — Raw QC Triage |
| Primary metric | Defect Recall@B (B=20, eval split) + Precision@B |
| Tăng tốt hay giảm tốt? | higher (càng cao càng tốt) |
| Đơn vị đánh giá | image |
| Công thức | Defect Recall@20 = # ảnh lỗi GT trong top-20 / # tổng ảnh lỗi GT trong eval |
| Review budget B | 20 ảnh |
| Seed | 42 |
| Threshold policy (chọn trên DEV) | **Hiệu chuẩn hoàn toàn trên split DEV**:<br>- Blur: Chuẩn hóa theo camera_id (`cam_A` thr=250, `cam_B` thr=100) do `cam_B` quang học mềm (median dev `cam_A`=870, `cam_B`=235).<br>- Dark: `p95 < 65` và `mean < 25` (tránh nhầm ảnh ban đêm sạch vì ảnh đêm sạch có đèn đường $p95 > 100$).<br>- Glare: Phát hiện cụm cháy sáng cục bộ $area \ge 200$ px với $pixel > 240$.<br>- Compression: Đo gradient 2D $min(block_h, block_v) > 1.8$ (loại trừ texture 1 chiều). |
| Eval split | eval (40 ảnh, không dùng để tune threshold) |
| Chỉ số lỗi xấu | False alarm in top-B theo lát cắt `light` (day, dusk, night) |
| Slices báo cáo | `light` (day, dusk, night) và `camera_id` (cam_A, cam_B) |
| Người chốt | Hau Pham (ML Engineer) |