# TÀI LIỆU ĐẶC TẢ KỸ THUẬT & HƯỚNG DẪN THỰC HÀNH
**Đề tài:** Tích hợp và Kiểm thử phần cứng khối IP `pulp-platform/apb_uart_sv` trên kít FPGA DE2-115 với mạch CP2102  
**Đối tượng:** Sinh viên thực hành Thiết kế Vi mạch / Hệ thống Nhúng FPGA  

---

## PHẦN 1: DANH SÁCH FILE MÃ NGUỒN & QUY TRÌNH TẠO PROJECT QUARTUS

### 1.1. Code đã đầy đủ chưa? Cần những file nào trong Quartus?
File `de2_115_apb_uart_bringup.sv` đã chứa đầy đủ **toàn bộ phần mạch điều khiển ngoại vi** (Top-level Wrapper, APB Master FSM, Mạch chống rung phím `button_debouncer` và Mạch giải mã LED 7 đoạn `seven_seg_decoder`).

Tuy nhiên, bên trong file này có gọi (instantiate) khối **DUT (`apb_uart_sv`)**. Do đó, để biên dịch (Compile) ra file `.sof` nạp xuống board, project Quartus cần tổng cộng **6 file SystemVerilog (`.sv`)** sau:

| STT | Tên File | Nguồn gốc | Vai trò trong dự án |
| :-- | :--- | :--- | :--- |
| **1** | **`de2_115_apb_uart_bringup.sv`** | **Sinh viên tự viết** (hoặc code mẫu của GV) | **Top-Level Entity:** Chứa APB Master FSM, Debouncer, Giải mã HEX và kết nối chân I/O của DE2-115. |
| **2** | `apb_uart_sv.sv` | Repo `pulp-platform/apb_uart_sv` | Giao diện bus APB Slave và quản lý hệ thống thanh ghi chuẩn 16550. |
| **3** | `uart_tx.sv` | Repo `pulp-platform/apb_uart_sv` | Máy trạng thái (FSM) truyền dữ liệu nối tiếp (`tx_o`). |
| **4** | `uart_rx.sv` | Repo `pulp-platform/apb_uart_sv` | Máy trạng thái (FSM) nhận dữ liệu nối tiếp (`rx_i`) và phát hiện lỗi khung truyền/chẵn lẻ. |
| **5** | `uart_interrupt.sv` | Repo `pulp-platform/apb_uart_sv` | Khối quản lý ưu tiên ngắt và xuất tín hiệu `event_o`. |
| **6** | `io_generic_fifo.sv` | Repo `pulp-platform` (`common_cells` / `apb_uart_sv`) | Bộ đệm FIFO dùng chung cho cả chiều truyền (TX FIFO) và chiều nhận (RX FIFO). |

> **Lưu ý quan trọng khi tạo Project trong Intel Quartus Prime:**
> 1. Chọn đúng mã chip FPGA của kít DE2-115: Family **Cyclone IV E**, Device **`EP4CE115F29C7`**.
> 2. Add đủ 6 file `.sv` ở trên vào project và đặt **`de2_115_apb_uart_bringup`** làm **Top-Level Entity**.
> 3. Vào `Assignments -> Settings -> Compiler Settings -> Verilog HDL Input`, chọn chuẩn **SystemVerilog** để Quartus hiểu được các từ khóa `logic`, `always_ff`, `always_comb`, `typedef enum`.

---

## PHẦN 2: SƠ ĐỒ KHỐI HỆ THỐNG (SYSTEM BLOCK DIAGRAM)

Vì khối `apb_uart_sv` chỉ là một **APB Slave** (hoạt động thụ động, chờ lệnh đọc/ghi từ bus APB), nó không thể tự cấu hình tốc độ Baud hay tự đẩy dữ liệu đi khi nạp một mình xuống FPGA. Do đó, ta cần thiết kế một hệ thống bao quanh (**System Wrapper**) đóng vai trò như một vi xử lý thu nhỏ điều khiển khối UART này.

```text
+---------------------------------------------------------------------------------------------------+
|                                   CHIP FPGA CYCLONE IV (DE2-115)                                  |
|                                                                                                   |
|   CLOCK_50 (50MHz) ---------------------------------------+-------------------+                   |
|   KEY[0] (Reset)   ---------------------------------------|---------------+   |                   |
|                                                           |               |   |                   |
|                      +------------------------+           v               v   v                   |
|   KEY[1] (Send) ---->| 1. KHỐI CHỐNG RUNG &   |     +---------------------------+                 |
|                      |    BẮT CẠNH LÊN        |---->|                           |                 |
|                      |   (button_debouncer)   |     |                           |                 |
|                      +------------------------+     |                           |                 |
|                                                     |  3. KHỐI ĐIỀU KHIỂN       |                 |
|   SW[7:0]  (TX Data) ------------------------------>|     APB MASTER FSM        |                 |
|   SW[15:14](Parity)  ------------------------------>|                           |                 |
|   SW[16]   (Stop Read)----------------------------->|  - Tự động Init 6 thanh   |                 |
|   SW[17]   (Echo Mode)----------------------------->|    ghi khi Reset          |                 |
|                                                     |  - Đọc LSR định kỳ        |                 |
|                      +------------------------+     |  - Đọc RBR khi có dữ liệu |                 |
|                      | 2. ĐỒNG BỘ HÓA 2-FF    |     |  - Ghi THR khi bấm KEY[1] |                 |
|   GPIO_UART_RX ----->|   (2-Stage Sync)       |     +-------------+-------------+                 |
|   (Từ TXD CP2102)    +-----------+------------+                   |     ^                         |
|                                  | (uart_rx_sync2)                |     |                         |
|                                  |            Giao diện Bus APB   |     | Tín hiệu ngắt           |
|                                  |         (PADDR, PWDATA, PSEL,  |     | (event_o)               |
|                                  |          PENABLE, PWRITE, ...) |     |                         |
|                                  v                                v     |                         |
|                              +------------------------------------------+----+                    |
|                              | 4. KHỐI IP MỤC TIÊU: apb_uart_sv (DUT)        |                    |
|                              |  +--------------+  +-----------+  +--------+  |                    |
|                              |  | Thanh ghi    |  | TX / RX   |  | Khối   |  |                    |
|                              |  | Chuẩn 16550  |  | FIFO      |  | Ngắt   |  |                    |
|                              |  +--------------+  +-----------+  +--------+  |                    |
|                              +---+-------------------------------------------+                    |
|                                  | (tx_o)                                                         |
|                                  v                                                                |
|   GPIO_UART_TX <-----------------+                                                                |
|   (Tới RXD CP2102)                                                                                |
|                                                                                                   |
|                      +-------------------------------------------------------+                    |
|                      | 5. KHỐI HIỂN THỊ TRẠNG THÁI & GIẢI MÃ LED 7 ĐOẠN      |                    |
|                      |    (seven_seg_decoder & LED Status Mapping)           |                    |
|                      +---+-------------------+-------------------+-----------+                    |
+--------------------------|-------------------|-------------------|--------------------------------+
                           |                   |                   |
                           v                   v                   v
                    HEX1..0 (TX Hex)    HEX5..4 (RX Hex)    LEDR[4:0] (Cờ lỗi LSR)
                                                            LEDG[8]   (Cờ ngắt event_o)
                                                            LEDG[0]   (Báo Init thành công)
```

---

## PHẦN 3: CHỨC NĂNG CHI TIẾT CỦA TỪNG KHỐI (MODULE SPECIFICATION)

### Khối 1: Bộ chống rung phím và Bắt cạnh lên (`button_debouncer`)
* **Vấn đề vật lý:** Nút nhấn cơ học `KEY[1]` trên kít DE2-115 khi nhấn xuống sẽ bị nảy tiếp điểm kim loại (bouncing) tạo ra hàng chục xung lên/xuống trong khoảng $5\text{ ms} - 10\text{ ms}$. Với xung nhịp $50\text{ MHz}$ (chu kỳ $20\text{ ns}$), nếu nối thẳng `KEY[1]` vào FSM, một lần bấm tay của sinh viên sẽ làm FSM hiểu nhầm là bấm hàng trăm lần và ghi tràn bộ đệm truyền `THR`.
* **Giải pháp thiết kế:**
  1. Đưa tín hiệu `~KEY[1]` qua 2 Flip-Flop để đồng bộ với xung nhịp `CLOCK_50`.
  2. Dùng bộ đếm kiểm tra: Tín hiệu nút nhấn phải giữ mức ổn định liên tục trong đúng **$10\text{ ms}$** ($500,000$ chu kỳ clock $50\text{ MHz}$) thì mới công nhận là nút đã được nhấn (`btn_stable_q = 1`).
  3. Dùng mạch **Bắt cạnh lên (Rising-Edge Detector)**: `pulse_out = btn_stable_q & ~btn_stable_prev`. Nhờ vậy, dù người dùng giữ tay trên nút `KEY[1]` bao lâu, đầu ra `send_pulse` cũng chỉ bật lên `1` trong **đúng 1 chu kỳ xung nhịp duy nhất** để kích hoạt gửi đúng 1 ký tự.

---

### Khối 2: Bộ đồng bộ hóa tín hiệu nhận (`2-FF Synchronizer`)
* **Vấn đề vật lý:** Tín hiệu nối tiếp từ chân `TXD` của mạch CP2102 đi vào chân `GPIO_UART_RX` của FPGA được tạo ra bởi bộ dao động nội trên chip CP2102, hoàn toàn **lệch pha và bất đồng bộ** với xung nhịp `CLOCK_50` trên DE2-115. Nếu đưa thẳng vào FSM của `uart_rx.sv`, hiện tượng **Metastability (siêu ổn định)** sẽ xảy ra khi tín hiệu thay đổi sát cạnh lên của clock.
* **Giải pháp thiết kế:** Cho tín hiệu đi qua 2 tầng D-Flip-Flop nối tiếp (`uart_rx_sync1` $\rightarrow$ `uart_rx_sync2`) được khởi tạo ở mức cao (`1'b1` - mức Idle của đường truyền UART).

---

### Khối 3: Máy trạng thái điều khiển APB Master (`APB Master FSM`)
Đây là **trọng tâm bài giảng** mà sinh viên cần nắm vững để tự viết code. Khối này đóng vai trò như một CPU thực hiện các giao dịch đọc/ghi trên bus AMBA APB theo quy tắc **2 chu kỳ mỗi giao dịch**:
* **Chu kỳ 1 — Pha SETUP (`apb_phase_q = 0`):** Bật `PSEL = 1`, `PENABLE = 0`, đưa địa chỉ lên `PADDR`, chiều truy cập lên `PWRITE` (và dữ liệu lên `PWDATA` nếu là lệnh Ghi).
* **Chu kỳ 2 — Pha ACCESS (`apb_phase_q = 1`):** Giữ nguyên các tín hiệu trên và bật **`PENABLE = 1`**. Khi Slave phản hồi `PREADY = 1` ở cạnh lên của clock, giao dịch hoàn tất (nếu là lệnh Đọc thì chốt dữ liệu từ `PRDATA`).

---

### Khối 4: Khối IP ngoại vi `apb_uart_sv` (DUT)
Là khối thiết kế chuẩn 16550 của nhóm PULP (ETH Zurich). Sinh viên cần hiểu **Bản đồ thanh ghi (Register Map)** và **Công thức tính tốc độ Baud** của khối này để lập trình cho APB Master:

#### A. Bảng thanh ghi của `apb_uart_sv` (Word-aligned 32-bit)
| Địa chỉ (`PADDR`) | Tên Thanh ghi | Chiều | Điều kiện `LCR[7]` (`DLAB`) | Chức năng chính |
| :--- | :--- | :---: | :---: | :--- |
| **`12'h000`** | **`RBR`** (Receive Buffer) | Read | `DLAB = 0` | Đọc 1 byte dữ liệu vừa nhận được từ đầu hàng đợi RX FIFO. |
| **`12'h000`** | **`THR`** (Transmit Holding) | Write | `DLAB = 0` | Ghi 1 byte dữ liệu cần truyền vào cuối hàng đợi TX FIFO. |
| **`12'h000`** | **`DLL`** (Divisor Latch LSB) | R/W | **`DLAB = 1`** | 8-bit thấp của hệ số chia tần số Baud. |
| **`12'h004`** | **`DLM`** (Divisor Latch MSB) | R/W | **`DLAB = 1`** | 8-bit cao của hệ số chia tần số Baud. |
| **`12'h004`** | **`IER`** (Interrupt Enable) | R/W | `DLAB = 0` | Bật/tắt các nguồn ngắt (`Bit 0`: Có dữ liệu RX; `Bit 2`: Lỗi đường truyền). |
| **`12'h008`** | **`FCR`** (FIFO Control) | Write | Bất kỳ | Cấu hình và xóa (clear) bộ đệm TX/RX FIFO (ghi `0x07` để bật & xóa FIFO). |
| **`12'h00C`** | **`LCR`** (Line Control) | R/W | Bất kỳ | Cấu hình khung truyền: `Bit 7` là **`DLAB`**; `Bit [5:3]` cấu hình Parity; `Bit 2` số Stop bit; `Bit [1:0]` số bit dữ liệu (`2'b11` = 8-bit). |
| **`12'h014`** | **`LSR`** (Line Status) | Read | Bất kỳ | Thanh ghi trạng thái: `Bit 0` (**DR** - Có dữ liệu nhận), `Bit 1` (**OE** - Tràn FIFO), `Bit 2` (**PE** - Lỗi Parity), `Bit 3` (**FE** - Lỗi Stop bit), `Bit 5` (**THRE** - TX FIFO còn trống). |

#### B. Công thức tính hệ số chia Baudrate trên DE2-115
Khối `apb_uart_sv` sử dụng kỹ thuật lấy mẫu quá mức **16 lần (16x Oversampling)**. Với tần số xung nhịp hệ thống `CLOCK_50` = $50,000,000\text{ Hz}$ và tốc độ truyền mong muốn là **$115,200\text{ bps}$**:
$$\text{Divisor} = \text{round}\left( \frac{f_{\text{CLOCK\_50}}}{16 \times \text{Baudrate}} \right) = \text{round}\left( \frac{50,000,000}{16 \times 115,200} \right) = \text{round}(27.1267) = 27 \text{ (Hex: } \text{0x001B}\text{)}$$
Do đó, ta nạp `DLL = 8'd27` (`8'h1B`) và `DLM = 8'd0` (`8'h00`).

---

### Khối 5: Khối Giải mã hiển thị (`seven_seg_decoder` & LEDs)
* Chuyển đổi mã nhị phân 4-bit (Nibble) sang mã điều khiển 7 thanh LED trên DE2-115 (lưu ý: LED 7 đoạn trên DE2-115 là loại **Anode chung - Active Low**, nghĩa là xuất mức `0` thì thanh LED sáng, xuất mức `1` thì tắt).
* `HEX1` & `HEX0`: Hiển thị mã Hex của ký tự đang gạt trên `SW[7:0]` chuẩn bị gửi lên PC.
* `HEX5` & `HEX4`: Hiển thị mã Hex của ký tự vừa nhận được từ PC qua thanh ghi `RBR`.

---

## PHẦN 4: THIẾT KẾ MÁY TRẠNG THÁI (APB MASTER FSM)

Để sinh viên dễ hiểu và tự code được, máy trạng thái gồm **11 trạng thái**, chia làm **2 pha hoạt động rõ rệt**:

### 4.1. Sơ đồ chuyển trạng thái (State Transition Diagram)

```text
                       [Nhấn KEY[0] Reset]
                                |
                                v
                         +--------------+
                         |   ST_RESET   |
                         +------+-------+
                                |
    === PHA 1: CHUỖI KHỞI TẠO TỰ ĐỘNG (6 GIAO DỊCH APB WRITE) ===
                                |
                                v
                 +------------------------------+
                 |      ST_INIT_LCR_DLAB1       |  Ghi LCR (0x0C) = 0x83 (Mở khóa DLAB=1, 8-bit)
                 +--------------+---------------+
                                | (Xong 2 chu kỳ APB)
                                v
                 +------------------------------+
                 |         ST_INIT_DLL          |  Ghi DLL (0x00) = 27 (Chia Baud 115200)
                 +--------------+---------------+
                                |
                                v
                 +------------------------------+
                 |         ST_INIT_DLM          |  Ghi DLM (0x04) = 0
                 +--------------+---------------+
                                |
                                v
                 +------------------------------+
                 |      ST_INIT_LCR_DLAB0       |  Ghi LCR (0x0C) tắt DLAB=0 & gán cấu hình Parity
                 +--------------+---------------+
                                |
                                v
                 +------------------------------+
                 |         ST_INIT_FCR          |  Ghi FCR (0x08) = 0x07 (Bật & xóa sạch FIFO)
                 +--------------+---------------+
                                |
                                v
                 +------------------------------+
                 |         ST_INIT_IER          |  Ghi IER (0x04) = 0x05 (Bật ngắt RX & LSR)
                 +--------------+---------------+  --> Bật đèn LEDG[0] = 1 (Init Done!)
                                |
    === PHA 2: VÒNG LẶP HOẠT ĐỘNG CHÍNH (POLLING, NHẬN RX & TRUYỀN TX) ===
                                |
                                v
                 +------------------------------+
          +----->|           ST_IDLE            |<----------------------+
          |      +--------------+---------------+                       |
          |                     | Khi có:                               |
          |                     | - Người dùng bấm KEY[1] (tx_pending)  |
          |                     | - Hoặc có ngắt từ UART (event_o = 1)  |
          |                     | - Hoặc định kỳ mỗi ~100us             |
          |                     v                                       |
          |      +------------------------------+                       |
          |      |         ST_POLL_LSR          |  Đọc thanh ghi LSR (0x14)
          |      |   (Cập nhật đèn LEDR[4:0])   |  Lưu PRDATA[7:0] vào lsr_status_reg
          |      +---+----------------------+---+                       |
          |          |                      |                           |
          |   Nếu LSR[0]==1 (Có byte nhận)  | Nếu không có dữ liệu RX,  |
          |   và SW[16]==0 (Cho phép đọc)   | nhưng có tx_pending==1    |
          |          |                      | và LSR[5]==1 (TX trống)   |
          |          v                      |                           |
          |  +---------------+              |                           |
          |  |  ST_READ_RBR  |              |                           |
          |  | Đọc RBR (0x00)|              |                           |
          |  | Xuất ra HEX5-4|              |                           |
          |  +-------+-------+              |                           |
          |          |                      |                           |
          |   Nếu không cần TX              v                           |
          +----------+------------> +---------------+                   |
                     (Nếu cần TX    | ST_WRITE_THR  |                   |
                      hoặc Echo)    | Ghi THR (0x00)|-------------------+
                                    +---------------+ (Xóa cờ tx_pending)
```

---

## PHẦN 5: BẢNG GÁN CHÂN (PIN ASSIGNMENT) & SƠ ĐỒ ĐẤU DÂY CP2102

### 5.1. Hướng dẫn cắm 3 sợi dây Jumper giữa mạch CP2102 và DE2-115
Hàng rào cắm **GPIO 40-pin (JP5)** nằm ở rìa bên phải của board DE2-115 (Chân số 1 nằm ở góc trên bên trái của JP5):

| Chân trên mạch CP2102 | Nối tới chân trên Header GPIO (JP5) của DE2-115 | Mã chân FPGA (Quartus Pin) | Giải thích luồng tín hiệu |
| :--- | :--- | :---: | :--- |
| **`GND`** | **Chân số 12** (hoặc **Chân số 30**) | `GND` | Nối đất chung giữa PC và FPGA (Bắt buộc). |
| **`RXD`** (Chân nhận của CP2102) | **Chân số 1 (`GPIO[0]`)** | **`PIN_AB22`** | Nhận dữ liệu truyền ra từ chân `GPIO_UART_TX` của FPGA. |
| **`TXD`** (Chân truyền của CP2102)| **Chân số 3 (`GPIO[2]`)** | **`PIN_AB21`** | Đẩy dữ liệu từ máy tính vào chân `GPIO_UART_RX` của FPGA. |

> **CẢNH BÁO AN TOÀN:** Tuyệt đối **KHÔNG** nối chân nguồn `3V3` hoặc `5V` của CP2102 vào board DE2-115.

---

### 5.2. Bảng gán chân đầy đủ trong Quartus Pin Planner
Sinh viên mở `Assignments -> Pin Planner` trong Quartus và gán chính xác các chân sau (hoặc import qua file `.qsf`):

| Tên Port trong Verilog | Mã Pin FPGA (`EP4CE115F29C7`) | Chuẩn điện áp (I/O Standard) | Ngoại vi tương ứng trên DE2-115 |
| :--- | :---: | :---: | :--- |
| **`CLOCK_50`** | `PIN_Y2` | 3.3-V LVTTL | Nguồn xung nhịp $50\text{ MHz}$ |
| **`KEY[0]`** | `PIN_M23` | 2.5 V | Nút nhấn Reset hệ thống (Nhấn = `0`) |
| **`KEY[1]`** | `PIN_M21` | 2.5 V | Nút nhấn gửi 1 byte dữ liệu lên PC |
| **`GPIO_UART_TX`** | `PIN_AB22` | 3.3-V LVTTL | Chân `GPIO[0]` (Nối vào `RXD` của CP2102) |
| **`GPIO_UART_RX`** | `PIN_AB21` | 3.3-V LVTTL | Chân `GPIO[2]` (Nối vào `TXD` của CP2102) |
| **`SW[7:0]`** | `PIN_AB26, AD26, AC26, AB27, AD27, AC27, AC28, AB28` | 2.5 V | 8 công tắc chọn mã ASCII cần gửi (`SW[7]` đến `SW[0]`) |
| **`SW[14]`** | `PIN_AA23` | 2.5 V | Bật/Tắt kiểm tra Parity (`0`: No Parity, `1`: Enable Parity) |
| **`SW[15]`** | `PIN_AA22` | 2.5 V | Chọn loại Parity (`0`: Odd Parity, `1`: Even Parity) |
| **`SW[16]`** | `PIN_Y24` | 2.5 V | Cố tình ngưng đọc `RBR` để gây lỗi tràn FIFO (`Overrun`) |
| **`SW[17]`** | `PIN_Y23` | 2.5 V | Chế độ `Echo Mode` (Nhận ký tự nào từ PC gửi trả lại ký tự đó) |
| **`LEDR[4:0]`** | `PIN_F18, F21, E19, F19, G19` | 2.5 V | 5 đèn LED Đỏ báo trực tiếp 5 bit thấp của thanh ghi `LSR[4:0]` |
| **`LEDG[0]`** | `PIN_E21` | 2.5 V | Đèn LED Xanh báo đã khởi tạo xong 6 thanh ghi UART |
| **`LEDG[8]`** | `PIN_F17` | 2.5 V | Đèn LED Xanh báo tín hiệu ngắt `event_o` từ khối UART |
| **`HEX0[6:0]`** | `PIN_H22, J22, L25, L26, E17, F22, G18` | 2.5 V | Hiển thị Nibble thấp của byte gửi (`SW[3:0]`) |
| **`HEX1[6:0]`** | `PIN_U24, U23, W25, W22, W21, Y22, M24` | 2.5 V | Hiển thị Nibble cao của byte gửi (`SW[7:4]`) |
| **`HEX4[6:0]`** | `PIN_AE18, AF19, AE19, AH21, AG21, AA19, AB19` | 3.3-V LVTTL | Hiển thị Nibble thấp của byte nhận (`RBR[3:0]`) |
| **`HEX5[6:0]`** | `PIN_AH18, AF18, AG19, AH19, AB18, AC18, AD18` | 3.3-V LVTTL | Hiển thị Nibble cao của byte nhận (`RBR[7:4]`) |

---

