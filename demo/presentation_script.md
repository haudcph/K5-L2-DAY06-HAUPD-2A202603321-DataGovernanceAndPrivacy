# KỊCH BẢN THUYẾT TRÌNH LIVE DEMO 5 PHÚT (DAY 06 · TRACK T02)
> Khung thời gian chuẩn 300 giây (5 phút), phân chia rõ vai trò, lời thoại và thao tác trên màn hình cho 5 thành viên nhóm G07.

---

## ⏱️ Timeline Tổng Quan (Khung 5 Phút)
* **0:00 - 0:30 (30s)**: Slide 0 · Giới thiệu nhóm & phân vai (Trưởng nhóm: Phạm Đức Hậu)
* **0:30 - 1:15 (45s)**: Slide 1 · Bước 01: Nêu bài toán & Risk Gate (Trưởng nhóm: Phạm Đức Hậu)
* **1:15 - 1:50 (35s)**: Slide 2 · Bước 02: Mở mẫu đầu vào & Provenance (Phụ trách Dữ liệu: Trần Khánh Chi)
* **1:50 - 2:50 (60s)**: Slide 3 · Bước 03: Cơ chế mô hình RAM-QC & 5 điểm cải tiến (Phụ trách Xử lý: Khưu Minh Phú)
* **2:50 - 3:35 (45s)**: Slide 4 · Bước 04: Trải nghiệm duyệt trực tiếp trên Web UI (Người duyệt: Nguyễn Tuấn Dũng)
* **3:35 - 4:20 (45s)**: Slide 5 · Bước 05: Chạy lại, kiểm thay đổi & Audit Log (Chạy + Kiểm tra: Phạm Đức Hậu & Nguyễn Phương Nga)
* **4:20 - 5:00 (40s)**: Slide 6 · Bước 06: Hiệu quả, Bảng so sánh, Ca khó & Giới hạn (Kiểm tra & Ca khó: Nguyễn Phương Nga)

---

## 🎙️ Lời Thoại & Thao Tác Chi Tiết Từng Bước

### [0:00 - 0:30] MỞ ĐẦU & PHÂN VAI (Phạm Đức Hậu - Trưởng nhóm)
* **Chiếu Slide 0**:
  > *"Kính chào thầy và các bạn. Hôm nay nhóm G07 xin trình diễn Live Demo trong đúng 5 phút về giải pháp **Track T02: Raw QC Triage (Sàng lọc ảnh lỗi camera mờ, lóa, tối và nén vỡ)** trong pipeline dữ liệu xe tự hành. Nhóm gồm 5 thành viên đảm nhận đúng các vai trò quy chuẩn:*
  > *- Em là **Phạm Đức Hậu** (2A202603321) — Trưởng nhóm, điều phối và tích hợp pipeline.*
  > *- Bạn **Trần Khánh Chi** (2A202603338) — Phụ trách dữ liệu và kiểm toán provenance.*
  > *- Bạn **Khưu Minh Phú** (2A202603337) — Phụ trách thuật toán xử lý lõi RAM-QC.*
  > *- Bạn **Nguyễn Tuấn Dũng** (2A202603345) — Người duyệt thực hiện thẩm định trực quan.*
  > *- Bạn **Nguyễn Phương Nga** (2A202603335) — Phụ trách kiểm tra, đánh giá chỉ số và thử nghiệm ca khó."*

---

### [0:30 - 1:15] BƯỚC 01 · NÊU BÀI TOÁN (Phạm Đức Hậu - Lead)
* **Chiếu Slide 1**:
  > *"Camera xe tự hành gửi về hàng triệu khung hình mỗi ngày. Nếu các ảnh bị mờ chuyển động, lóa đèn pha, tối đen hay vỡ hình do nén JPEG lọt vào tập huấn luyện, mô hình AI sẽ học sai đặc trưng và gây tai nạn nghiêm trọng trên đường thực tế. Nhưng chi phí chuyên gia có hạn, ngân sách kiểm toán con người bị giới hạn cứng ở **Budget B = 20 ảnh** trên tập eval.*
  > *Mục tiêu kỹ thuật của nhóm: Tối đa hóa **Defect Recall@20** để bắt trọn nhiều ảnh hỏng nhất vào 20 suất duyệt. Đồng thời thiết lập một **Cổng an toàn (Risk Gate)**: Hệ thống mặc định ở trạng thái **HOLD** khi chưa duyệt đủ 20 ảnh, và chỉ tự động chuyển sang **GO** khi đã kiểm toán minh bạch 100%."*

---

### [1:15 - 1:50] BƯỚC 02 · MẪU ĐẦU VÀO & PROVENANCE (Trần Khánh Chi - Dữ liệu)
* **Chiếu Slide 2** (Mở terminal gõ `.venv/bin/python -m tools.verify_manifests` và chỉ vào ảnh `img_17_2.jpg`):
  > *"Em là Khánh Chi. Bộ dữ liệu của nhóm gồm 96 ảnh được xác thực toàn vẹn bằng SHA256 qua lệnh `tools.verify_manifests` — kết quả 14/14 manifest đều OK, không có byte dữ liệu nào bị sai lệch.*
  > *Dữ liệu được chia tách nghiêm ngặt theo scene: `dev` (56 ảnh để hiệu chuẩn tham số) và `eval` (40 ảnh chấm điểm độc lập).*
  > *Đây là mẫu ảnh `img_17_2` thuộc tập eval của camera `cam_A`. Khi đi dưới nắng gắt, vầng sáng mặt trời rọi thẳng gây lóa (Glare) nghiêm trọng che khuất biển số xe và làn đường. Hệ thống phải phát hiện chính xác vùng lóa này và đưa ảnh lên vị trí ưu tiên số 1 của hàng đợi duyệt."*

---

### [1:50 - 2:50] BƯỚC 03 · CƠ CHẾ MÔ HÌNH RAM-QC & 5 ĐIỂM CẢI TIẾN (Khưu Minh Phú - Xử lý)
* **Chiếu Slide 3** *(Giải thích cấu trúc thuật toán mới RAM-QC)*:
  > *"Em là Minh Phú. Tiếp thu ý kiến phản biện từ buổi trước, nhóm đã thiết kế mô hình mới **RAM-QC (ROI-Adaptive Multi-Feature QC)** giải quyết triệt để 5 hạn chế:*
  > *1. **Lọc 3 tầng (3-Tier Triage)**: Phân rõ `auto-KEEP` (<0.15), `REVIEW` (0.15 - 0.85), và `auto-RECAPTURE` (>=0.85) với ngưỡng khóa cứng trên dev, giúp hệ thống scale mượt mà khi dữ liệu tăng gấp 10 lần.*
  > *2. **Công thức gộp đa lỗi**: $Score = \max(s_i) + 0.05 \cdot \sum s_j + \delta_{\text{tie}}$, ghi nhận tường minh mọi lỗi trong reason.*
  > *3. **Chuẩn hóa lát cắt**: `cam_B` có ống kính quang học mềm tự nhiên (Laplacian dev ~235 so với `cam_A` ~955) nên ngưỡng mờ được hạ xuống 90 để không bị báo động giả; ban đêm dùng ngưỡng kép $P_{95} < 65$ và $mean < 25$ để phân biệt ảnh đêm sạch có đèn xe.*
  > *4. **Phát hiện lóa nhỏ**: Bắt được các cụm bão hòa diện tích chỉ từ $\ge 20$ px.*
  > *5. **Trọng số không gian ROI (Spatial ROI Prior)**: Vùng bầu trời ($y < 0.35H$) chỉ chịu trọng số $0.35$ nên lóa to không bị phạt oan; còn hành lang lái xe mặt đường ($y \ge 0.35H$) chịu trọng số gấp 5 lần ($1.85$), giúp bắt ngay các đốm lóa nguy hiểm chiếu vào xe cộ!"*

---

### [2:50 - 3:35] BƯỚC 04 · DUYỆT MỘT MỤC (Nguyễn Tuấn Dũng - Reviewer)
* **Chiếu Slide 4** (Mở trình duyệt xem file `out/poc/contact_sheet.html`):
  > *"Em là Tuấn Dũng, đóng vai trò Reviewer. Trên giao diện web Contact Sheet offline, hệ thống tự động lọc ra đúng 20 ảnh rủi ro cao nhất của tập eval. Tại các ca bị lóa như `img_17_2`, thuật toán tự vẽ khung chữ nhật màu vàng đóng đúng vị trí vết lóa.*
  > *Tại mục số 8: ảnh `img_15_3`. Máy tính chấm điểm cao và đề xuất `RECAPTURE` vì thấy hơi tối lúc hoàng hôn. Nhưng qua mắt nhìn thẩm định, em thấy vạch kẻ đường và xe cộ phía trước vẫn nhìn rất rõ ràng, không gây nguy hiểm. Vì vậy em chọn **`reject`** (bác bỏ đề xuất lỗi để giữ lại ảnh) và ghi chú lý do là `Dark`. Sau đó em bấm nút **Export decisions CSV** để lưu file `review_queue_reviewed.csv`."*

---

### [3:35 - 4:20] BƯỚC 05 · CHẠY LẠI, KIỂM THAY ĐỔI & AUDIT (Phạm Đức Hậu & Nguyễn Phương Nga)
* **Chiếu Slide 5** (Mở terminal chạy `make run TRACK=t02`, xem `audit_log.jsonl` và `decision.json`):
  > *"Sau khi bạn Dũng hoàn tất duyệt, em chạy lại lệnh `make run TRACK=t02`. Bây giờ hãy đối chiếu đúng mục `img_15_3`:*
  > *- Trước review: Hành động là `RECAPTURE`, điểm nghi ngờ là `0.8549`.*
  > *- Sau review: Hành động đã tự động đổi thành **`KEEP`**, điểm số hạ xuống `0.0001`.*
  > *Mọi can thiệp của người duyệt được lưu vết bất biến trong `audit_log.jsonl` có đầy đủ timestamp, tên reviewer `Nguyễn Tuấn Dũng`, giá trị before và after.*
  > *Đồng thời trong file `decision.json`, Cổng an toàn tự động kích hoạt chuyển từ **`HOLD` sang `GO`** với chữ ký của lead Phạm Đức Hậu: xác nhận 67 ảnh RECAPTURE, 29 ảnh KEEP và tỉ lệ hoàn thành duyệt đạt 100%."*

---

### [4:20 - 5:00] BƯỚC 06 · HIỆU QUẢ, BẢNG SO SÁNH & GIỚI HẠN (Nguyễn Phương Nga - QA & Ca khó)
* **Chiếu Slide 6**:
  > *"Em là Phương Nga. Về hiệu quả định lượng (kết quả tự kiểm nội bộ):*
  > *- **Defect Recall@20** tăng ngoạn mục từ **$0.4545$ lên $0.7727$** (tăng tương đối **$+70.0\%$**).*
  > *- **Precision@20** đạt **$85.0\%$** (17 trong 20 ảnh review là lỗi thực tế).*
  > *- Tỉ lệ báo động giả trong điều kiện dusk và night giảm tuyệt đối về **$0.0\%$**.*
  > *- Tốc độ xử lý cực nhanh: ~8.5 ms/ảnh trên CPU.*
  > *Về ca khó: Khi đốm lóa nằm ở đường chân trời sát mép ranh giới $y \approx 0.35H$, trọng số không gian có thể tạo ra điểm số trung gian, cần chuyên viên can thiệp.*
  > *Hướng phát triển: Nhóm dự kiến tích hợp mô hình Transformer CLIP / MUSIQ trên Google Colab để đánh giá chất lượng ảnh ngữ nghĩa sâu hơn khi có tài nguyên GPU.*
  > *Nhóm G07 xin kết thúc bài trình bày trong đúng 5 phút. Cảm ơn thầy và các bạn đã theo dõi!"*
