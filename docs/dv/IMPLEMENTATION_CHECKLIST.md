# Checklist Yêu cầu 2

| Task | Kết quả cần đạt | Kiểm chứng | Trạng thái |
|---|---|---|---|
| SPEC lên GitHub | Canonical v1.0, lịch sử baseline | check_spec + remote HEAD | DONE — 7c5ec9c |
| RTL target | Hợp đồng APB/UART/FIFO/IRQ v1.0 | directed + independent serial oracle | DONE — mã nguồn 66e9d40; các ca mô phỏng liên kết PASS |
| UVM | agent/driver/monitor/scoreboard/sequences/coverage | compile + positive/negative control | DONE — 13 test classes; 2/2 negative controls DETECTED |
| DV Plan | 80 requirement → stimulus/checker/coverage/evidence | traceability checker | DONE — 80 requirements, 19 testcase definitions, 65 top ports |
| Regression | directed, automatic, random ≥3 seeds | machine-readable verdict + hashes/logs | DONE — 15/15 UVM và 3/3 supplementary PASS; seeds 17/29/101; 810/810 bins |
| Bàn giao | README/results/commands thống nhất | Kiểm gói Git độc lập và đối chiếu remote SHA; không coi là chạy lại toàn bộ simulation | IN_PROGRESS — đang kiểm gói evidence và push |

FPGA/Quartus/board sign-off thuộc Yêu cầu 3, không dùng simulation thay thế.

Kết quả chi tiết: [RESULTS.md](RESULTS.md), [summary.json](../../dv/results/target_v1/summary.json).
73 requirement có các test mô phỏng liên kết PASS, 2 requirement có document checks PASS;
5 requirement FPGA vẫn HW_PENDING. 810/810 chỉ là functional coverage theo model đã định nghĩa;
1.157 native RTL instrumentation points chưa hit, chưa đóng toàn bộ code/toggle coverage.
