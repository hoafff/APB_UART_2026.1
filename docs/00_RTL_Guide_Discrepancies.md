# ĐỐI CHIẾU `Huongdan_UART.md` VỚI RTL PULP — ISSUE & DISCREPANCY REGISTER

> **Trạng thái:** v0.1, 29/10/2026 — phân tích tĩnh mã nguồn, **chưa chạy mô phỏng/FPGA**.  
> **Nguồn hướng dẫn:** `Huongdan_UART.md` do giảng viên cung cấp.  
> **Nguồn RTL chuẩn:** [`pulp-platform/apb_uart_sv` tại commit `dfad6e04d19cc9481d3cd2750b45b970dc61271b`](https://github.com/pulp-platform/apb_uart_sv/tree/dfad6e04d19cc9481d3cd2750b45b970dc61271b).  
> **Quy tắc:** Dùng RTL khi xác định **hành vi thực tế của DUT**; vẫn giữ phần hướng dẫn như **mục tiêu thiết kế/kiểm thử**. Các mục nghi vấn không tự động được kết luận là lỗi cho đến khi mô phỏng xác nhận.

**Mức độ:** `BLOCKER` = sai sẽ cản hoạt động chính; `HIGH` = sai lệch chức năng quan trọng; `MEDIUM` = hành vi hạn chế/điểm cần làm rõ; `INFO` = điều kiện hoặc đầu việc còn thiếu.

## 1. Tổng hợp nhanh

| ID | Mức độ | Vấn đề | Hướng xử lý ngay |
|---|---|---|---|
| **DIF-01** | BLOCKER | Offset thanh ghi **khác** `0x00,0x04,0x08,...` trong hướng dẫn | Master phải dùng offset RTL `0,1,2,3,5` |
| **DIF-02** | BLOCKER | Baud divisor **không có hệ số 16** như hướng dẫn | Không ghi DLL=27; đo baud bằng simulation |
| **DIF-03** | HIGH | Odd/Even parity qua `SW[15]` không có trong RTL DUT | Giới hạn tính năng, ưu tiên even parity/no parity |
| **DIF-04** | HIGH | RX framing error/stop-bit validation không được triển khai theo mô tả | Không gán testcase FE là expected pass |
| **DIF-05** | HIGH | LSR overrun cờ `[1]` không được cập nhật khi FIFO đầy | Test FIFO full/drop, không mặc định có OE |
| **DIF-06** | MEDIUM | `FCR[0]` không điều khiển enable FIFO | Ghi 0x07 chỉ có clear RX/TX và trigger selection |
| **DIF-07** | HIGH | Interrupt `RDA_i` nhận **LSR[5]** thay vì tín hiệu RX data ready | Đo `event_o`, IIR trước khi dùng ngắt để polling |
| **DIF-08** | HIGH/OPEN | Thứ tự RX SAVE_DATA và PARITY + clear error liên tục | Mô phỏng kiểm tra parity error từng byte |
| **DIF-09** | MEDIUM | Một số thanh ghi kiểu 16550 chỉ được **khai báo tên**, chưa có read/write | Đặc tả đúng subset hỗ trợ |
| **DIF-10** | INFO | Source Top-Level `de2_115_apb_uart_bringup.sv` **không có** trong repo PULP | Tự viết hoặc nhận code từ thầy |
| **DIF-11** | MEDIUM | Ngưỡng FIFO interrupt dùng so sánh `==`, không phải `>=` | Test ngưỡng và vượt ngưỡng |
| **DIF-12** | INFO | DUT đã có đồng bộ RX 3-bit; hướng dẫn yêu cầu thêm 2-FF ở wrapper | Giữ kiến trúc hướng dẫn, đo thêm độ trễ |
| **DIF-13** | INFO/OPEN | Chân pin/voltage từ hướng dẫn không thể kiểm chứng bằng RTL DUT | Kiểm tra DE2-115 manual + Pin Planner |

---

## 2. Đối chiếu chi tiết và bằng chứng

### DIF-01 — Register map byte-offset khác word-aligned (BLOCKER)

**Hướng dẫn:** Phần 3A/4 ghi `LCR=0x0C`, `LSR=0x14`, `IER/DLM=0x04`, `FCR=0x08`, với word-aligned 32-bit.

**RTL:** [`apb_uart_sv.sv` – định nghĩa các hằng thanh ghi](https://github.com/pulp-platform/apb_uart_sv/blob/dfad6e04d19cc9481d3cd2750b45b970dc61271b/apb_uart_sv.sv#L34-L43), [decoder `register_adr = PADDR[2:0]`](https://github.com/pulp-platform/apb_uart_sv/blob/dfad6e04d19cc9481d3cd2750b45b970dc61271b/apb_uart_sv.sv#L342-L346). Các offset thực tế:

| Thanh ghi | Hướng dẫn | RTL dùng |
|---|---|---|
| RBR/THR/DLL | `0x00` | `0x0` |
| IER/DLM | `0x04` | `0x1` |
| IIR/FCR | `0x08` | `0x2` |
| LCR | `0x0C` | `0x3` |
| LSR | `0x14` | `0x5` |

**Hậu quả:** Nếu ghi `0x0C`, decoder lấy `3'b100` nên **không ghi LCR**. `0x14` cũng thành `3'b100`, không đọc LSR. Vì chỉ dùng 3 bit thấp, địa chỉ alias theo chu kỳ 8.

**Quyết định:** Đưa offset RTL vào SPEC, APB Master, UVM RAL và mọi testcase. Không tự sửa địa chỉ DUT.

### DIF-02 — Baud divisor 27 không phù hợp RTL (BLOCKER)

**Hướng dẫn:** Phần 3B: `Divisor = round(50e6/(16×115200)) = 27`, gán `DLL=0x1B`, `DLM=0x00`.

**RTL:** [`uart_tx.sv` bộ đếm](https://github.com/pulp-platform/apb_uart_sv/blob/dfad6e04d19cc9481d3cd2750b45b970dc61271b/uart_tx.sv#L182-L209) so sánh trực tiếp `baud_cnt==cfg_div_i`; [`uart_rx.sv` bộ đếm](https://github.com/pulp-platform/apb_uart_sv/blob/dfad6e04d19cc9481d3cd2750b45b970dc61271b/uart_rx.sv#L202-L237) cũng dùng trực tiếp divisor. Không có chia 16 lần như bảng hướng dẫn.

**Hậu quả:** DLL=27 tạo chu kỳ bit ngắn hơn nhiều so với 115200 ở 50MHz. Số clock lý tưởng trên bit = `50e6/115200 ≈ 434.03`. Giá trị divisor khảo sát ban đầu ở khoảng `432–433`, nhưng các chu kỳ phụ của FSM có thể ảnh hưởng kết quả.

**Quyết định:** Chưa khóa divisor vội. Làm test đo thời gian giữa các cạnh TX và loopback RX để chọn đúng DLL/DLM. Không khẳng định giá trị 432 hay 433 đã được thử nghiệm.

### DIF-03 — Chọn Odd/Even parity trong hướng dẫn không đi qua DUT (HIGH)

**Hướng dẫn:** Phần 2/5 yêu cầu `SW[14]` bật parity và `SW[15]` chọn odd/even; phần 3 mô tả LCR `[5:3]` cấu hình parity.

**RTL:** [`apb_uart_sv.sv`, kết nối TX/RX](https://github.com/pulp-platform/apb_uart_sv/blob/dfad6e04d19cc9481d3cd2750b45b970dc61271b/apb_uart_sv.sv#L75-L111) chỉ truyền `regs_q[LCR][3]` vào `cfg_parity_en_i`. `LCR[4]` và `LCR[5]` không điều khiển thuật toán chọn parity. [`uart_tx.sv`](https://github.com/pulp-platform/apb_uart_sv/blob/dfad6e04d19cc9481d3cd2750b45b970dc61271b/uart_tx.sv) phát parity là XOR tích lũy, phù hợp với **even parity**.

**Quyết định:** Chỉ ghi hỗ trợ **no parity/even parity** theo RTL; chọn odd qua `SW[15]` là mục tiêu của hướng dẫn nhưng **không thể thực hiện chỉ bằng ghi thanh ghi**. Không thay DUT để có odd parity nếu chưa thống nhất phạm vi sửa RTL.

### DIF-04 — Thiếu kiểm tra framing/stop-bit ở RX (HIGH)

**Hướng dẫn:** Phần 1.1/3A nói `uart_rx` phát hiện lỗi khung truyền và `LSR[3]` báo framing error.

**RTL:** [`uart_rx.sv`](https://github.com/pulp-platform/apb_uart_sv/blob/dfad6e04d19cc9481d3cd2750b45b970dc61271b/uart_rx.sv#L140-L162) có state STOP_BIT nhưng không thấy điều kiện báo lỗi khi stop bit=0; [`apb_uart_sv.sv`](https://github.com/pulp-platform/apb_uart_sv/blob/dfad6e04d19cc9481d3cd2750b45b970dc61271b/apb_uart_sv.sv#L199-L213) không có logic gán `LSR[3]`. `uart_rx` không có port `cfg_stop_bits_i` (dòng được comment trong DUT), còn TX có hỗ trợ stop bit 1/2.

**Quyết định:** Tạo test framing như kiểm tra **giới hạn thực hiện**, không coi `FE=1` là expected pass của bản DUT gốc.

### DIF-05 — Overrun/LSR[1] không báo như hướng dẫn (HIGH)

**Hướng dẫn:** Phần 3A/5 mô tả RX FIFO tràn sẽ bật `LSR[1]`; `SW[16]` dừng đọc để gây lỗi overrun.

**RTL:** [`io_generic_fifo.sv`](https://github.com/pulp-platform/apb_uart_sv/blob/dfad6e04d19cc9481d3cd2750b45b970dc61271b/io_generic_fifo.sv) chỉ đẩy khi `valid_i && !full`; [`apb_uart_sv.sv`](https://github.com/pulp-platform/apb_uart_sv/blob/dfad6e04d19cc9481d3cd2750b45b970dc61271b/apb_uart_sv.sv#L198-L213) không cập nhật `LSR[1]`.

**Quyết định:** Thử khả năng FIFO đầy và mất byte; cờ OE không coi là có thật. Ghi rõ trong kết quả nếu requirement của hướng dẫn không được đáp ứng.

### DIF-06 — `FCR[0]` không bật/tắt FIFO (MEDIUM)

**Hướng dẫn:** Phần 3A/4: ghi FCR `0x07` để bật và xóa FIFO.

**RTL:** [`apb_uart_sv.sv`, FCR write](https://github.com/pulp-platform/apb_uart_sv/blob/dfad6e04d19cc9481d3cd2750b45b970dc61271b/apb_uart_sv.sv#L239-L249) chỉ xử lý `PWDATA[1]`, `[2]`, `[7:6]`; **không đọc bit `[0]`**. Hai FIFO luôn được instantiate.

**Quyết định:** SPEC ghi `FCR=0x07` tạo xung clear TX/RX, không ghi là đã bật FIFO; test rõ việc bit0 không làm thay đổi chức năng.

### DIF-07 — Nguồn RDA interrupt nối sai tín hiệu kỳ vọng (HIGH)

**Hướng dẫn:** Phần 3A/4/5 mong `IER[0]` bật ngắt khi RX có dữ liệu và `event_o` phản ánh sự kiện nhận.

**RTL:** [`apb_uart_sv.sv`, instance `uart_interrupt`](https://github.com/pulp-platform/apb_uart_sv/blob/dfad6e04d19cc9481d3cd2750b45b970dc61271b/apb_uart_sv.sv#L167-L185) nối `.RDA_i(regs_n[LSR][5])`; nhưng trong cùng file [`LSR[5]` được gán trạng thái **TX FIFO empty**](https://github.com/pulp-platform/apb_uart_sv/blob/dfad6e04d19cc9481d3cd2750b45b970dc61271b/apb_uart_sv.sv#L205-L212). Phần RX-data-ready là `LSR[0]`.

**Quyết định:** Ghi là **nghi vấn nối sai** có bằng chứng. Viết test tách trường hợp `TX empty, RX empty`, `TX busy, RX has data`, `TX empty, RX has data` để đo `event_o` và IIR. Không khẳng định ngay mọi ngắt RX đều sai nếu chưa mô phỏng.

### DIF-08 — Parity error RX có rủi ro bị gắn sai/mất (HIGH/OPEN)

**Hướng dẫn:** Phần 3A yêu cầu LSR[2] báo parity error khi khung nhận sai.

**RTL:** [`uart_rx.sv`](https://github.com/pulp-platform/apb_uart_sv/blob/dfad6e04d19cc9481d3cd2750b45b970dc61271b/uart_rx.sv#L119-L152) đi qua `SAVE_DATA` (phát `rx_valid_o`) **trước** `PARITY` (mới set error). [`apb_uart_sv.sv`](https://github.com/pulp-platform/apb_uart_sv/blob/dfad6e04d19cc9481d3cd2750b45b970dc61271b/apb_uart_sv.sv#L74-L98) nối `.err_clr_i(1'b1)`, đồng thời [FIFO lưu `{parity_error,rx_data}`](https://github.com/pulp-platform/apb_uart_sv/blob/dfad6e04d19cc9481d3cd2750b45b970dc61271b/apb_uart_sv.sv#L115-L139). Trong [`uart_rx.sv`](https://github.com/pulp-platform/apb_uart_sv/blob/dfad6e04d19cc9481d3cd2750b45b970dc61271b/uart_rx.sv#L242-L260), `err_clr_i` có ưu tiên trên `set_error`.

**Quyết định:** Đây là rủi ro đặc biệt quan trọng; cần directed test gửi byte có parity lỗi xen kẽ byte hợp lệ, đọc RBR + LSR theo từng byte, xem cả waveform nội bộ trước khi kết luận. Không dựa vào `LSR[2]` làm oracle tuyệt đối.

### DIF-09 — Chuẩn 16550 được triển khai dạng subset (MEDIUM)

**Hướng dẫn:** Phần 3 gọi đây là quản lý "thanh ghi chuẩn 16550", dễ hiểu là có đầy đủ register map.

**RTL:** [`apb_uart_sv.sv`](https://github.com/pulp-platform/apb_uart_sv/blob/dfad6e04d19cc9481d3cd2750b45b970dc61271b/apb_uart_sv.sv#L214-L306) chỉ thấy thực thi các case ghi THR/DLL, IER/DLM, LCR, FCR; đọc RBR/DLL, LSR, LCR, IER/DLM, IIR. Các hằng MCR/MSR/SCR có khai báo nhưng không có read/write ở case.

**Quyết định:** Ghi chính xác các thanh ghi **được hỗ trợ** trong SPEC; không tự suy ra những thanh ghi 16550 còn lại hoạt động.

### DIF-10 — File Top-Level chỉ là mã được yêu cầu, chưa được cung cấp (INFO)

**Hướng dẫn:** Phần 1 khẳng định `de2_115_apb_uart_bringup.sv` chứa APB Master, debouncer và 7-seg decoder.

**Repo PULP:** [`src_files.yml`](https://github.com/pulp-platform/apb_uart_sv/blob/dfad6e04d19cc9481d3cd2750b45b970dc61271b/src_files.yml) chỉ liệt kê 5 RTL DUT, không có Top-Level này.

**Quyết định:** Không coi Top-Level đã có hay compile-ready. Phải tự tạo hoặc lấy file mã mẫu và rà soát với spec mới trước khi làm FPGA. Đây là *thiếu file ngoài repo*, không phải lỗi DUT.

### DIF-11 — FIFO trigger chỉ so sánh bằng mức đích (MEDIUM)

**Hướng dẫn:** Nêu khả năng RX interrupt khi có dữ liệu, không đi sâu điều kiện ngưỡng.

**RTL:** [`uart_interrupt.sv`](https://github.com/pulp-platform/apb_uart_sv/blob/dfad6e04d19cc9481d3cd2750b45b970dc61271b/uart_interrupt.sv#L39-L60) dùng `rx_elements_i == 1/4/8/14`, không dùng `>=`.

**Quyết định:** Thử với số phần tử ở `threshold-1`, `threshold`, `threshold+1`. Đây là lưu ý bổ sung về hành vi RTL, không nhất thiết là mâu thuẫn trực tiếp.

### DIF-12 — Đồng bộ RX hai tầng ngoài wrapper và ba bit trong DUT (INFO)

**Hướng dẫn:** Phần 3/2 khuyến nghị thêm 2-FF synchronizer trước `rx_i`.

**RTL:** [`uart_rx.sv`](https://github.com/pulp-platform/apb_uart_sv/blob/dfad6e04d19cc9481d3cd2750b45b970dc61271b/uart_rx.sv#L185-L200) đã có `reg_rx_sync[2:0]` dịch dữ liệu theo clock.

**Quyết định:** Không phải xung đột chức năng; chỉ cần đánh giá lại latency/timing khi có cả hai tầng ở ngoài và trong DUT. Trong UVM DUT-level thì lái `rx_i` trực tiếp theo UART stimulus.

### DIF-13 — Pin assignment chưa có bằng chứng độc lập trong RTL (INFO/OPEN)

**Hướng dẫn:** Phần 5 cung cấp JP5, `PIN_AB22`, `PIN_AB21`, nhóm HEX/LED/SW và chuẩn 2.5/3.3 V.

**RTL:** RTL `apb_uart_sv` không thể chứng minh đúng pinout của board DE2-115. 

**Quyết định:** Giữ bảng pin trong SPEC ở trạng thái **[GUIDE — CHƯA XÁC MINH]**. Trước khi đấu dây, đối chiếu DE2-115 manual, sơ đồ board và Quartus Pin Planner; đảm bảo CP2102 I/O level tương thích. Không nối chân VCC CP2102 vào FPGA theo hướng dẫn.

---

## 3. Kiểm tra ưu tiên khi làm DV Plan và FPGA

1. **Trước UVM:** Bắt đầu bằng APB register read/write, kiểm tra địa chỉ đúng `0x0/0x1/0x2/0x3/0x5` và DLAB (DIF-01); test TX baud và RX loopback (DIF-02).
2. **Sau đó:** Directed tests TX/RX, FIFO full/clear, kiểm tra parity-error và interrupt (DIF-03 đến DIF-08); ghi nhận mọi sai khác giữa expected/observed.
3. **Trước FPGA:** Xây dựng Top-Level đúng offset và baud; sau đó kiểm tra GPIO/pin/voltage (DIF-10, DIF-13). Chức năng Odd/Even, Framing Error và Overrun indicator phải có ghi chú giới hạn, không quảng bá như đã pass.

### Mẫu ghi nhận kết quả kiểm chứng

| Cột | Ý nghĩa |
|---|---|
| `Issue ID` | Ví dụ DIF-07 |
| `Test ID` | Ví dụ TC_INT_RDA_01 |
| `Requirement` | `REQ_INT_001` hoặc mã `REQ_...` tương ứng |
| `Expected from RTL` | Hành vi cụ thể được code định nghĩa |
| `Expected from guide` | Mục tiêu thầy mô tả (nếu khác) |
| `Observed` | Kết quả waveform/FPGA thực tế |
| `Verdict` | Pass / RTL divergence / Bug confirmed / Open |
| `Evidence` | Simulation log, waveform, commit, screenshot |

---

## 4. Chính sách cập nhật

- **Không đổi DUT gốc** chỉ để làm cho các test theo hướng dẫn pass.
- Khi có bằng chứng mô phỏng, cập nhật trạng thái mục tương ứng: `OPEN → CONFIRMED` hoặc `OPEN → CLOSED / NOT A BUG`.
- Mọi sửa lỗi (nếu giảng viên đồng ý) phải thực hiện riêng nhánh và nêu rõ khác biệt với commit gốc; test cả **original DUT** lẫn **patched DUT** nếu cần.
- Tài liệu này là nhật ký sai khác, không tự thay thế Verification Plan.

**Tài liệu SPEC chính:** [`01_System_Specification.md`](01_System_Specification.md).