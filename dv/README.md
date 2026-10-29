# Yêu cầu 2 — APB UART UVM (implementation v0.1)

**Ngày 29/10/2026 — STATUS: SOURCE CREATED / NOT COMPILED / NOT RUN.** Môi trường thực thi hiện tại không có Questa/ModelSim, VCS, Xcelium, Verilator hoặc Icarus Verilog. Không có testcase nào được báo PASS khi chưa có log/waveform.

## Điểm xuất phát

- [SPEC v0.3](../docs/01_System_Specification.md) — DUT behavior và yêu cầu.
- [DV Plan v0.1](../docs/03_DV_Plan.md) — 25 yêu cầu DUT, testcase, expected, coverage targets và sign-off.
- [DV readiness review](../docs/02_DV_Readiness_Review.md) — handoff và thứ tự test.
- [RTL/Guide discrepancies](../docs/00_RTL_Guide_Discrepancies.md) — 15 vấn đề, bao gồm DIF-07/DIF-08.
- [DUT baseline](../rtl/vendor/pulp_apb_uart_sv/) — 5 file RTL tại PULP commit dfad6e04, nguyên bản.

## File source

| File | Mục đích |
|---|---|
| uvm/uart_apb_if.sv | Tín hiệu APB + UART chung |
| uvm/apb_uart_uvm_pkg.sv | APB sequencer, driver, monitor; UART RX BFM, TX monitor; scoreboard, coverage; test classes |
| uvm/tb_top.sv | DUT instance + clock 50MHz, reset, UVM config_db |
| sim/run_questa.sh | Script compile và chạy với Questa/ModelSim + UVM_HOME |

## Các test đã viết mã nguồn, chưa chạy

| UVM_TESTNAME | Liên quan | Ý nghĩa |
|---|---|---|
| apb_reg_smoke_test | TC_REG_DLAB/RESET, TC_APB_READY_ERR | IIR readback 0xC1, LCR, DLL/DLM, unmapped register |
| uart_tx_8n1_test | TC_TX_THR/FRAME | Ghi THR=0x41, monitor serial UART 8N1, scoreboard |
| uart_rx_8n1_test | TC_RX_VALID_FRAME/RBR_POP/LSR_DR | Phát RX byte 0x42, đọc LSR, RBR |
| apb_random_regs_test | TC_REG_ADDR_ACCESS/APB_ALIAS (partial) | 80 constrained-random valid transactions, LCR/IER/alias/unmapped |
| uart_rx_parity_gap_test | TC_RX_PARITY_FAULT, DIF-08 | **EXPECTED FAIL**: parity flag bị clear liên tục, theo RTL |
| uart_irq_rda_gap_test | TC_INT_RX_RDA_BUG, DIF-07 | **EXPECTED FAIL**: ngắt RDA có thể xuất hiện dù RX empty |

**Chưa implement:** TX mode matrix 5/6/7/8, baud divisor sweep, full FIFO order/clear/threshold, interrupt comprehensive cases, mid-stream reset, full functional coverage closure. DV Plan đánh dấu các test này là PLANNED.

## Chạy trên máy có UVM-capable Questa/ModelSim

Cần simulator với hỗ trợ SystemVerilog/UVM, biến UVM_HOME chỉ tới thư mục chứa src/uvm_pkg.sv. Tùy bản Questa/UVM có thể cần thêm DPI shared library hoặc điều chỉnh compile/link flags.

~~~bash
export UVM_HOME=/opt/uvm-1.2
bash dv/sim/run_questa.sh apb_reg_smoke_test
bash dv/sim/run_questa.sh uart_tx_8n1_test
bash dv/sim/run_questa.sh uart_rx_8n1_test
bash dv/sim/run_questa.sh apb_random_regs_test 17
~~~

Known-gap suite (chạy riêng, có chủ đích phát UVM_ERROR để tránh báo thành PASS):

~~~bash
bash dv/sim/run_questa.sh uart_rx_parity_gap_test
bash dv/sim/run_questa.sh uart_irq_rda_gap_test
~~~

## Cần lưu ý trước khi kết luận PASS

- Bit timing của môi trường thử dùng **candidate** DLL/DLM = 0x01B1 (433), time config 434 clocks/bit. Chưa đo waveform: không xem đây là baud chính thức 115200. Không dùng DLL=27 theo guide.
- Driver APB drive trên cạnh xuống; monitor sample PRDATA cạnh lên hoàn tất. Scoreboard cập nhật RBR pop sau read.
- Current scoreboard là baseline model để làm smoke: chưa hỗ trợ đầy đủ interrupt/FIFO cycle-accurate/timing. Coverage hiện có APB direction×addr×DLAB và UART direction×mode×parity, không được báo 100% functional coverage.
- Hai known-gap test phải nằm ngoài “green regression” và gắn issue IDs. Nếu một kết quả phù hợp bug RTL, đó là **bằng chứng sai khác so với hướng dẫn**, không phải tính năng đã pass.
- Chỉ compile năm file trong src_files.yml; tuyệt đối không add thêm apb_uart.sv vì trùng định nghĩa module.

## Trạng thái minh bạch

| Test / nhóm | Status |
|---|---|
| APB register smoke / TX 8N1 / RX 8N1 | SOURCE WRITTEN — NOT RUN |
| Constrained-random APB | SOURCE WRITTEN — NOT RUN |
| Parity/RDA known gaps | SOURCE WRITTEN — EXPECTED FAIL WHEN RUN |
| FIFO edge, baud sweep, comprehensive coverage | PLANNED — NOT CODED |
| Simulator compile success, log, waveform, coverage measured | **NOT AVAILABLE** |

**Kế tiếp:** Lấy log compiler từ simulator thật, sửa lỗi build nếu có; chạy P0, đo baud chuẩn, mở rộng testcase coverage, lập bug report. Từng kết quả mới có bằng chứng để nâng SPEC v1.0.
