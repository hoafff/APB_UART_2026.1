# Checklist Yêu cầu 2

| Task | Kết quả cần đạt | Kiểm chứng | Trạng thái |
|---|---|---|---|
| SPEC lên GitHub | Canonical v1.0, lịch sử baseline | check_spec + remote HEAD | DONE — 7c5ec9c |
| RTL target | Hợp đồng APB/UART/FIFO/IRQ v1.0 | directed + independent serial oracle | IN_PROGRESS |
| UVM | agent/driver/monitor/scoreboard/sequences/coverage | compile + positive/negative control | IN_PROGRESS |
| DV Plan | 80 requirement → stimulus/checker/coverage/evidence | traceability checker | TODO |
| Regression | directed, automatic, random ≥3 seeds | machine-readable verdict + hashes/logs | TODO |
| Bàn giao | README/results/commands thống nhất | clean checkout replay + remote SHA | TODO |

FPGA/Quartus/board sign-off thuộc Yêu cầu 3, không dùng simulation thay thế.
