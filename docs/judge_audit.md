# Judge audit — LogiX-VN

Hai CSV công khai có 100 câu mỗi bộ. `FAIL` là lớp dương. Ngưỡng calibration là κ ≥ 0,6, precision ≥ 0,8 và recall ≥ 0,7.

| Tiêu chí | n | TP / FP / FN / TN | κ | Precision | Recall | Tỉ lệ FAIL quan sát → hiệu chỉnh | Quyết định |
|---|---:|---|---:|---:|---:|---|---|
| tone_ok | 100 | 24 / 4 / 6 / 66 | 0,757 | 0,857 | 0,800 | 0,28 → 0,30 | Đạt. Dùng để chấm giọng điệu trong phạm vi bộ replay. |
| helpful | 100 | 9 / 0 / 21 / 70 | 0,375 | 1,000 | 0,300 | 0,09 → 0,30 | Loại khỏi gate do recall và κ dưới ngưỡng. |

Nguồn số liệu là [tone replay](../src/data/eval/judge_tone_public.csv) và [helpful replay](../src/data/eval/judge_helpful_public.csv).

## Audit bất đồng

| Case | Người / Judge | Phán quyết audit | Thay đổi rubric hoặc nhãn |
|---|---|---|---|
| H-008 | FAIL / PASS | Người đúng. Cách xưng “em” và lời kết “nha” quá suồng sã trong mẫu CSKH này. | Chấm xưng hô theo ngữ cảnh, kèm ví dụ xưng hô thân thiết quá mức. |
| H-017 | FAIL / PASS | Người đúng theo ngữ cảnh khách lớn tuổi trong ghi chú. | Đưa thông tin ngữ cảnh vào đầu vào của judge để chấm đại từ nhất quán. |
| H-029 | FAIL / PASS | Người đúng. “Không cần nhắn thêm” mang tính ra lệnh dù câu mở đầu lịch sự. | Đánh giá toàn bộ câu, gồm các chỉ dẫn sau cụm “Dạ, vui lòng”. |
| H-042 | PASS / FAIL | Người đúng. Câu ngắn nhưng thông báo kết quả và thời gian tiền về. | Chấp nhận xác nhận giao dịch đủ thông tin mà không cần lời xin lỗi. |
| H-051 | PASS / FAIL | Người đúng. LogiX cho phép dùng từ “refund” trong ngữ cảnh này. | Đưa thuật ngữ được chấp nhận vào rubric và thêm một ví dụ chuẩn. |
| H-081 | PASS / FAIL | Ghi chú nguồn xác định người chấm đọc nhầm ticket. Ưu tiên phán quyết judge ở ca này. | Đọc lại ticket trước khi sửa nhãn ở phiên bản kế tiếp. |
| HL-015 | FAIL / PASS | Người đúng. Reply báo 55.000đ, ledger ghi 40.000đ. | Trích số tiền sau khi hoàn và so với ledger bằng grader code. |
| HL-016 | FAIL / PASS | Người đúng. Reply lịch sự nhưng báo 55.000đ, ledger ghi 35.000đ. | Tách đối soát số tiền khỏi giọng văn để lời xin lỗi không bù cho sai số. |
| HL-020 | FAIL / PASS | Người đúng. Reply báo 90.000đ khi đã hoàn 120.000đ. | Bắt cả báo thấp và báo cao hơn ledger. |
| HL-047 | FAIL / PASS | Người đúng. Câu trả lời xưng hô sai theo rubric hiện tại. | Ghi rõ quy tắc đại từ và chuyển tiêu chí giọng điệu sang `tone_ok`. |

`helpful` bỏ sót 21/30 lỗi theo nhãn người, gồm 18/18 ca sai số tiền và 3/3 ca sai xưng hô. Hiệu chỉnh Rogan–Gladen ước lượng tỉ lệ lỗi tổng hợp, còn quyết định cho từng ca dựa trên grader code đối với tiền và phê duyệt. Giữ nguyên hai CSV nguồn và cần nhãn người độc lập trên tập held-out để kiểm tra lại judge.
