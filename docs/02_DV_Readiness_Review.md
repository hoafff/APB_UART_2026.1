# DV readiness — TARGET-v1.0

SPEC v1.0 và DV Plan v1.0 là tài liệu hoạt động. Review v0.3 và baseline được lưu tại docs/history.

Môi trường hiện có UVM APB agent, serial RX peer/TX monitor, register/FIFO/error/IRQ scoreboard, SVA, constrained-random + seed, native covergroups/coverage, replay runner và exporter kiểm nguồn. Có 13 UVM test classes, ba simulation bổ sung (system/controller/one-hot), ma trận 80 requirements và 810 mandatory functional bins.

Bảng kết quả DV ghi số ca UVM, độ phủ chức năng và các điểm code coverage còn thiếu. RC1 đã qua Quartus, fitter, STA và ba mô phỏng Questa. Năm yêu cầu liên quan phần cứng còn chờ nghiệm thu trên bo. [Kết quả DV](dv/RESULTS.md) · [Kết quả FPGA](08_FPGA_Release_Review.md)

Các ca sử dụng stub slave để kiểm error/arbiter được ghi riêng với test controller; không nhầm phản hồi lỗi được inject với lỗi tự nhiên của UART đúng. Probe nội bộ dùng để căn stimulus collision, không lấy DUT data làm expected.
