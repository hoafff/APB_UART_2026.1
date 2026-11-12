# DV readiness — TARGET-v1.0

SPEC v1.0 và DV Plan v1.0 là tài liệu hoạt động. Review v0.3 và baseline được lưu tại docs/history.

Môi trường hiện có UVM APB agent, serial RX peer/TX monitor, register/FIFO/error/IRQ scoreboard, SVA, constrained-random + seed, native covergroups/coverage, replay runner và exporter kiểm nguồn. Có 13 UVM test classes, ba simulation bổ sung (system/controller/one-hot), ma trận 80 requirements và 810 mandatory functional bins.

[RESULTS.md](dv/RESULTS.md) là nguồn verdict hiện hành, kèm source hashes/logs/coverage. Chưa chạy Questa/Quartus/fitter/STA/board; không dùng simulator PASS để đóng năm requirement FPGA. Native unhit instrument points được lưu công khai; không tự tuyên bố toàn bộ code coverage hoặc toàn bộ SPEC sign-off.

Các ca sử dụng stub slave để kiểm error/arbiter được ghi riêng với test controller; không nhầm phản hồi lỗi được inject với lỗi tự nhiên của UART đúng. Probe nội bộ dùng để căn stimulus collision, không lấy DUT data làm expected.
