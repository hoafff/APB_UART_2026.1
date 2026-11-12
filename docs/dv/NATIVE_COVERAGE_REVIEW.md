# Native coverage — audit closure v2

Tính lại từ `dv/results/target_v2/coverage_merged.dat.gz`: line **130/135**, branch **149/156**, expr **279/309**, toggle **1975/3030**. Nguồn merge là 15 normal UVM runs + 3 supplemental runs, cùng source/build bindings đã kiểm. Không cộng negative controls, seed bổ sung hoặc các probe audit.

Có **1.097 điểm chưa hit**: 5 line, 7 branch, 30 expr, 1.055 toggle. Giữ nguyên toàn bộ mẫu số; không thêm exclusion. Tập functional 833/833 và native coverage đo các nghĩa khác nhau. DV Plan §6 dùng native coverage để chẩn đoán; không đặt ngưỡng 100% native làm điều kiện bàn giao Yêu cầu 2.

| Module | Toggle chưa hit | Line | Branch | Expr |
|---|---:|---:|---:|---:|
| de2_115_apb_uart_bringup | 177 | 0 | 0 | 0 |
| de2_uart_controller | 425 | 3 | 2 | 10 |
| apb_uart_sv | 79 | 1 | 0 | 1 |
| uart_fifo | 314 | 1 | 5 | 19 |
| uart_rx | 46 | 0 | 0 | 0 |
| uart_tx | 14 | 0 | 0 | 0 |

Rà source các điểm non-toggle:

- `apb_uart_sv.sv:113`: default register-write nằm sau valid-address/permission guard. `:119`: điểm biểu thức kết hợp `tx_count != 0` và `tx_count == 0` cùng sai là bất khả thi trong mô hình hai trạng thái. Đây là nhận xét source, chưa phải chứng minh formal hay exclusion được duyệt.
- `uart_fifo.sv:37–49`: có specialization WIDTH=8 cho TX và WIDTH=11 cho RX. Nhánh quét/ack metadata không có cùng ý nghĩa ở cả hai instance; TX không ack error, các bit trên độ rộng hợp lệ sau phép shift luôn bằng 0. Raw instrumentation còn tách điểm theo specialization/hierarchy. Không suy rằng mọi điểm tại một dòng đều không thể đạt; 1 line/5 branch/19 expr vẫn để mở trong ledger.
- `de2_uart_controller.sv:73,96`: các default của case được giữ mở. `:21,22,23,51,84,90,91,99,100`: điểm điều kiện/fault/slot phụ thuộc instance và cấu hình test. TC15 đã kiểm fault injection, overflow, fairness và simultaneous consume/new ở controller stub, nhưng chưa đảm bảo mọi điểm tương ứng trong system instance đều được hit. Slave thật của profile này không tạo wait state. Đây là giới hạn phạm vi native, không được đổi thành PASS từng điểm.
- Toggle: address/data upper bits, counter ranges, memory entries và từng configuration/hierarchy chưa được kích hết. Không dùng việc FIFO random probe đã PASS để cộng thêm toggle; probe đó không nằm trong 18 input coverage của merge. Các điểm còn lại không có waiver hoặc chứng minh unreachable.

Chi tiết từng điểm giữ trong [native_unhit_points.json](../../dv/results/target_v2/native_unhit_points.json). Kết quả recount độc lập với JSON summary của exporter nằm trong `dv/results/audit_closure_20261112/checks.json`. Không tuyên bố native coverage closure, X-propagation, formal hoặc hardware sign-off.
