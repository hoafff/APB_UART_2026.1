# APB_UART_2026.1 — APB UART trên DE2-115

Dự án kiểm thử UART qua APB, hướng đến FPGA Terasic DE2-115 và CP2102.

- **Yêu cầu 1:** [SPEC TARGET-v1.0](docs/01_System_Specification.md), 80 yêu cầu và 65 chân đối chiếu CSV.
- **Yêu cầu 2:** [DV Plan — audit closure v2](docs/03_DV_Plan.md), RTL mục tiêu, UVM, directed/automatic/constrained-random, SVA và coverage đã có. [Kết quả và giới hạn](docs/dv/RESULTS.md) là nguồn verdict thực thi.
- **Yêu cầu 3:** **SOFTWARE_READY / HARDWARE_PENDING** — đã chạy Quartus Lite 25.1, fitter/STA ba corner, tạo `.sof` và manifest SHA-256; chưa nạp/thử bo thật. Xem [hướng dẫn triển khai và nạp](docs/06_FPGA_Implementation.md).

**Bước tiếp theo:** kiểm jumper/điện áp, nạp SRAM và thử DE2-115 + CP2102 khi có bo.
Xem [ghi chú Windows 11](docs/05_Windows11_FPGA_Handoff.md) và
[kết quả sửa và kiểm lại](docs/dv/AUDIT_CLOSURE_2026-11-12.md).

## Bắt đầu

1. [SPEC](docs/01_System_Specification.md), [thay đổi RTL](docs/04_RTL_Changes.md).
2. [DV Plan](docs/03_DV_Plan.md), [80 requirement mappings](docs/dv/REQUIREMENT_MATRIX.md), [testcase definitions](docs/dv/testcases.json), [833 functional bins](docs/dv/coverage_model.json).
3. [Hướng dẫn chạy UVM](dv/README.md), [regression results](docs/dv/RESULTS.md), [defect/tool-flow ledger](docs/dv/BUG_LOG.md).
4. [Hướng dẫn giảng viên](reference/Huongdan_UART.md), [CSV DE2-115](reference/DE2_115_pin_assignments.csv).
5. [SPEC v0.3](docs/history/01_System_Specification_v0.3.md), [baseline review](docs/history/APB_UART_2026.1_REVIEW.md) để đối chiếu lịch sử.

## Kiến trúc và compatibility

Giữ PULP nguyên gốc trong `rtl/vendor/pulp_apb_uart_sv/`, commit upstream `dfad6e04d19cc9481d3cd2750b45b970dc61271b`. Bản sửa ở `rtl/modified/pulp_apb_uart_sv/`: word-aligned register map, baud 16×, none/odd/even parity, FIFO, PE/FE/OE/BI và IRQ theo SPEC. Wrapper/master ở `rtl/fpga/`.

Profile board: 50 MHz, DLL=27/DLM=0, terminal 115200, 8N1 mặc định; N/O/E chọn trước reset. Không compile đồng thời vendor và target vì trùng tên module. Bản sửa là subset đã định nghĩa, không tuyên bố tương thích đầy đủ 16550.

## Chạy tự động

```bash
bash dv/sim/run_smoke.sh
```

Cần Verilator/Z3 trong OSS CAD Suite; có thể dùng PATH, `OSS_CAD_SUITE` hoặc `~/.local/bin/ic-eda`. UVM được pin và tải tự động vào `.tools/uvm`. Flow có 15 run UVM chức năng (12 directed + random ba seed), hai negative controls, ba simulation bổ sung, document checks và exporter. Xem dv/README.md về RAM/disk/time và cách chạy từng test.

Kết quả baseline không đóng yêu cầu target. Chỉ xuất PASS khi nguồn đúng hash, checker/assertion hoạt động, traffic hoàn tất và không có lỗi. Code coverage, functional coverage và hardware sign-off được báo riêng; các điểm native chưa hit được giữ để review.
