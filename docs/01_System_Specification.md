# SYSTEM SPECIFICATION — APB UART SV

> **Đề tài:** Kiểm thử giao thức truyền thông UART sử dụng giao tiếp APB  
> **DUT:** `pulp-platform/apb_uart_sv` trên FPGA Altera/Terasic DE2-115 (Cyclone IV E)  
> **Phiên bản:** 0.1 — *Draft, phân tích tĩnh RTL; chưa có kết quả mô phỏng/FPGA*  
> **Ngày lập:** 29/10/2026  
> **Repo bài tập:** https://github.com/hoafff/APB_UART_2026.1

## 0. Nguồn tài liệu, quy tắc ưu tiên và ký hiệu

**Ba yêu cầu của giảng viên:** (1) Specifications; (2) DV Plan, Test Case, môi trường UVM và directed/automatic/random/coverage; (3) kiểm thử trên DE2-115.

**Nguồn tham chiếu:**

1. `Huongdan_UART.md` do giảng viên cung cấp — định hướng hệ thống và thử nghiệm FPGA.
2. [PULP APB UART SV](https://github.com/pulp-platform/apb_uart_sv), nhánh `pulpinov1`, **commit cố định** [`dfad6e04d19cc9481d3cd2750b45b970dc61271b`](https://github.com/pulp-platform/apb_uart_sv/tree/dfad6e04d19cc9481d3cd2750b45b970dc61271b) — nguồn chuẩn về hành vi RTL của DUT.
3. Đề bài cuối kỳ do giảng viên công bố — nguồn chuẩn về **phạm vi nộp bài**.

**Quy tắc:** Khi `Huongdan_UART.md` và RTL mâu thuẫn về hoạt động của DUT, **lấy RTL ở commit cố định** để mô tả và làm oracle kiểm thử. Khi RTL chưa thực hiện chức năng mà hướng dẫn yêu cầu, giữ yêu cầu ở phần *mong muốn/đề xuất* và ghi *giới hạn hoặc nghi vấn*; **không tự nhận là DUT đã hỗ trợ**. Các khác biệt được lưu tại [`00_RTL_Guide_Discrepancies.md`](00_RTL_Guide_Discrepancies.md).

| Ký hiệu | Ý nghĩa |
|---|---|
| **[RTL]** | Quan sát trực tiếp từ mã nguồn PULP tại commit đã khóa |
| **[GUIDE]** | Chức năng hoặc cấu hình do `Huongdan_UART.md` mô tả |
| **[PLAN]** | Yêu cầu thiết kế/kiểm chứng được đề xuất cho đồ án |
| **[OPEN]** | Phải kiểm chứng thêm bằng mô phỏng, đối chiếu datasheet hoặc FPGA |

---

## 1. Giới thiệu và phạm vi

### 1.1. Mục tiêu

Xây dựng đặc tả cho một hệ thống tích hợp IP UART có giao diện **APB Slave**; dùng tài liệu này làm cơ sở tạo **DV Plan + UVM testbench**, rồi triển khai một **FPGA bring-up** trên DE2-115 kết nối máy tính qua USB–UART CP2102.

### 1.2. Phân định DUT và hệ thống

- **DUT (Design Under Test):** module `apb_uart_sv` cùng các module con được instantiate trong nó. DUT **không** bao gồm APB Master, nút bấm, LED/HEX, CP2102.
- **Verification environment:** UVM testbench (APB agent, UART stimulus/monitor, scoreboard, coverage), chạy trong simulator, **không tổng hợp lên FPGA**.
- **FPGA system/top-level:** `de2_115_apb_uart_bringup` (cần viết hoặc lấy mẫu từ giảng viên) gồm APB Master FSM, bộ chống rung, đồng bộ tín hiệu ngoại vi, giải mã HEX, LED và kết nối DUT.

### 1.3. Sơ đồ tổng quan

```text
                               DE2-115 FPGA
  KEY[1] ─> Debouncer ─┐
  SW[17:0] ─────────────┼─> APB Master FSM ── APB ──> +---------------------+
  CLOCK_50/KEY[0] ──────┘                         ┌──> | apb_uart_sv (DUT)   |
                                                │    | Register bank      |
  CP2102 TXD ─> GPIO_UART_RX ─> [sync] ─> rx_i ─┘    | uart_rx / uart_tx    |
  CP2102 RXD <─ GPIO_UART_TX <──────────── tx_o <──── | TX/RX FIFO, interrupt|
                                                     +----------+----------+
                                                                │ event_o
                       HEX/LED <── APB read data / status <───────┘
```

[GUIDE] Hệ thống điều khiển gửi một byte từ `SW[7:0]` khi bấm `KEY[1]`, nhận dữ liệu từ PC và hiển thị HEX, hỗ trợ Echo Mode `SW[17]` và tùy chọn dừng đọc RX `SW[16]`. Đây là **đặc tả của FPGA wrapper**, không phải port sẵn có của DUT.

---

## 2. Cấu trúc RTL và cấu hình tham số

### 2.1. File RTL phải đưa vào project

Danh sách đúng theo [`src_files.yml`](https://github.com/pulp-platform/apb_uart_sv/blob/dfad6e04d19cc9481d3cd2750b45b970dc61271b/src_files.yml):

| File | Module và chức năng |
|---|---|
| `apb_uart_sv.sv` | APB Slave, bank thanh ghi, ghép TX/RX/FIFO/interrupt |
| `uart_tx.sv` | FSM UART Transmitter, phát `tx_o` |
| `uart_rx.sv` | FSM UART Receiver, lấy mẫu `rx_i` |
| `io_generic_fifo.sv` | FIFO generic được instantiate **hai lần**: TX và RX |
| `uart_interrupt.sv` | Tạo `event_o`, mã IIR |

Ngoài 5 file trên, cần source `de2_115_apb_uart_bringup.sv` do người thực hiện cung cấp. Repo còn chứa `apb_uart.sv` cùng định nghĩa module `apb_uart_sv`: **không đưa đồng thời** `apb_uart.sv` và `apb_uart_sv.sv` vào danh sách biên dịch để tránh trùng module.

### 2.2. Tham số [RTL]

| Tham số | Mặc định | Ý nghĩa |
|---|---:|---|
| `APB_ADDR_WIDTH` | 12 | Độ rộng cổng `PADDR` (mặc dù decoder chỉ dùng `PADDR[2:0]`) |
| `TX_FIFO_DEPTH` | 16 | Độ sâu FIFO truyền tính theo byte |
| `RX_FIFO_DEPTH` | 16 | Độ sâu FIFO nhận tính theo byte |
| TX FIFO `DATA_WIDTH` | 8 | Byte truyền |
| RX FIFO `DATA_WIDTH` | 9 | Byte nhận + 1 bit parity-error kèm theo |

---

## 3. Giao diện bên ngoài DUT [RTL]

Đối chiếu khai báo module [tại đây](https://github.com/pulp-platform/apb_uart_sv/blob/dfad6e04d19cc9481d3cd2750b45b970dc61271b/apb_uart_sv.sv#L11-L33).

| Port | Chiều | Độ rộng | Ý nghĩa |
|---|---|---:|---|
| `CLK` | input | 1 | Clock chung của DUT |
| `RSTN` | input | 1 | Reset tích cực thấp; dùng trong `always_ff @(posedge CLK, negedge RSTN)` |
| `PADDR` | input | `APB_ADDR_WIDTH` (12) | Địa chỉ APB; decoder xét `PADDR[2:0]` |
| `PWDATA` | input | 32 | Dữ liệu ghi APB; logic thanh ghi sử dụng `PWDATA[7:0]` và một số bit cấu hình |
| `PWRITE` | input | 1 | 1 = write, 0 = read |
| `PSEL` | input | 1 | Chọn APB Slave |
| `PENABLE` | input | 1 | Pha ACCESS APB |
| `PRDATA` | output | 32 | Dữ liệu đọc; các thanh ghi 8-bit zero-extend lên 32-bit |
| `PREADY` | output | 1 | Luôn 1 trong RTL gốc |
| `PSLVERR` | output | 1 | Luôn 0 trong RTL gốc |
| `rx_i` | input | 1 | UART serial receive |
| `tx_o` | output | 1 | UART serial transmit |
| `event_o` | output | 1 | Interrupt/event từ `uart_interrupt` |

**Mặc định hệ thống FPGA:** [GUIDE] `CLOCK_50 = 50 MHz`, reset từ `KEY[0]`, UART TX/RX đi tới CP2102 qua GPIO.

---

## 4. Giao thức APB và điều kiện truy cập

### 4.1. Pha giao dịch [PLAN]

1. **IDLE:** `PSEL=0`, không có giao dịch.
2. **SETUP:** Master đặt ổn định `PADDR`, `PWRITE`, `PWDATA` (nếu ghi), `PSEL=1`, `PENABLE=0`.
3. **ACCESS:** giữ địa chỉ/chiều/dữ liệu, `PSEL=1`, `PENABLE=1`; lấy mẫu giao dịch tại cạnh lên `CLK` khi `PREADY=1`.
4. **COMPLETE:** Master bỏ `PSEL` hoặc chuyển sang giao dịch tiếp theo đúng quy tắc APB.

### 4.2. Hành vi đặc thù [RTL]

- Điều kiện ghi: `PSEL && PENABLE && PWRITE`.
- Điều kiện đọc: `PSEL && PENABLE && !PWRITE`.
- `PREADY = 1'b1` và `PSLVERR = 1'b0` không đổi: Slave không phát wait-state và không báo lỗi truy cập.
- Đọc `PRDATA` được tạo từ logic tổ hợp, mặc định `0` nếu không đọc hoặc truy cập thanh ghi không hỗ trợ.
- APB Master không được giữ một giao dịch WRITE ở ACCESS qua nhiều cạnh lên clock vì có thể tạo tác dụng phụ nhiều lần (như đẩy nhiều byte vào FIFO).
- **Decoder dùng `register_adr = PADDR[2:0]`, KHÔNG dùng địa chỉ word-aligned `0x00,0x04,0x08,...` như hướng dẫn.** Đây là khác biệt **DIF-01**.

### 4.3. Các yêu cầu APB

| ID | Yêu cầu |
|---|---|
| `REQ_APB_001` | Master phải phát SETUP trước ACCESS với tín hiệu địa chỉ/chiều/giá trị ghi ổn định. |
| `REQ_APB_002` | DUT chỉ tác động ghi thanh ghi/FIFO khi `PSEL&PENABLE&PWRITE=1`. |
| `REQ_APB_003` | DUT chỉ xuất thông tin thanh ghi đọc khi `PSEL&PENABLE&!PWRITE=1`. |
| `REQ_APB_004` | `PREADY=1` và `PSLVERR=0` theo RTL gốc. |
| `REQ_APB_005` | Kiểm thử địa chỉ theo `PADDR[2:0]`; kiểm tra cả trường hợp alias do bit địa chỉ cao bị bỏ qua. |

---

## 5. Register map của DUT — **theo RTL, không theo bảng địa chỉ hướng dẫn**

Các hằng địa chỉ định nghĩa ở [`apb_uart_sv.sv`](https://github.com/pulp-platform/apb_uart_sv/blob/dfad6e04d19cc9481d3cd2750b45b970dc61271b/apb_uart_sv.sv#L34-L43). Địa chỉ dưới đây là **offset PADDR thực tế**, mỗi địa chỉ liền kề cách nhau 1.

| `PADDR[2:0]` | Read (DLAB=0) | Write (DLAB=0) | Read/Write khi DLAB=1 | Ghi chú |
|---|---|---|---|---|
| `0x0` | RBR | THR | DLL | RBR pop RX FIFO; THR push TX FIFO |
| `0x1` | IER | IER | DLM | Interrupt enable hoặc divisor MSB |
| `0x2` | IIR | FCR | IIR read / FCR write | Không phụ thuộc DLAB |
| `0x3` | LCR | LCR | LCR | Chọn data bits, stop TX, parity enable và DLAB |
| `0x4` | — | — | — | `MCR` được khai báo nhưng không thấy logic read/write |
| `0x5` | LSR | — | LSR read | Line status |
| `0x6` | — | — | — | `MSR` được khai báo nhưng không thấy logic read/write |
| `0x7` | — | — | — | `SCR` được khai báo nhưng không thấy logic read/write |

**Lưu ý:** Các offset có thể alias khi thay đổi `PADDR` bit cao: `PADDR=0x003`, `0x00B`… cùng giải mã thanh ghi `0x3` do decoder chỉ giữ 3 bit thấp. Đây là **hành vi RTL**, không phải khẳng định tương thích một bản đồ memory-mapped APB thông dụng.

### 5.1. Các bit cấu hình và trạng thái

| Thanh ghi | Những bit được RTL sử dụng | Ý nghĩa / hạn chế |
|---|---|---|
| `LCR` | `[7]` | `DLAB`: 1 truy cập DLL/DLM thay RBR/THR/IER |
| `LCR` | `[3]` | Bật parity cho TX/RX; RTL không tiêu thụ bit chọn odd/even `[4]` |
| `LCR` | `[2]` | TX chọn 1 hoặc 2 stop bits; RX không có input cấu hình stop bits |
| `LCR` | `[1:0]` | `00/01/10/11` → 5/6/7/8 data bits |
| `IER` | `[0]`, `[1]`, `[2]` | Cho phép interrupt RX-data, TX-empty, error theo khối interrupt |
| `FCR` | `[1]`, `[2]` | Lệnh clear RX FIFO / TX FIFO (tự xóa sau xung); bit `[0]` không được dùng như enable |
| `FCR` | `[7:6]` | RX FIFO interrupt threshold: mã `00/01/10/11` ứng với 1/4/8/14 phần tử |
| `LSR` | `[0]` | Có phần tử trong RX FIFO (`fifo_rx_valid`) |
| `LSR` | `[2]` | Bit parity-error lấy từ dữ liệu RX FIFO; xem cảnh báo độ tin cậy ở DIF-08 |
| `LSR` | `[5]` | TX FIFO trống; **chưa chắc** shift register đã phát xong |
| `LSR` | `[6]` | Cả TX FIFO trống và TX shift register ready |

Các bit LSR `[1]` (overrun), `[3]` (framing error) không có logic cập nhật tương ứng trong RTL đã đối chiếu; không coi là được hỗ trợ chỉ vì tài liệu hướng dẫn có ghi.

### 5.2. Reset values [RTL]

| Thanh ghi | Giá trị reset |
|---|---|
| `IER` | `0x00` |
| `IIR` (bank lưu nội bộ) | `0x01` |
| `LCR` | `0x00` |
| `MCR`, `MSR`, `SCR` (bank lưu nội bộ) | `0x00` |
| `LSR` | `0x60` |
| `DLL`, `DLM` | `0x00` |
| `trigger_level_q` | `00` |
| TX/RX FIFO | reset số phần tử về 0 |

**Ghi chú:** `IIR` đọc trên bus được lấy từ `uart_interrupt.IIR_o`, không phải trực tiếp từ bản ghi `regs_q[IIR]`. `LSR` có các bit cập nhật động nên giá trị sau vài clock có thể khác giá trị chốt tại thời điểm reset.

### 5.3. Yêu cầu kiểm chứng thanh ghi

| ID | Yêu cầu |
|---|---|
| `REQ_REG_001` | Xác minh các thanh ghi hữu hiệu ở offsets `0x0`, `0x1`, `0x2`, `0x3`, `0x5`. |
| `REQ_REG_002` | `LCR[7]` điều khiển phân trang DLL/DLM với RBR/THR/IER. |
| `REQ_REG_003` | APB 32-bit, dữ liệu thanh ghi chủ yếu nằm ở byte thấp. |
| `REQ_REG_004` | Kiểm thử reset `IER`, `LCR`, `DLL`, `DLM` và các bit trạng thái khả quan sát. |
| `REQ_REG_005` | Truy cập không được triển khai trả `PRDATA=0` và không có `PSLVERR`. |

---

## 6. Đặc tả truyền UART (TX) [RTL]

- Dữ liệu APB ghi `THR` (`PADDR=0x0` khi `DLAB=0`) lấy `PWDATA[7:0]`, đưa vào **TX FIFO 16 phần tử**.
- `uart_tx` nhận byte FIFO theo handshake `tx_valid_i/tx_ready_o`, phát khung: **Start(0) → 5–8 data bits, LSB-first → parity tùy chọn → 1/2 stop bits (1)**.
- Đường `tx_o` ở trạng thái IDLE là `1`.
- Bật parity bởi `LCR[3]`; parity TX hiện thực theo XOR tích lũy, phù hợp even parity; **không có logic chọn odd parity theo `LCR[4]`**.
- `LSR[5]=1` khi TX FIFO không còn phần tử; `LSR[6]=1` khi FIFO trống và bộ phát ở trạng thái ready.

### Baud generator

Ở [`uart_tx.sv`](https://github.com/pulp-platform/apb_uart_sv/blob/dfad6e04d19cc9481d3cd2750b45b970dc61271b/uart_tx.sv#L182-L209), bộ đếm so sánh `baud_cnt == cfg_div_i` rồi sinh `bit_done`. `cfg_div_i={DLM,DLL}`. **Không có khối chia baud `16×` như tài liệu hướng dẫn.**

- Với `f_CLK=50 MHz`, `baud=115200`, số clock mỗi bit mục tiêu gần `50,000,000 / 115,200 ≈ 434.03`.
- Vì bộ đếm **và** FSM có chu kỳ cập nhật riêng, cần **đo cạnh `tx_o` bằng testbench** để khóa chính xác `DLL/DLM`; giá trị khởi đầu cho khảo sát ở khoảng **432–433**, **không dùng 27**.
- [OPEN] Chưa khẳng định giá trị divisor chính thức trước khi chạy mô phỏng TX/RX và kiểm thử sai số baud.

| ID | Yêu cầu |
|---|---|
| `REQ_TX_001` | Ghi THR tại offset `0x0`, `DLAB=0`, tạo dữ liệu đầu vào TX FIFO. |
| `REQ_TX_002` | TX ở IDLE giữ mức `1`; mỗi frame có start/data/optional parity/stop. |
| `REQ_TX_003` | Các bit dữ liệu truyền LSB-first; hỗ trợ 5,6,7,8 bit theo `LCR[1:0]`. |
| `REQ_TX_004` | `LCR[2]` ảnh hưởng số stop bits TX; `LCR[3]` bật parity. |
| `REQ_TX_005` | Đo chính xác bit period theo bộ chia RTL bằng waveform, sau đó đối chiếu baud mục tiêu. |

---

## 7. Đặc tả nhận UART (RX) [RTL]

- `uart_rx` có đồng bộ tín hiệu đầu vào nội bộ bằng `reg_rx_sync` 3 bit; phát hiện cạnh xuống của start bit.
- RX thu 5–8 bit theo `cfg_bits_i` vào byte dữ liệu, phát `rx_valid_o` để đưa vào **RX FIFO 16 phần tử**, phần tử RX FIFO gồm `{parity_error,rx_data}` (9 bit).
- Đọc RBR tại `PADDR=0x0`, `DLAB=0` đưa dữ liệu RX FIFO lên `PRDATA[7:0]` và tạo tín hiệu pop FIFO.
- `LSR[0]` chỉ thị có dữ liệu RX; parity-error đọc từ phần tử FIFO vào `LSR[2]` theo logic RTL.
- [OPEN] Luồng xử lý parity có rủi ro: `SAVE_DATA` (đưa byte vào FIFO) diễn ra **trước** trạng thái `PARITY`, trong khi `err_clr_i` bị nối mức 1; chưa được chứng minh tính đúng đắn của bit lỗi đi kèm byte.
- **Không được khẳng định RX phát hiện framing error/overrun** khi RTL chưa triển khai các cờ liên quan.

| ID | Yêu cầu |
|---|---|
| `REQ_RX_001` | RX nhận khung UART hợp lệ và đưa byte thu vào RX FIFO. |
| `REQ_RX_002` | Đọc RBR trả về byte nhận và pop FIFO. |
| `REQ_RX_003` | `LSR[0]` phản ánh trạng thái FIFO có/không có byte. |
| `REQ_RX_004` | Kiểm tra riêng tính đúng đắn của parity-error; đánh dấu test failing nếu RTL sai. |
| `REQ_RX_005` | Thử nghiệm framing/overrun như các bài kiểm tra giới hạn, **không kỳ vọng thành công nếu thiếu logic**. |

---

## 8. FIFO và interrupt [RTL]

### 8.1. FIFO

- TX FIFO 16×8; RX FIFO 16×9.
- Clear RX qua `FCR[1]`, clear TX qua `FCR[2]`; `FCR[7:6]` chọn mức trigger 1/4/8/14.
- `io_generic_fifo` xác định `full` khi `elements==BUFFER_DEPTH`; ghi khi `valid_i && !full`. Nếu đầy, dữ liệu mới không được thêm. APB phía trên **không có backpressure qua `PREADY` hay `PSLVERR`**, nên kiểm thử burst/writes liên tiếp phải lưu ý mất dữ liệu.
- `FCR[0]` không tạo trạng thái enable/disable FIFO trong RTL.

### 8.2. Interrupt

- `uart_interrupt` xét yêu cầu lỗi (`IER[2]`), nhận dữ liệu (`IER[0]`), TX-empty (`IER[1]`), cập nhật mã `IIR_o` và `event_o=~IIR_o[0]`.
- Mức trigger dựa trên số phần tử RX FIFO bằng phép so sánh `==` các mốc 1/4/8/14 (không phải `>=`), cần test ở biên.
- **Điểm bất thường trong RTL:** cổng `RDA_i` của `uart_interrupt` được nối tới `regs_n[LSR][5]` (TX FIFO empty), chứ không phải `LSR[0]` (RX data ready). Kết quả interrupt RX **phải xác minh bằng mô phỏng**, không lấy mô tả hướng dẫn làm oracle.
- `CTI_i` nối cố định `0` (không có timeout interrupt thực tế).

| ID | Yêu cầu |
|---|---|
| `REQ_FIFO_001` | Mỗi FIFO có độ sâu 16 phần tử và có thể reset/clear. |
| `REQ_FIFO_002` | Kiểm chứng thứ tự FIFO (FIFO order) và hành vi khi đầy. |
| `REQ_FIFO_003` | Kiểm chứng mức trigger RX: 1/4/8/14 phần tử. |
| `REQ_INT_001` | Đối chiếu các bit IER với `event_o`/IIR qua từng loại kích thích. |
| `REQ_INT_002` | Ưu tiên kiểm thử rủi ro nối sai `RDA_i` trước khi dùng interrupt trong FPGA wrapper. |

---

## 9. System Specification cho FPGA DE2-115 [GUIDE / PLAN]

**Phần này là yêu cầu thiết kế mới cho Top-Level**, không phải hành vi chứng minh từ repo DUT.

### 9.1. Hệ thống cần thực hiện

| ID | Yêu cầu hệ thống |
|---|---|
| `REQ_SYS_001` | Cấp `CLOCK_50` cho DUT và logic wrapper; reset bằng `KEY[0]` tích cực thấp. |
| `REQ_SYS_002` | Tạo `button_debouncer` cho `KEY[1]`, đồng bộ phím và tạo xung `send_pulse` một chu kỳ; thời gian ổn định dự kiến 10 ms = 500.000 clock @50MHz. |
| `REQ_SYS_003` | Tạo APB Master FSM phát đúng SETUP/ACCESS, tự động init 6 giao dịch APB ghi: LCR(DLAB=1), DLL, DLM, LCR(DLAB=0), FCR, IER. |
| `REQ_SYS_004` | Sau init, FSM hoạt động `IDLE → POLL_LSR → [READ_RBR] / [WRITE_THR] → IDLE`, thăm dò định kỳ khoảng 100 µs hoặc theo yêu cầu phím/ngắt. |
| `REQ_SYS_005` | `SW[7:0]` chọn dữ liệu TX; bấm `KEY[1]` gửi một ký tự khi được phép. |
| `REQ_SYS_006` | `SW[16]` cho phép dừng việc đọc RBR để khảo sát RX FIFO đầy; không mặc định có cờ overrun từ DUT. |
| `REQ_SYS_007` | `SW[17]` bật Echo Mode: đọc byte từ RBR rồi ghi lại THR. |
| `REQ_SYS_008` | Chân RX từ CP2102 đi qua đường đồng bộ phù hợp clock FPGA trước khi vào DUT; lưu ý DUT đã có bộ đồng bộ RX nội bộ. |
| `REQ_SYS_009` | `HEX1:HEX0` hiển thị byte từ SW; `HEX5:HEX4` hiển thị byte RX; `LEDR[4:0]` báo LSR[4:0], `LEDG[8]` báo `event_o`, `LEDG[0]` báo init thành công. |
| `REQ_SYS_010` | Dùng đúng địa chỉ thanh ghi RTL (`0x3`,`0x0`,`0x1`,`0x2`,`0x5`), không dùng địa chỉ word-aligned trong hướng dẫn. |
| `REQ_SYS_011` | Baud và cấu hình parity phải tương thích hành vi thực tế RTL; `SW[15]` chọn odd/even **chưa hỗ trợ** như mô tả trong hướng dẫn. |

### 9.2. APB Master FSM dự kiến

Theo `Huongdan_UART.md` chương 4, 11 state ở mức chức năng: `ST_RESET`, `ST_INIT_LCR_DLAB1`, `ST_INIT_DLL`, `ST_INIT_DLM`, `ST_INIT_LCR_DLAB0`, `ST_INIT_FCR`, `ST_INIT_IER`, `ST_IDLE`, `ST_POLL_LSR`, `ST_READ_RBR`, `ST_WRITE_THR`. Mỗi giao dịch có pha SETUP và ACCESS riêng; việc đếm **11 trạng thái chức năng không có nghĩa mỗi giao dịch mất đúng một clock**.

**Bảng init sau khi sửa địa chỉ** (giá trị cấu hình là mục tiêu, còn divisor sẽ chốt sau mô phỏng):

| Thứ tự | Thanh ghi | PADDR đúng | Dữ liệu/công dụng |
|---|---|---|---|
| 1 | LCR | `0x3` | `0x83`: DLAB=1, 8 data bits |
| 2 | DLL | `0x0` | Byte thấp của divisor **cần đo lại**, không mặc định `0x1B` |
| 3 | DLM | `0x1` | Byte cao divisor (thường 0 tại 115200 nếu divisor ~433) |
| 4 | LCR | `0x3` | `0x03`: 8N1 hoặc `0x0B`: 8 bits + parity enable; odd/even select không có hiệu lực RTL |
| 5 | FCR | `0x2` | `0x07`: tác dụng thực tế là clear RX/TX, `FCR[0]` không được sử dụng |
| 6 | IER | `0x1` | `0x05`: bật RX-data/error interrupt, **cần test RDA trước** |

### 9.3. DE2-115 và CP2102

[GUIDE] Chọn FPGA `EP4CE115F29C7`. Dây CP2102: `RXD` → FPGA UART TX (`GPIO[0]`, `PIN_AB22`), `TXD` → FPGA UART RX (`GPIO[2]`, `PIN_AB21`), nối **GND chung** (guide đề xuất chân header 12 hoặc 30). **Không nối nguồn 3V3/5V CP2102 vào board FPGA**; xác minh điện áp I/O thực tế của module CP2102 trước khi cắm.

**Gán chân theo hướng dẫn, CHƯA kiểm chứng bằng board manual / Pin Planner:**

| Port | Pin/nhóm pin hướng dẫn |
|---|---|
| `CLOCK_50` | `PIN_Y2` |
| `KEY[0]`, `KEY[1]` | `PIN_M23`, `PIN_M21` |
| `GPIO_UART_TX`, `GPIO_UART_RX` | `PIN_AB22`, `PIN_AB21` |
| `SW[7:0]` | `PIN_AB26, AD26, AC26, AB27, AD27, AC27, AC28, AB28` |
| `SW[14:17]` | `PIN_AA23, PIN_AA22, PIN_Y24, PIN_Y23` |
| `LEDR[4:0]` | `PIN_F18, F21, E19, F19, G19` |
| `LEDG[0]`, `LEDG[8]` | `PIN_E21`, `PIN_F17` |
| `HEX0[6:0]` | `PIN_H22, J22, L25, L26, E17, F22, G18` |
| `HEX1[6:0]` | `PIN_U24, U23, W25, W22, W21, Y22, M24` |
| `HEX4[6:0]` | `PIN_AE18, AF19, AE19, AH21, AG21, AA19, AB19` |
| `HEX5[6:0]` | `PIN_AH18, AF18, AG19, AH19, AB18, AC18, AD18` |

**I/O Standards** trong hướng dẫn: một số nhóm 2.5V (`KEY`, `SW`, `LEDR`, `LEDG`, `HEX0/1`) và một số nhóm 3.3-V LVTTL (`GPIO_UART`, `HEX4/5`). Phải kiểm tra với DE2-115 manual/Quartus trước khi nạp; không coi bảng pin này là xác nhận an toàn điện.

---

## 10. Kế hoạch kiểm chứng ở mức SPEC (định hướng yêu cầu 2)

Đây **chưa phải DV Plan đầy đủ**. Khi làm DV Plan, mọi testcase phải trỏ về `REQ_...` và phân biệt:

1. **RTL-supported:** đo/so với hành vi được RTL định nghĩa, kỳ vọng pass.
2. **Known discrepancy:** kiểm thử một yêu cầu của hướng dẫn không được RTL hiện thực đầy đủ; test có thể fail có chủ đích để chứng minh giới hạn.
3. **Open investigation:** cần waveform, lint hoặc thực nghiệm rồi mới quyết định pass/fail.

Phân nhóm cần bao phủ: APB handshake; reset; register DLAB; truyền TX 5–8 bits; RX; FIFO order/full/clear; parity; interrupt; random register sequences; cross coverage giữa frame mode và đường TX/RX. Trên FPGA, kiểm tra cơ bản: init, PC→FPGA, FPGA→PC, echo, hiển thị HEX/LED, thử FIFO đầy và tín hiệu interrupt.

## 11. Những điểm còn mở và tiêu chí đóng SPEC

| Mã | Nội dung | Cách xác minh |
|---|---|---|
| `OPEN-01` | Khóa divisor thực nghiệm cho 115200 tại 50MHz | Testbench đo chu kỳ bit của TX, loopback RX, đối chiếu sai số |
| `OPEN-02` | Khả năng báo parity error | Directed test với parity cố ý sai, quan sát `LSR[2]`, FIFO 9-bit |
| `OPEN-03` | `event_o` báo RX theo dữ liệu hay báo sai do `RDA_i` | APB/UART interrupt directed test |
| `OPEN-04` | Độ đầy/clear FIFO, mất dữ liệu khi ghi đầy | Directed stress test |
| `OPEN-05` | Board pinout và I/O standard | Đối chiếu manual DE2-115 + Quartus Pin Planner |
| `OPEN-06` | RTL Top-Level `de2_115_apb_uart_bringup.sv` | Viết/review source; chưa được cung cấp trong PULP repo |
| `OPEN-07` | Bộ đồng bộ RX ngoài và trong DUT ảnh hưởng latency | Waveform/STA khi tích hợp FPGA |

**Bản SPEC v0.1 được xem là bản phân tích ban đầu, chưa phải dấu xác nhận hoàn tất.** Trước khi chốt v1.0 cần xem lại register map, tính baud bằng mô phỏng, xem kết quả những lỗi nghi vấn và xác minh pinout. Không sửa DUT để hợp thức hóa SPEC; mọi patch (nếu có) phải dùng commit/branch riêng và đánh dấu khác với DUT gốc.

---

## Phụ lục A — Dẫn chứng chính

- Hướng dẫn gốc: `Huongdan_UART.md`, phần 1–5 (tệp thầy cung cấp).
- [RTL: top + APB + registers](https://github.com/pulp-platform/apb_uart_sv/blob/dfad6e04d19cc9481d3cd2750b45b970dc61271b/apb_uart_sv.sv)
- [RTL: UART TX](https://github.com/pulp-platform/apb_uart_sv/blob/dfad6e04d19cc9481d3cd2750b45b970dc61271b/uart_tx.sv)
- [RTL: UART RX](https://github.com/pulp-platform/apb_uart_sv/blob/dfad6e04d19cc9481d3cd2750b45b970dc61271b/uart_rx.sv)
- [RTL: Interrupt](https://github.com/pulp-platform/apb_uart_sv/blob/dfad6e04d19cc9481d3cd2750b45b970dc61271b/uart_interrupt.sv)
- [RTL: FIFO](https://github.com/pulp-platform/apb_uart_sv/blob/dfad6e04d19cc9481d3cd2750b45b970dc61271b/io_generic_fifo.sv)
- [RTL file list](https://github.com/pulp-platform/apb_uart_sv/blob/dfad6e04d19cc9481d3cd2750b45b970dc61271b/src_files.yml)
- **Bảng sai khác chi tiết:** [`00_RTL_Guide_Discrepancies.md`](00_RTL_Guide_Discrepancies.md).
