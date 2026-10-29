# 03 — DESIGN VERIFICATION PLAN (DV PLAN) — APB UART SV

> **DV Plan v0.1 · 29/10/2026 · Yêu cầu 2**  
> **Source of truth:** [System Specification v0.3](01_System_Specification.md), [RTL/Guide differences](00_RTL_Guide_Discrepancies.md), [DV readiness review](02_DV_Readiness_Review.md).  
> **DUT baseline:** [PULP @ dfad6e04d19cc9481d3cd2750b45b970dc61271b](../rtl/vendor/pulp_apb_uart_sv/).  
> **Status:** PLAN APPROVED FOR IMPLEMENTATION / NOT VERIFIED. No simulations have yet passed.

## 1. Mục tiêu và giới hạn

Kiểm chứng **module apb_uart_sv** và các module con, bằng SystemVerilog UVM testbench, với APB Master BFM phía input và UART RX input driver + TX monitor trên serial pins. Kiểm tra tính đúng APB register access, DLAB, reset, TX/RX, FIFO, interrupt, timing và coverage. **Không** đưa KEY/SW/HEX/LED/CP2102 vào DUT-level UVM; đây là yêu cầu FPGA (Yêu cầu 3).

Nguồn dẫn: hướng dẫn thầy định nghĩa mục tiêu hệ thống; hành vi thực tế của DUT lấy từ RTL pinned. **Conformance với RTL ≠ compliance với chuẩn 16550**. Một testcase phơi bày một GUIDE-GAP không được xem là PASS tính năng đó.

## 2. Baseline và nguyên tắc kiểm thử

- DUT ở [rtl/vendor/pulp_apb_uart_sv](../rtl/vendor/pulp_apb_uart_sv/) gồm năm file trong src_files.yml. **Không chỉnh RTL** để ép testcase pass.
- Mặc định: CLK 50 MHz (20 ns period), RSTN active-low async. APB 12-bit address, 32-bit data.
- Valid APB: SETUP (PSEL=1,PENABLE=0) trước ACCESS (PSEL=1,PENABLE=1). Completion khi PREADY=1. RTL luôn PREADY=1, PSLVERR=0.
- Offsets thật do PADDR[2:0]: 0=RBR/THR/DLL; 1=IER/DLM; 2=IIR/FCR; 3=LCR; 5=LSR. DLAB=LCR[7]. Các alias high bits cùng dữ liệu giải mã; read 4/6/7=0.
- Read side effects: RBR pop FIFO; IIR và LSR tạo clear-interrupt mask. Sample PRDATA trước NBA/pop; scoreboard update sau event.
- Giá trị after-reset ngay trên APB: IIR read = 0xC1 trong điều kiện không enable interrupt, **không** là 0x01. LSR reset value 0x60 tại event reset; giá trị tại các clock tiếp theo có thể thay đổi.
- **OPEN baud**: không nạp 27 của guide. Đo real TX bit length để khóa divisor, bắt đầu khảo sát khoảng 432..433; 433 là *giá trị thử*, không phải kết quả đã xác nhận.
- **Known static gap DIF-08**: uart_rx.err_clr_i=1 (clear dominates), parity flag cannot be latched after reset. **Known static gap DIF-07**: RDA_i receives LSR[5] (TX empty) instead of RX-ready. Hai ca này phải được đưa vào **expected-failing guide-compliance suite (XFAIL)**; waveform vẫn chưa được chạy.
- Chạy negative/guide-gap riêng khỏi healthy regression, không tính 100% pass nếu lỗi thật.

## 3. Strategy: verification components

| Component | Vai trò |
|---|---|
| tb_top + uart_apb_if | Clock/reset; DUT instance; giao tiếp APB/UART |
| APB sequencer/driver/monitor | Phát giao dịch 2 pha; thu giao dịch ACCESS complete; tránh bus race |
| UART RX BFM | Lái serial bits start/data/parity/stop vào rx_i theo clock cycles/bit |
| UART TX monitor | Decode tx_o độc lập thành frame; kiểm start,data,parity,stop |
| APB + UART scoreboard | Dự đoán LCR/DLAB/IER/DLL/DLM, TX expected queue, RX FIFO expected queue, side effects |
| Coverage collector | Cross APB read/write/offset/DLAB; serial frame bins; FIFO/IRQ đưa vào giai đoạn tiếp |
| test classes | Smoke, TX, RX, random registers, XFAIL parity, XFAIL IRQ |
| log/result report | UVM summary + wave/log + testcase ID + issue ID + commit + simulator version |

**Oracle độc lập:** TX reference lấy từ APB THR write, không dựa internal DUT TX state. RX reference từ UART RX BFM, không dựa internal RX FIFO. Internal signal chỉ dùng khi phân tích issue. Sample serial giữa bit; APB monitor sample tại completion.

## 4. Test cases và pass/fail criteria

| ID | REQ | Stimulus (directed) | Expected & checker | Priority | Suite |
|---|---|---|---|---|---|
| TC_APB_PROTOCOL | REQ_APB_001 | Read/Write LCR qua SETUP→ACCESS | Driver/monitor stable controls, one completion | P0 | normal |
| TC_APB_WRITE_GATING | REQ_APB_002 | Idle/setup/read vs write-ACCESS | không update ở sai pha | P1 | normal |
| TC_APB_READ_GATING | REQ_APB_003 | PSEL=0, SETUP, READ ACCESS | PRDATA 0 ngoài valid read | P1 | normal |
| TC_APB_READY_ERR | REQ_APB_004 | APB reads/writes | PREADY 1, PSLVERR 0 | P0 | normal |
| TC_APB_ALIAS | REQ_APB_005 | write/read LCR at 0x03/0x0B | same register; 0x0C không phải LCR | P1 | normal |
| TC_REG_ADDR_ACCESS | REQ_REG_001 | access offsets 0/1/2/3/5 | read/write theo map + DLAB | P0 | normal |
| TC_REG_DLAB | REQ_REG_002 | LCR=0x83, DLL/DLM, restore DLAB0 | DLL/DLM readback, IER tách biệt | P0 | normal |
| TC_REG_DATA_WIDTH | REQ_REG_003 | high bits PWDATA varied | only low byte impacts 8-bit regs | P1 | normal |
| TC_RESET_REG | REQ_REG_004 | assert reset during/after config | LCR/IER/divisor reset; APB IIR=0xC1 khi no IRQ | P0 | normal |
| TC_REG_UNIMPLEMENTED | REQ_REG_005 | offsets 4/6/7 read/write | PRDATA=0; PSLVERR=0 | P1 | normal |
| TC_TX_THR | REQ_TX_001 | write THR data 0x41 | one enqueued TX frame, no duplicates | P0 | normal |
| TC_TX_FRAME | REQ_TX_002 | 8N1 byte 0x41 | idle, start0, LSB, stop1 | P0 | normal |
| TC_TX_DATABITS | REQ_TX_003 | 5/6/7/8 configs | exact bit count/data mask | P1 | normal |
| TC_TX_PARITY_STOP | REQ_TX_004 | no/even parity; 1/2 stop | even parity XOR, correct stops; odd is gap | P1 | normal+gap |
| TC_TX_BAUD_MEASURE | REQ_TX_005 | sweep divisor; 50MHz | observed bit time, baud error%; no hardcode 27 | P0 | investigation |
| TC_RX_VALID_FRAME | REQ_RX_001 | serial 0x42, 8N1 | received byte in RBR | P0 | normal |
| TC_RX_RBR_POP | REQ_RX_002 | RX two bytes then read twice | FIFO oldest first; each read pops once | P1 | normal |
| TC_RX_LSR_DR | REQ_RX_003 | RX input then read RBR | LSR[0] 0→1→0 | P0 | normal |
| TC_RX_PARITY_FAULT | REQ_RX_004 | bad parity frame | guide expects PE; RTL original cannot latch err_o; capture XFAIL | P0 | xfail |
| TC_RX_FRAMING_OVERRUN_GAP | REQ_RX_005 | invalid stop / RX overflow | demonstrate missing FE/OE flags, not baseline PASS | P2 | xfail |
| TC_FIFO_RESET_CLEAR | REQ_FIFO_001 | populate queues; FCR clear bits | counts empty, no stale data | P1 | normal |
| TC_FIFO_ORDER_FULL | REQ_FIFO_002 | 16 entries, then 17th; read order | full behavior, loss/backpressure as RTL | P1 | investigation |
| TC_FIFO_THRESH | REQ_FIFO_003 | thresholds 1/4/8/14 | assess T-1/T/T+1; isolate bogus RDA source | P1 | investigation |
| TC_INT_SOURCES_CLEAR | REQ_INT_001 | IER masks, read IIR/LSR | model IIR/event; reassert if source remains | P1 | investigation |
| TC_INT_RX_RDA_BUG | REQ_INT_002 | IER[0]=1, RX empty and TX empty | guide: no RX IRQ; RTL may assert due to TX empty; capture XFAIL | P0 | xfail |

**Initial implementation in repo** includes P0 APB register smoke, TX frame, RX byte, random APB-register test and known-gap scenarios (see README under dv/). Other rows remain **PLANNED**, not automatically completed by having a matrix.

## 5. Random testing

**Phase A:** constrained random APB legal accesses to registers LCR/IER and unmapped offsets 4/6/7, with high-address alias; avoid RBR/THR in generic register random to prevent opaque UART side effects. Seed logged and reproducible. Expected readback maintained in scoreboard.

**Phase B (later):** random TX bytes, frame modes 5–8, parity/no parity, 1/2 stop; random RX bytes and delays, FIFO order/clear/full and reset injection. Generate only legal APB accesses unless explicitly targeting protocol robustness.

## 6. Functional coverage và mục tiêu

| Coverage model | Bins/cross | Target for completion |
|---|---|---|
| APB | read/write × offset 0..7 × DLAB; selected/setup/alias | >=95% reachable bins |
| TX | 5/6/7/8 × parity off/even × stop 1/2; data {00,FF,55,AA,41,random} | all 16 frame-mode combinations demonstrated |
| RX | 5/6/7/8 × parity on/off; good/bad parity; RX FIFO {0,1,15,16} | all legal modes; gap tests reported separately |
| FIFO | empty/partial/full; push/pop/clear; thresholds T-1/T/T+1 | all reachable cases, justified waivers |
| Interrupt | IER bits×IIR×event; RX/TX occupancy classes | reachable combinations; gap evidence |
| Assertions / checks | APB protocol, reset, scoreboard frame/RBR/side effect | 0 unexplained errors in normal suite |

*These are coverage targets, not measured results.* Exclude invalid/unreachable bins with rationale, not silent waivers. Final sign-off depends on regression PASS and reviewed known-gap waivers, not coverage % alone.

## 7. Test suites, evidence & sign-off

- **smoke:** APB reset/register/handshake, TX 8N1, RX 8N1; must PASS once simulator is available.
- **regression:** smoke plus data-width/register aliases, TX modes, FIFO behavior, random seeds, interrupts; full coverage report.
- **known_gap/xfail:** RX parity, RDA interrupt, framing/overrun; report expected nonconformance and waveform. **Do not include as green PASS** in smoke.
- **Evidence per test:** tool/version, seed, commit IDs, command line, UVM transcript, relevant waveform with timing, expected/observed, verdict, linked REQ/DIF.
- **Gate for SPEC 1.0 sign-off:** required P0 cases completed, baud measured and documented, XFAILs characterized and approved as limitations, no unknown severity-P0 failures, coverage review and test inventory maintained.
- **Gate for FPGA:** Top-Level implementation (missing upstream) and Quartus pin/electrical validation are part of Yêu cầu 3, not evidence of DUT-UVM pass.

## 8. OPEN

1. UVM-capable simulator/version and license (Questa, VCS, Xcelium, or UVM-capable equivalent).
2. Real baud bit-period from waveform, tolerance for CP2102 115200 operation.
3. Actual simulator evidence for parity/interrupt known RTL gaps.
4. Full FIFO regression, concurrent edges, read sampling and reset mid-frame.
5. Functional coverage closure and test result reports.

**V0.1 DV Plan = ready to implement, not a claim that DUT passes.**
