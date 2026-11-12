# Checklist Yêu cầu 2

| Task | Kết quả cần đạt | Kiểm chứng | Trạng thái |
|---|---|---|---|
| SPEC lên GitHub | Canonical v1.0, lịch sử baseline | check_spec + remote HEAD | DONE — 7c5ec9c |
| RTL target | Hợp đồng APB/UART/FIFO/IRQ v1.0 | directed + independent serial oracle | DONE — mã nguồn 66e9d40; các ca mô phỏng liên kết PASS |
| UVM | agent/driver/monitor/scoreboard/sequences/coverage | compile + positive/negative control | DONE — 13 test classes; 2/2 negative controls DETECTED |
| DV Plan | 80 requirement → stimulus/checker/coverage/evidence | traceability checker | DONE — 80 requirements, 19 testcase definitions, 65 top ports |
| Regression | directed, automatic, random ≥3 seeds | machine-readable verdict + hashes/logs | DONE — 15/15 UVM và 3/3 supplementary PASS; seeds 17/29/101; 810/810 bins |
| Bàn giao | README/results/commands thống nhất | Kiểm gói Git độc lập và đối chiếu remote SHA; không coi là chạy lại toàn bộ simulation | DONE — gói evidence c423388 đã push; origin/main khớp SHA và working tree sạch tại lần đối chiếu |
| Rà soát bổ sung Yêu cầu 1–2 | Kiểm contract, RTL, integrity guard và khả năng chuyển checkout | 80 nghĩa yêu cầu khớp; 5 UART runs và 10 ca công cụ PASS; checkout autocrlf được kiểm | DONE — xem REVIEW_2026-11-12.md |
| Chuyển Yêu cầu 3 sang Windows 11 | Ghi kế hoạch cùng máy dual boot, source và việc còn lại | Đối chiếu ghi chú với SPEC/filelist, giữ HW_PENDING | NOTE_DONE — thực thi Windows/FPGA NOT_RUN |

FPGA/Quartus/board sign-off thuộc Yêu cầu 3, không dùng simulation thay thế.

Kết quả chi tiết: [RESULTS.md](RESULTS.md), [summary.json](../../dv/results/target_v1/summary.json).
73 requirement có các test mô phỏng liên kết PASS, 2 requirement có document checks PASS;
5 requirement FPGA vẫn HW_PENDING. 810/810 chỉ là functional coverage theo model đã định nghĩa;
1.157 native RTL instrumentation points chưa hit, chưa đóng toàn bộ code/toggle coverage.

Kiểm gói Git ngày 12/11/2026: 20 log có đủ verdict/checker marker, 810 bin được tính lại
từ log của các run PASS, SHA-256 của hai waveform và toàn bộ nguồn khớp manifest.
Document checks chạy đạt từ bản xuất Git độc lập. Kiểm tính toàn vẹn gói bàn giao
không được tính thành một lượt mô phỏng mới.
