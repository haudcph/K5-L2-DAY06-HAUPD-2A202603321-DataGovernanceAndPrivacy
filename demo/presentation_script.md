# KỊCH BẢN THUYẾT TRÌNH LIVE DEMO 5 PHÚT (DAY 06 · TRACK T02)
> Khung thời gian chuẩn 300 giây (5 phút), phân chia rõ vai trò, lời thoại và thao tác trên màn hình cho nhóm G07.

---

## ⏱️ Timeline Tổng Quan (Khung 5 Phút)
* **0:00 - 0:30 (30s)**: Slide 0 · Giới thiệu nhóm & phân vai
* **0:30 - 1:15 (45s)**: Slide 1 · Bước 01: Nêu bài toán & Risk Gate (Trưởng nhóm: Phạm Đức Hậu)
* **1:15 - 1:50 (35s)**: Slide 2 · Bước 02: Mở mẫu đầu vào & Provenance (Phụ trách Dữ liệu)
* **1:50 - 2:50 (60s)**: Slide 3 · Bước 03: Cơ chế & Cách Model hoạt động (Phụ trách Xử lý / Core)
* **2:50 - 3:35 (45s)**: Slide 4 · Bước 04: Trải nghiệm duyệt trực tiếp (Người duyệt: Nguyễn Tuấn Dũng)
* **3:35 - 4:20 (45s)**: Slide 5 · Bước 05: Chạy lại, kiểm thay đổi & Audit Log (Chạy + Kiểm tra)
* **4:20 - 5:00 (40s)**: Slide 6 · Bước 06: Hiệu quả, Ca khó & Hướng mở rộng (Thử nghiệm ca khó)

---

## 🎙️ Lời Thoại & Thao Tác Chi Tiết Từng Phút

### [0:00 - 0:30] MỞ ĐẦU & PHÂN VAI (Trưởng nhóm)
* **Chiếu Slide 0**:
  > *"Kính chào thầy và các bạn. Hôm nay nhóm G07 xin trình diễn Live Demo trong 5 phút về giải pháp **Track T02: Raw QC Triage (Ảnh mờ, lóa và thiếu sáng)** trong pipeline dữ liệu xe tự hành. Nhóm gồm 6 thành viên đảm nhận đúng 6 vai trò theo yêu cầu của môn học."*

---

### [0:30 - 1:15] BƯỚC 01 · NÊU BÀI TOÁN (Phạm Đức Hậu - Lead)
* **Chiếu Slide 1**:
  > *"Bài toán đặt ra: Camera xe tự hành gửi về hàng triệu ảnh. Những ảnh bị mờ nét, lóa đèn pha, tối đen hầm hay vỡ nén JPEG sẽ làm model AI nhận diện sai, gây tai nạn nguy hiểm. Tuy nhiên, chi phí không cho phép thuê người soi thủ công cả triệu ảnh. Ngân sách con người bị giới hạn ở **Budget B = 20 ảnh**.*
  > *Mục tiêu của nhóm: Tối đa hóa **Defect Recall@20** trên tập eval. Đồng thời thiết lập một **Cổng an toàn (Risk Gate)**: Hệ thống sẽ luôn ở trạng thái **HOLD** khi chưa có đủ 20 lượt duyệt của chuyên viên, và chỉ chuyển sang **GO** khi đã kiểm toán minh bạch."*

---

### [1:15 - 1:50] BƯỚC 02 · MẪU ĐẦU VÀO & PROVENANCE (Phụ trách Dữ liệu)
* **Chiếu Slide 2** (Mở terminal gõ `make verify` và mở ảnh `img_17_2.jpg`):
  > *"Bộ dữ liệu của nhóm gồm 96 ảnh được xác thực toàn vẹn bằng SHA256 qua lệnh `make verify`, chia thành tập `dev` (56 ảnh để hiệu chuẩn ngưỡng) và `eval` (40 ảnh chấm điểm độc lập).*
  > *Đây là mẫu ảnh `img_17_2` thuộc tập eval chụp bằng `cam_A`. Khi mặt trời chiếu thẳng vào kính, ảnh bị lóa (Glare) nghiêm trọng làm mất hoàn toàn chi tiết biển số xe. Nhiệm vụ của máy là phải phát hiện ra vết lóa này và đưa ảnh lên Top 1 hàng chờ duyệt."*

---

### [1:50 - 2:50] BƯỚC 03 · KIẾN TRÚC & CƠ CHẾ HOẠT ĐỘNG CỦA MODEL (Phụ trách Xử lý)
* **Chiếu Slide 3** *(Slide mới về thuật toán)*:
  > *"Thay vì dùng Baseline đơn giản chỉ đo 1 ngưỡng Laplacian toàn ảnh (rất dễ bị mù lóa và nhầm ảnh đêm), nhóm em xây dựng **Cổng phát hiện lỗi đa đặc trưng (Multi-Feature Anomaly Gate)** gồm 4 cảm biến:*
  > *1. **Cảm biến Mờ**: Chuẩn hóa ngưỡng Laplacian theo từng camera trên tập DEV (`cam_A` = 250, `cam_B` = 100 do `cam_B` quang học mềm).*
  > *2. **Cảm biến Tối**: Đo phân vị $P_{95}$. Ảnh đêm sạch có đèn đường nên $P_{95} > 100$. Máy chỉ phạt khi cả $P_{95} < 65$ và $mean < 25$.*
  > *3. **Cảm biến Lóa**: Tìm cụm pixel bão hòa $> 240$ có diện tích $\ge 200$ px và tự động vẽ Bounding Box màu vàng.*
  > *4. **Cảm biến Nén vỡ JPEG**: Đo gradient 2 chiều $min(Block_H, Block_V) > 1.8$ để triệt tiêu việc báo nhầm texture sọc 1 chiều.*
  > *Điểm tổng được tính bằng hàm MAX kết hợp vi sai Tie-breaker, giúp 40/40 ảnh eval có thứ hạng phân biệt rõ ràng."*

---

### [2:50 - 3:35] BƯỚC 04 · DUYỆT MỘT MỤC (Nguyễn Tuấn Dũng - Reviewer)
* **Chiếu Slide 4** (Mở web `out/poc/contact_sheet.html`):
  > *"Em là Nguyễn Tuấn Dũng, đóng vai trò Reviewer. Trên giao diện web, hệ thống đã xếp 20 ảnh nguy ngờ nhất của tập eval. Thầy có thể thấy ảnh lóa `img_17_2` được đóng khung vàng đánh dấu chính xác vùng cháy sáng.*
  > *Tại mục số 8: ảnh `img_15_3`. Máy tính chấm điểm cao và đề xuất `RECAPTURE` vì thấy ảnh hơi tối lúc hoàng hôn. Nhưng bằng mắt nhìn thực tế, em thấy biển số và xe vẫn rất rõ nét. Vì vậy em chọn **`reject`** (bác bỏ đề xuất lỗi) và ghi chú lý do là `Dark`. Sau đó em bấm **Export decisions CSV** để tải file về."*

---

### [3:35 - 4:20] BƯỚC 05 · CHẠY LẠI, KIỂM THAY ĐỔI & AUDIT (Chạy + Kiểm tra)
* **Chiếu Slide 5** (Mở terminal chạy `make run TRACK=t02`, mở `audit_log.jsonl` và `decision.json`):
  > *"Sau khi nạp file review của bạn Dũng, em chạy lại lệnh `make run TRACK=t02`. Bây giờ đối chiếu đúng mục `img_15_3`:*
  > *- Trước review: Action là `RECAPTURE`, điểm nghi ngờ là `0.855`.*
  > *- Sau review: Action đã đổi thành **`KEEP`**, điểm số hạ xuống `0.0001` để loại khỏi danh sách lỗi.*
  > *Mọi thay đổi này được lưu vết bất biến trong `audit_log.jsonl` có đầy đủ tên reviewer, hành động override, lý do.*
  > *Đặc biệt, trong file `decision.json`, Cổng an toàn tự động chuyển từ **`HOLD` sang `GO`** với chữ ký của Trưởng nhóm Phạm Đức Hậu: ghi nhận 34 ảnh RECAPTURE và 62 ảnh KEEP."*

---

### [4:20 - 5:00] BƯỚC 06 · HIỆU QUẢ, CA KHÓ & HƯỚNG MỞ RỘNG (Thử nghiệm ca khó)
* **Chiếu Slide 6**:
  > *"Về hiệu quả: Pipeline chạy hoàn toàn offline trên CPU siêu nhanh (~0.7ms/ảnh), bắt trọn 100% các ca Glare và nén JPEG mà Baseline chịu thua.*
  > *Về ca khó: Khi đốm lóa ở quá xa có diện tích $< 200$ px (như đèn pha xe cách 50m), máy có thể nhầm với đèn đường bình thường nên bỏ sót.*
  > *Hướng phát triển: Khi đưa lên môi trường có GPU (như Google Colab), nhóm sẽ tích hợp model Zero-Shot CLIP hoặc Transformer MUSIQ để chấm điểm chất lượng ảnh theo ngữ nghĩa sâu hơn.*
  > *Nhóm G07 xin kết thúc phần trình diễn trong đúng 5 phút. Cảm ơn thầy và các bạn đã lắng nghe!"*
