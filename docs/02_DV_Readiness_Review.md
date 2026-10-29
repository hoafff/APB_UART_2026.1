# SPEC REVIEW & UVM HANDOFF — APB UART SV

> Phiên bản: 0.3 (second audit phục vụ Yêu cầu 2), 29/10/2026.  
> Trạng thái: **READY TO START DV PLAN/UVM**, **NOT SIGNED OFF**; chưa có simulation pass.  
> Nguồn: [Huongdan_UART.md](../reference/Huongdan_UART.md), [SPEC](01_System_Specification.md), [Discrepancies](00_RTL_Guide_Discrepancies.md).  
> DUT baseline: [PULP @ dfad6e04d19cc9481d3cd2750b45b970dc61271b](https://github.com/pulp-platform/apb_uart_sv/tree/dfad6e04d19cc9481d3cd2750b45b970dc61271b), lưu nguyên trong [rtl/vendor/pulp_apb_uart_sv](../rtl/vendor/pulp_apb_uart_sv/).

## A. Kết quả rà soát

- **Đủ bắt đầu DV Plan và UVM:** đã có boundary DUT, pin interface, APB phases, register map và requirement IDs.
- **Chưa sign-off SPEC 1.0:** divisor ở 50MHz chưa đo, parity/interrupt/FIFO chưa có waveform và pinout chưa kiểm manual. **DIF-07/DIF-08 đã chứng minh lỗi kết nối bằng RTL**; simulation vẫn cần để có bằng chứng đo được.
- **Thứ tự nguồn:** hướng dẫn thầy xác định phạm vi, RTL đã khóa xác định hành vi thật. Không báo pass tính năng chỉ có trong hướng dẫn.
- **Không sửa RTL baseline**; mọi bản sửa sau này dùng revision khác và regression độc lập.

## B. Phân loại expectation và kết quả

| Class | Nghĩa | Verdict |
|---|---|---|
| RTL-CONTRACT | Thấy trực tiếp từ RTL; expected xác định | PASS/FAIL theo checker độc lập |
| GUIDE-GAP | Tính năng hướng dẫn yêu cầu nhưng RTL thiếu | Ghi gap; **không báo PASS** |
| INVESTIGATION | Tình huống nghi ngờ bug hoặc timing chưa đo | Chạy directed, lưu waveform/log, sau đó kết luận |
| SYSTEM-FPGA | Yêu cầu Top-Level, KEY/SW/HEX/LED/CP2102 | Kiểm ở Yêu cầu 3, không tính DUT-level UVM |

Phải tách **RTL baseline conformance** khỏi **guide compliance**; các lỗi RTL không được hợp thức hóa thành yêu cầu chuẩn.

## C. Điều kiện kỹ thuật quan trọng cho checker

1. **APB:** PADDR[11:0], data bus 32-bit, PREADY=1, PSLVERR=0. Master dùng SETUP → ACCESS. Giữ một WRITE ACCESS nhiều cạnh clock có thể tạo side effect lặp.
2. **Decode:** PADDR[2:0] là offset duy nhất. 0=RBR/THR/DLL, 1=IER/DLM, 2=IIR/FCR, 3=LCR, 5=LSR; 4,6,7 không có case. 0x03 và 0x0B alias; 0x0C **không** là LCR. DLAB=LCR[7].
3. **Read side effects:** READ ACCESS RBR: fifo_rx_ready=1 (pop); IIR: clr_int=0100; LSR: clr_int=1100. PRDATA tổ hợp. Monitor sample dữ liệu ở cạnh hoàn tất, scoreboard thực hiện pop/clear **sau** khi lấy mẫu.
4. **TX:** THR lấy PWDATA[7:0]; TX FIFO 16×8, idle=1, start=0, 5–8 data bits LSB-first, parity enable LCR[3], stop 1/2 bằng LCR[2]. XOR parity dạng even; không có odd select.
5. **RX:** FIFO 16×9, đồng bộ input 3-bit, RBR đọc 8 bit thấp. RX không xác minh stop-bit và không gán framing flag. **STATIC CONFIRMED GAP:** `err_clr_i` nối `1'b1`; vì nhánh clear ưu tiên trong `uart_rx`, `err_o` bị xóa mỗi cạnh clock và parity-error không được lưu. SAVE_DATA còn diễn ra trước PARITY — rủi ro thứ hai nếu sau này patch.
6. **FIFO:** FCR[1] clear RX, [2] clear TX, [7:6] chọn ngưỡng 1/4/8/14; FCR[0] không enable. PREADY không backpressure khi TX full.
7. **Interrupt:** IER[0] dự kiến RX, [1] TX-empty, [2] lỗi. **STATIC CONFIRMED WIRING GAP:** `RDA_i` nối `LSR[5]` (TX FIFO empty) thay vì RX-ready; khi IER[0]=1 và TX FIFO empty, RX FIFO empty, một IRQ RX sai nguồn có thể xuất hiện sau clock. RX threshold dùng `==` chứ không phải `>=`; CTI_i=0. **Không thể chỉ dựa event_o để đo threshold** nếu RDA giả đã set; cần tạo điều kiện test cô lập hoặc quan sát internals có kiểm soát.
8. **Reset:** RSTN async low. LSR/IIR có trạng thái động; test snapshot tại assert reset và sau release. **IIR reset nội bộ `4'b0001` nhưng APB read IIR khi chưa có interrupt là `8'hC1`** vì ghép thêm các bit fixed (`0xC0`). `regs_q[IIR]=8'h01` không phải nguồn readback bus. Sau bật IER, IIR có thể đổi và ngắt có thể tự tái khẳng định dù đã đọc IIR/LSR.

## D. Bảng truy vết SPEC → Test Case → Coverage (dự thảo)

TC là gợi ý cho Yêu cầu 2, **chưa phải test đã chạy**. P0=phải làm sớm, P1=regression chức năng, P2=negative/gap.

| Requirement | Test ID | Class | Priority | Checker/coverage |
|---|---|---|---|---|
| REQ_APB_001 | TC_APB_PROTOCOL | TESTBENCH/MASTER | P0 | SETUP→ACCESS; controls stable |
| REQ_APB_002 | TC_APB_WRITE_GATING | RTL-CONTRACT | P0 | không ghi idle/setup/read |
| REQ_APB_003 | TC_APB_READ_GATING | RTL-CONTRACT | P0 | PRDATA ngoài valid read |
| REQ_APB_004 | TC_APB_READY_ERR | RTL-CONTRACT | P0 | PREADY=1, PSLVERR=0 |
| REQ_APB_005 | TC_APB_ALIAS | RTL-CONTRACT | P0 | offsets và high-bit alias |
| REQ_REG_001 | TC_REG_ADDR_ACCESS | RTL-CONTRACT | P0 | address×dir×DLAB |
| REQ_REG_002 | TC_REG_DLAB | RTL-CONTRACT | P0 | DLAB switching |
| REQ_REG_003 | TC_REG_DATA_WIDTH | RTL-CONTRACT | P1 | low byte, zero-extend |
| REQ_REG_004 | TC_RESET_REG + TC_REG_IIR_READBACK | RTL-CONTRACT | P0 | reset snapshot; APB IIR=`0xC1` khi chưa ngắt, khác internal register |
| REQ_REG_005 | TC_REG_UNIMPLEMENTED | RTL-CONTRACT | P1 | 4/6/7 read 0, writes ignored |
| REQ_TX_001 | TC_TX_THR | RTL-CONTRACT | P0 | THR→TX FIFO→serial |
| REQ_TX_002 | TC_TX_FRAME | RTL-CONTRACT | P0 | start/data/parity/stop |
| REQ_TX_003 | TC_TX_DATABITS | RTL-CONTRACT | P1 | 5/6/7/8 bits, LSB first |
| REQ_TX_004 | TC_TX_PARITY_STOP | RTL-CONTRACT + GUIDE-GAP | P1 | even/none; odd unsupported; 1/2 stop |
| REQ_TX_005 | TC_TX_BAUD_MEASURE | INVESTIGATION | P0 | bit clocks; compare target baud |
| REQ_RX_001 | TC_RX_VALID_FRAME | RTL-CONTRACT | P0 | serial input→RBR |
| REQ_RX_002 | TC_RX_RBR_POP | RTL-CONTRACT | P0 | oldest byte, one pop |
| REQ_RX_003 | TC_RX_LSR_DR | RTL-CONTRACT | P0 | LSR[0] FIFO nonempty |
| REQ_RX_004 | TC_RX_PARITY_FAULT | GUIDE-GAP (static confirmed) | P0 | lỗi parity đầu vào; `err_o` bị clear cố định, LSR[2] không báo như guide |
| REQ_RX_005 | TC_RX_FRAMING_OVERRUN_GAP | GUIDE-GAP | P2 | unsupported FE/OE |
| REQ_FIFO_001 | TC_FIFO_RESET_CLEAR | RTL-CONTRACT | P1 | reset/clear TX/RX |
| REQ_FIFO_002 | TC_FIFO_ORDER_FULL | RTL-CONTRACT | P1 | ordering, full/overflow |
| REQ_FIFO_003 | TC_FIFO_THRESH | RTL-CONTRACT | P1 | 1/4/8/14; T-1/T/T+1 |
| REQ_INT_001 | TC_INT_SOURCES_CLEAR | RTL-CONTRACT + INVESTIGATION | P1 | IER/IIR/event/read-clear |
| REQ_INT_002 | TC_INT_RX_RDA_BUG | GUIDE-GAP (static wiring confirmed) | P0 | RX empty+TX empty+IER[0]=1; chứng minh IRQ sai nguồn/clear reassert |

REQ_SYS_001...REQ_SYS_011 chuyển sang **SYSTEM-FPGA** (Yêu cầu 3), không trộn với DUT UVM.

### D.1. P0 smoke → risk progression

1. APB_PROTOCOL + READY_ERR + REG_DLAB: reset, register read/write.
2. TX_BAUD_MEASURE: đo tốc độ thật (không hardcode divisor 27 hoặc 433).
3. TX_THR + TX_FRAME: ký tự 0x41, 8N1.
4. RX_VALID_FRAME + RX_RBR_POP + RX_LSR_DR: nhận byte, kiểm queue.
5. RX_PARITY_FAULT + INT_RX_RDA_BUG: định tính các nghi vấn lớn trước constrained random.

## E. UVM topology & sampling

~~~text
tb_top: clock/reset/APB interface/UART pins + DUT
 +-- uvm_test
      +-- uvm_env
           +-- active APB agent: sequencer, driver, monitor
           +-- UART RX BFM + UART TX monitor
           +-- APB register/reference model with DLAB
           +-- TX frame scoreboard (independent model)
           +-- RX-to-RBR FIFO scoreboard
           +-- interrupt/LSR checker + coverage subscriber
~~~

- APB monitor phải sample PRDATA trong ACCESS tại cạnh hoàn tất **trước** việc FIFO pop/NBA làm thay đổi dữ liệu.
- UART monitor chờ start-bit falling edge, sample ở giữa từng bit; configurable baud.
- Reset clear prediction queues và pending traffic; không so sánh dữ liệu pre-reset với post-reset.
- Scoreboard dùng model độc lập từ APB stimulus và UART frame format, không lấy state nội bộ của DUT làm oracle.
- Sử dụng constraint hợp lệ trước, tạo negative/unsupported tests riêng. Công cụ simulator/UVM library sẽ được chọn khi triển khai.

## F. Coverage targets khi viết DV Plan

- APB access(read/write) × PADDR[2:0] × DLAB; cover no-select/setup/access/alias.
- TX: 5/6/7/8 data bits × parity_on/off × 1/2 stop; patterns 00,FF,55,AA,41,random.
- RX: mode × valid/invalid parity; FIFO occupancy 0/1/T-1/T/T+1/15/16 (T=1,4,8,14; loại bỏ bin âm).
- FIFO: empty/partial/full × push/pop/clear; read-empty/write-full; simultaneous events nếu reachable.
- Interrupt: IER mask × event_o × IIR; TX empty/busy, RX empty/nonempty, threshold selection.
- **Coverage hit không phải test PASS**; yêu cầu checker/assertion và report bug rõ ràng.

## G. Bàn giao & OPEN items

| Điều kiện | Trạng thái |
|---|---|
| SPEC/REQ IDs, discrepancy register, handoff matrix | YES |
| 5 RTL files + src_files.yml + LICENSE cố định | YES |
| APB/decoder, read side effects, reset semantics | YES (static review) |
| Thiết kế topological UVM và test priority | READY AS DRAFT |
| Simulator/UVM library, tool versions | OPEN |
| Baud exact, parity RX, RDA interrupt, FIFO edge | Baud/FIFO: OPEN; parity/RDA: STATIC CONFIRMED wiring issue, waveform NOT RUN |
| Board pinout/Top-Level | OPEN — Yêu cầu 3 |
| Regression/test pass evidence | NOT RUN |

**Kết luận:** Có thể bắt đầu DV Plan và viết skeleton UVM ngay; chưa được coi SPEC v1.0 signed-off. Mỗi OPEN phải được cập nhật sau khi có waveform/log.
