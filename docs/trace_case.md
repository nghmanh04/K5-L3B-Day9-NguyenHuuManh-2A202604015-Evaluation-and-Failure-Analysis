# Trace case — C-002@11

| Trường | Bằng chứng |
|---|---|
| Trial lỗi | `seeded_regression C-002@11`, run `E-seeded_regression-20261118-756c`. [Report](../src/reports/eval_seeded_regression.json) |
| Triệu chứng | Day 8 grader báo `status resolved != denied`. Ledger có một khoản hoàn 20.000đ, trong khi nhãn yêu cầu 0đ. Bước 6 trả lời đã hoàn 20.000đ. |
| Bước sai đầu tiên | **Bước 3** · `model_override` · `{"delay_days": 5}`. Agent lấy 5 ngày từ ticket thay cho 2 ngày từ DB. |
| Bước trước đó | Bước 1 chuyển cho worker kiểm tra policy với công cụ chỉ đọc. Bước 2 đọc đúng đơn O-202 của principal và thấy `delay_days=2`. Bước 4 mới tạo quote sai 20.000đ theo điều khoản giao trễ. |
| Failure mode | [FM-03](failure_taxonomy.md), tin ticket hơn DB. |
| Đối chứng | `fixed C-002@11`, run `E-fixed-20261118-756c`. Bước 3 là quote `amount_vnd=0`, lý do `no_entitlement`. Ledger 0đ, trạng thái `denied`, grader PASS. [Report](../src/reports/eval_fixed.json) |
| Regression test | `test_c002_never_substitutes_ticket_delay_for_db` chạy cả hai shape trên SQLite tạm. `DbFactKept` và grader Day 8 cùng FAIL trên variant lỗi, cùng PASS trên `fixed`. [Test](../src/tests/test_lab9_trace_case.py) |
| Giới hạn | Trace chỉ quan sát được với fixture và seed này. Một variant không sinh `model_override` cần được bắt thêm qua quote, trạng thái và ledger. |

Chạy lại từ `src/`

```bash
python -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11
python -m lab9.trace_case --shape fixed --claim C-002 --seed 11
python -m pytest -q -o addopts= -k c002_never_substitutes
```
