# APB_UART_2026.1 — Specifications and Verification

**DUT:** PULP APB UART SV (TI 16550-style subset), hệ thống FPGA DE2-115 + CP2102 theo hướng dẫn giảng viên.  
**Yêu cầu 1:** SPEC **v0.2 đã rà soát và sẵn sàng làm cơ sở lập DV Plan**, nhưng **chưa sign-off / chưa mô phỏng**.  
**Yêu cầu 2:** Chưa viết UVM/testbench và chưa chạy test; đã có *handoff review* cùng traceability REQ→TC.  
**Yêu cầu 3:** FPGA bring-up chưa triển khai.

## Bắt đầu ở đây

1. [docs/01_System_Specification.md](docs/01_System_Specification.md) — đặc tả hệ thống và DUT, REQ IDs, RTL behavior và [OPEN] items.
2. [docs/00_RTL_Guide_Discrepancies.md](docs/00_RTL_Guide_Discrepancies.md) — 14 điểm sai khác/rủi ro/bổ sung quan trọng giữa hướng dẫn và RTL.
3. [docs/02_DV_Readiness_Review.md](docs/02_DV_Readiness_Review.md) — **review SPEC, bảng REQ→TC, UVM architecture, P0/P1/P2, coverage và công việc OPEN**.
4. [reference/Huongdan_UART.md](reference/Huongdan_UART.md) — tài liệu giảng viên, giữ nguyên để đối chiếu.

## RTL baseline (không chỉnh sửa)

Nguồn: [pulp-platform/apb_uart_sv](https://github.com/pulp-platform/apb_uart_sv), branch pulpinov1, commit:

    dfad6e04d19cc9481d3cd2750b45b970dc61271b

Đã lưu nguyên 5 file RTL, [src_files.yml](rtl/vendor/pulp_apb_uart_sv/src_files.yml) và [LICENSE](rtl/vendor/pulp_apb_uart_sv/LICENSE) tại [rtl/vendor/pulp_apb_uart_sv/](rtl/vendor/pulp_apb_uart_sv/).

**Chỉ đưa 5 RTL được liệt kê trong src_files.yml vào compilation list.** Không compile đồng thời apb_uart.sv và apb_uart_sv.sv (trùng định nghĩa). Top-Level de2_115_apb_uart_bringup.sv không nằm trong upstream, phải viết riêng cho Yêu cầu 3.

## Quy tắc của dự án

- Bám phạm vi và kiến trúc do giảng viên hướng dẫn.
- Mọi địa chỉ, timing, hành vi DUT phải đối chiếu RTL ở commit đã khóa; khác biệt được ghi cụ thể trong issue register.
- UVM test phải phân biệt **RTL-CONTRACT**, **GUIDE-GAP** và **INVESTIGATION**; không báo PASS cho tính năng chưa được DUT hỗ trợ.
- Không thay đổi RTL gốc chỉ để test PASS. Nếu sửa bug thì dùng branch/revision riêng, không ghi đè baseline.

## Bước tiếp theo — Yêu cầu 2

Từ [DV readiness review](docs/02_DV_Readiness_Review.md), chốt DV Plan chính thức, chọn simulator/UVM version, tạo APB/UART agents + independent scoreboard, rồi chạy các bài **P0**: APB/REG smoke, TX bit time/frame, RX RBR/LSR, parity/interrupt investigation. Lưu waveforms, coverage và bug log; lúc đó mới có cơ sở chốt SPEC v1.0.
