# Bug / issue ledger

| ID | Phạm vi | Quan sát | Xử lý / bằng chứng |
|---|---|---|---|
| BASE-01 | Baseline UVM | 15 backtick sformatf + 1 backtick fatal làm compile thất bại | Archive đã sửa cú pháp; baseline review lưu lịch sử |
| BASE-02 | Baseline UART | Byte map/direct divider không khớp guide | TARGET có word map/16×, kiểm APB/baud |
| BASE-03 | Baseline UART | Odd parity, PE/FE/OE/BI, IRQ không đủ contract | Bản target riêng; target_tx_modes/target_errors/target_irq và các test liên quan PASS; xem RESULTS.md |
| FLOW-01 | Testbench | SV task direction kế thừa output làm error argument không có default input đúng | Khai báo input rõ sau output; lưu failed build log |
| FLOW-02 | Host build | PCH không ghi được vì /home hết chỗ | Xóa generated .o/.a/.gch/.d của các audit build cũ; giữ sources/binary/log; build lại |
| FLOW-03 | Host runtime | Constrained-random không tìm được z3 dù suite đã cài | Runner chạy simulator qua môi trường suite; seed 17/29/101 PASS sau khi sửa PATH; Z3 4.15.5 |
| TB-04 | Scoreboard review | THR đến đúng stop boundary khi queue trước đó rỗng không được coi là byte đã queued trước cạnh | Back-to-back oracle trừ arrival cùng cạnh; thêm directed TX empty+arrival, không bắt bypass trái SPEC |
| FLOW-04 | Evidence exporter | JSON còn PASS nhưng log lỗi/thiếu completion/assertions, test trùng, timeout hoặc negative control nguồn không ổn định vẫn lọt qua exporter | Tái hiện 9 ca trước sửa; exporter đối chiếu raw log, counters, coverage và test/seed inventory. 10 ca kiểm tra công cụ đạt sau sửa; kết quả RTL cũ cũng qua guard mới |
| FLOW-05 | Chuyển checkout sang Windows | `core.autocrlf=true` đổi RTL sang CRLF, khiến SHA-256 vendor baseline không khớp dù logic không đổi | `.gitattributes` cố định LF cho source; giữ nguyên byte CSV và raw logs. Kiểm lại checkout với autocrlf bật; đây là kiểm chuyển đổi file trên Linux, chưa phải chạy Windows |

Final regression report là nguồn trạng thái thực thi; không đóng yêu cầu chỉ từ bảng sửa lỗi.

Chi tiết lần rà soát bổ sung: [REVIEW_2026-11-12.md](REVIEW_2026-11-12.md).
