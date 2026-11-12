# APB_UART_2026.1 — APB UART trên DE2-115

Dự án kiểm thử UART qua APB, hướng đến FPGA Terasic DE2-115 và CP2102.

- **Yêu cầu 1:** [SPEC TARGET-v1.0](docs/01_System_Specification.md) đã hoàn thiện: 80 yêu cầu, 8 nhóm nghiệm thu và 65 chân đã đối chiếu CSV.
- **Yêu cầu 2:** DV Plan và UVM đang được chuyển từ baseline sang TARGET-v1.0; chưa có regression của RTL mục tiêu.
- **Yêu cầu 3:** chưa triển khai Quartus/fitter/STA hoặc thử board.

## Tài liệu và nguồn

1. [SPEC chính thức](docs/01_System_Specification.md).
2. [Requirement index](docs/spec/requirements.json), [pin map](docs/spec/pins.json), [truy vết ID cũ](docs/spec/legacy_mapping.json).
3. [DV Plan hiện tại](docs/03_DV_Plan.md) và [UVM](dv/README.md): bản baseline, đang cập nhật.
4. [Hướng dẫn giảng viên](reference/Huongdan_UART.md), [CSV DE2-115](reference/DE2_115_pin_assignments.csv).
5. [SPEC v0.3 lịch sử](docs/history/01_System_Specification_v0.3.md), [báo cáo kiểm tra baseline](docs/history/APB_UART_2026.1_REVIEW.md).

## Quyết định thiết kế

Dùng PULP APB UART làm nền và sửa RTL để đáp ứng SPEC mục tiêu: địa chỉ word-aligned, baud 16×, none/odd/even parity, FIFO và PE/FE/OE/BI, ngắt có ưu tiên và clear đúng. Profile board: 50 MHz, divisor 27, terminal 115200.

Giữ nguyên baseline trong `rtl/vendor/pulp_apb_uart_sv/`, upstream commit `dfad6e04d19cc9481d3cd2750b45b970dc61271b`. Bản sửa dùng thư mục/filelist riêng. Không compile hai bản có cùng tên module.

Kết quả baseline không đóng yêu cầu TARGET-v1.0. Mọi kết quả phải kèm revision, tool, seed, log và phạm vi; kiểm tra tài liệu không tương đương simulation hay FPGA sign-off.
