# ĐẶC TẢ KỸ THUẬT HỆ THỐNG APB–UART TRÊN FPGA DE2-115

**Dự án:** APB_UART_2026.1 — Kiểm thử UART sử dụng giao tiếp APB.
**Phiên bản tài liệu:** 1.0 — đặc tả thiết kế mục tiêu cho IP sửa từ PULP.
**Ngày:** 12/11/2026.
**Phạm vi bàn giao:** Yêu cầu 1 — Specifications; làm đầu vào cho DV Plan/UVM và FPGA.
**Trạng thái tại lần phát hành SPEC:** chưa triển khai RTL/regression/Quartus/board; tiến độ thực thi sau đó xem [DV results](dv/RESULTS.md).
**Quyết định của chủ dự án:** sửa RTL để đáp ứng các chức năng trong hướng dẫn; không dừng ở việc ghi nhận giới hạn của IP nguyên bản.

## 1. Mục đích, nguồn chuẩn và cách sử dụng

Tài liệu này xác định một hệ thống có thể triển khai và kiểm thử độc lập: DUT UART có giao diện APB, môi trường kiểm chứng DUT, và wrapper FPGA DE2-115 giao tiếp PC qua CP2102. Các yêu cầu ghi “phải” là hợp đồng của **bản mục tiêu v1.0**, không phải mô tả rằng PULP nguyên bản đã thực hiện được chúng.

### 1.1. Tài liệu nguồn và revision

| Mã | Nguồn | Vai trò |
|---|---|---|
| S01 | Đề bài “Bài tập lớn cuối kỳ” trong ảnh Teams người dùng cung cấp | Ba yêu cầu: SPEC; DV Plan/UVM/directed/automatic/random/coverage; kiểm thử DE2-115 |
| S02 | `Huongdan_UART.md`, nội dung đính kèm và `reference/Huongdan_UART.md` tại repo S04 | Mục tiêu hệ thống, APB word-aligned, baud 16×, KEY/SW/HEX/LED và CP2102 |
| S03 | [pulp-platform/apb_uart_sv](https://github.com/pulp-platform/apb_uart_sv/tree/dfad6e04d19cc9481d3cd2750b45b970dc61271b), commit `dfad6e04d19cc9481d3cd2750b45b970dc61271b` | Baseline RTL giữ nguyên để đối chứng; không tự động là oracle của bản sửa |
| S04 | [hoafff/APB_UART_2026.1](https://github.com/hoafff/APB_UART_2026.1/tree/e0b17bfadaebefa578e2141ee57c32ed9a5d6f56), commit `e0b17bfadaebefa578e2141ee57c32ed9a5d6f56` | SPEC v0.3, DV Plan v0.1, UVM ban đầu và bản sao RTL upstream |
| S05 | `DE2_115_pin_assignments.csv` trong Downloads; SHA-256 `b3bedb3419d6ed39db5bc913e0910ec6dc4cb990e93b347cdfe765308ca0ba17` | Nguồn map chân/I/O standard; bảng đầy đủ cần dùng được chép tại mục 13 |
| S06 | [Manual DE2-115 của Terasic](https://www.terasic.com.tw/attachment/archive/502/DE2_115_User_manual.pdf) | Đối chiếu board/GPIO/JP6; vị trí jumper thực tế còn phải kiểm tra khi làm FPGA |
| S07 | [TI TL16C550C datasheet](https://www.ti.com/lit/ds/symlink/tl16c550c.pdf), bảng nhận dạng ngắt | Tham chiếu mã IIR và thứ tự ưu tiên; dự án không tuyên bố tương thích toàn bộ 16550 |
| S08 | `APB_UART_2026.1_REVIEW.md` và `APB_UART_review_evidence.zip`, kiểm tra ngày 12/11/2026 | Bằng chứng về baseline, pin và bản sao UVM chỉ sửa cú pháp; tóm tắt tại mục 15 |
| S09 | [Arm AMBA APB Protocol Specification, IHI 0024E](https://documentation-service.arm.com/static/63fe2c1356ea36189d4e79f3) | Tham chiếu pha SETUP/ACCESS và sampling khi PSEL/PENABLE/PREADY; profile của dự án không có PSTRB/PPROT |

Thứ tự áp dụng: **phạm vi đề bài + quyết định sửa IP → hợp đồng mục tiêu trong SPEC này → RTL triển khai → kết quả kiểm thử**. Khi RTL mục tiêu khác SPEC, phải báo lỗi hoặc thay đổi SPEC có version; không sửa expected của test chỉ để chạy xanh. Hành vi lỗi của baseline được giữ trong lịch sử, không trở thành yêu cầu đúng của bản sửa.

### 1.2. Phân biệt ba đối tượng

| Đối tượng | Ý nghĩa và trạng thái |
|---|---|
| `BASE-PULP` | Năm file RTL S03 nguyên bản; đã rà soát và chạy các phép kiểm ghi ở mục 15 |
| `TARGET-v1.0` | Phiên bản sửa đáp ứng SPEC này; **chưa có kết quả thực thi** tại ngày lập SPEC |
| `SYSTEM-DE2` | Wrapper + TARGET-v1.0 + constraints + board/CP2102; **chưa triển khai/kiểm chứng** |

Không compile đồng thời baseline và bản sửa nếu cùng tên module `apb_uart_sv`. `apb_uart.sv` và `apb_uart_sv.sv` trong upstream được kiểm tra là trùng nội dung; chỉ chọn file `apb_uart_sv.sv` trong compilation list.

### 1.3. Các lựa chọn đã chốt trong bản SPEC

Người dùng chốt **sửa RTL**. Các chi tiết còn lại dưới đây là lựa chọn kỹ thuật của SPEC để người triển khai có một hợp đồng xác định; chưa phải sự xác nhận của giảng viên về rubric chấm điểm.

| Mục | Quy định TARGET-v1.0 |
|---|---|
| Địa chỉ APB | Word-aligned: `0x000/004/008/00C/014`; không alias qua bit địa chỉ cao |
| Baud | Clock-enable 16×; `B = fCLK/(16×D)`; board dùng `D=27`, DLL=`0x1B`, DLM=`0x00` |
| Chức năng bắt buộc | TX/RX full-duplex; 5–8 data bits; none/odd/even parity; 1/2 stop; FIFO; PE/FE/OE/BI; ngắt đúng; gửi tay/nhận/echo/hold-RX |
| Lỗi APB | PREADY luôn 1; PSLVERR báo địa chỉ/quyền truy cập sai và THR không nhận được byte |
| FIFO | 16 entry khi enable; chế độ 1 entry khi disable; không có hidden pending RX thứ 17 |
| Board mặc định | 50 MHz, 115200 danh định, 8N1, không flow control; parity chọn trước reset |
| Giới hạn chuẩn | Subset phục vụ bài tập; không modem, RTS/CTS, DMA, RX-timeout IRQ, stick parity, phát break hoặc stop 1,5 bit |
| Hiển thị lỗi | LEDR[4:1] giữ các lỗi đã đọc từ LSR đến reset để quan sát được; LEDR[0] là DR của lần đọc LSR gần nhất |

**Lưu ý chuyển phiên bản:** divisor 433, địa chỉ LCR=`0x003` và IIR không-ngắt=`0xC1` ngay sau reset là các dữ kiện của BASE-PULP. Không dùng bộ giá trị đó để cấu hình TARGET-v1.0. Bộ giá trị 27/word-aligned ở trên chỉ đúng **sau khi RTL mục tiêu được triển khai**.

## 2. Phạm vi chức năng và ranh giới nghiệm thu

### 2.1. DUT, wrapper và môi trường kiểm chứng

```text
PC / terminal 115200, 8N1 hoặc 8O1/8E1
              │ USB
            CP2102
       RXD ◄──┼──────── GPIO_UART_TX ◄─────────────┐
       TXD ───┼──────── GPIO_UART_RX → 2FF → DUT RX│
       GND ───┴──────── GND chung                 │
                                                 │
  DE2-115: CLOCK_50 → reset/CDC → APB master → apb_uart_sv
           KEY1 → debounce ───────┘              ├─ UART TX/RX
           SW → đồng bộ/chốt ────┘               ├─ TX/RX FIFO
           KEY0 → reset                           ├─ registers
           HEX/LEDR/LEDG ← master/status/event_o ─┘
```

- DUT gồm APB slave/register bank, TX, RX, hai FIFO và interrupt controller. DUT không chứa nút bấm/HEX hay CP2102.
- Wrapper làm master APB duy nhất, khởi tạo DUT, gửi một byte từ SW khi nhấn KEY1, nhận và hiển thị byte, echo, dừng đọc RX để kiểm tra overflow.
- UVM chạy trong simulator, không tổng hợp lên FPGA. Scoreboard phải mô hình hóa hợp đồng mục tiêu; không lấy state nội bộ của DUT làm expected chính.
- SPEC xác định yêu cầu và cách nghiệm thu. DV Plan/test implementation là Yêu cầu 2; bitstream và thử board là Yêu cầu 3.

### 2.2. Ngoài phạm vi

Không triển khai CPU/SoC, DMA, modem registers, RTS/CTS hoặc software flow control; không cấp nguồn board từ CP2102; không cam kết tương thích mọi phần mềm 16550. Không bắt buộc dùng PLL hoặc tạo clock chậm riêng. Không yêu cầu sửa upstream/public repository trong phạm vi viết SPEC.

## 3. Tham số và cấu trúc triển khai

| Tham số | Giá trị/profile bắt buộc | Quy tắc |
|---|---:|---|
| `APB_ADDR_WIDTH` | 12 | Địa chỉ byte trong aperture 4 KiB; decode đầy đủ |
| APB data width | 32 | Dữ liệu register hữu hiệu ở `[7:0]`; không có PSTRB |
| `TX_FIFO_DEPTH` | 16 | Profile nghiệm thu cố định; thay depth cần SPEC revision |
| `RX_FIFO_DEPTH` | 16 | 16 byte + metadata lỗi/ack; không tính RX shift register là queue chờ |
| TX entry | 8 bit | Chỉ N bit thấp truyền theo cấu hình frame |
| RX entry | 8 data + PE/FE/BI | Thêm trạng thái error-ack theo entry hoặc cấu trúc tương đương |
| Divisor register | 16 bit | D=`{DLM,DLL}`; 1..65535 hoạt động, 0 có hành vi vô hiệu hóa tại mục 7 |
| Oversampling | 16 ticks/bit | Mỗi tick cách D clock; clock-enable trong cùng miền CLK |
| `CLOCK_HZ` | 50.000.000 Hz | Chu kỳ danh định 20 ns |
| `DEBOUNCE_CYCLES` | 500.000 | 10 ms ổn định cho cả nhấn và nhả |
| `POLL_CYCLES` | 5.000 | 100 µs khi không có yêu cầu xử lý sớm |
| Pending tại wrapper | 1 manual + 1 echo | Hai slot độc lập, không ghi đè byte chưa gửi |

Các module gốc được giữ làm cấu trúc tham khảo: `apb_uart_sv`, `uart_tx`, `uart_rx`, `uart_interrupt`, `io_generic_fifo`. Sửa interface nội bộ khi cần parity-select, metadata lỗi và FIFO handshake. Top DUT giữ tập port ngoài ở mục 4.1. Top board là `de2_115_apb_uart_bringup`; debouncer, reset synchronizer và seven-segment decoder là các khối tổng hợp được. Có thể tách thành nhiều file; số “6 file” trong hướng dẫn không phải giới hạn kiến trúc.

Quy ước thư mục cho bước triển khai sau: giữ `rtl/vendor/pulp_apb_uart_sv/` bất biến; đặt bản sửa trong `rtl/modified/pulp_apb_uart_sv/`, wrapper trong `rtl/fpga/`, và filelist riêng cho từng DUT. Đây là quy ước cần triển khai, không phải các file đã có.

## 4. Giao diện ngoài

### 4.1. Port DUT `apb_uart_sv`

| Port | Chiều | Rộng | Hợp đồng |
|---|---|---:|---|
| `CLK` | in | 1 | Cạnh lên; clock chung cho mọi state tổng hợp |
| `RSTN` | in | 1 | Async assert thấp; hệ thống phải deassert đồng bộ CLK |
| `PADDR` | in | 12 | Byte address ổn định từ SETUP đến completion |
| `PWDATA` | in | 32 | Byte thấp hữu hiệu khi write; bit cao bị bỏ qua |
| `PWRITE` | in | 1 | 1=write, 0=read |
| `PSEL` | in | 1 | Chọn slave |
| `PENABLE` | in | 1 | Pha ACCESS |
| `PRDATA` | out | 32 | Read data tổ hợp; zero-extend byte; 0 ngoài valid read |
| `PREADY` | out | 1 | 1 cố định; không kéo dài giao dịch vì FIFO đầy |
| `PSLVERR` | out | 1 | Chỉ hữu hiệu trong ACCESS; định nghĩa tại mục 5 |
| `rx_i` | in | 1 | UART RX, idle=1; có synchronizer nội bộ |
| `tx_o` | out | 1 | UART TX, idle/reset=1 |
| `event_o` | out | 1 | Mức ngắt active-high; không phải xung một clock |

### 4.2. Port top board

| Port | Chiều | Rộng | Chức năng |
|---|---|---:|---|
| `CLOCK_50` | in | 1 | Clock 50 MHz |
| `KEY[1:0]` | in | 2 | Active-low: KEY0 reset, KEY1 send |
| `SW[17:0]` | in | 18 | Dữ liệu/mode; SW[13:8] dự phòng, không ảnh hưởng DUT |
| `GPIO_UART_RX` | in | 1 | CP2102 TXD → FPGA GPIO[2] |
| `GPIO_UART_TX` | out | 1 | FPGA GPIO[0] → CP2102 RXD |
| `LEDR[4:0]` | out | 5 | DR snapshot và lỗi đã ghi nhận |
| `LEDG[8:0]` | out | 9 | Init/fault/IRQ; các bit chưa dùng phải xuất 0 |
| `HEX0[6:0]`, `HEX1[6:0]` | out | 7 mỗi port | Byte SW, low/high nibble |
| `HEX4[6:0]`, `HEX5[6:0]` | out | 7 mỗi port | Byte RX gần nhất, low/high nibble |

Tổng cộng **65 bit port** phải có pin assignment nếu giữ nguyên khai báo trên. 52 chân trong hướng dẫn là subset dùng chức năng chính; 13 chân thêm là SW[13:8] và LEDG[7:1]. Bảng mục 13 gán đủ cả port dự phòng, tránh để Quartus tự chọn chân ngoài ý muốn.

## 5. Hợp đồng APB

### 5.1. SETUP, ACCESS và thời điểm tác dụng

`transfer = RSTN && PSEL && PENABLE && PREADY`. Mỗi giao dịch hợp lệ phải có một chu kỳ SETUP (`PSEL=1,PENABLE=0`) trước ACCESS (`PSEL=1,PENABLE=1`). Master giữ nguyên PADDR/PWRITE/PWDATA từ SETUP đến cạnh lên completion. Back-to-back được giữ PSEL=1 nhưng phải có PENABLE=0 cho SETUP mới.

| Khoảng clock | PSEL | PENABLE | Tác dụng |
|---|---:|---:|---|
| IDLE | 0 | 0 | Không read/write/clear/pop |
| SETUP | 1 | 0 | Không side effect; đặt địa chỉ/control/data |
| ACCESS | 1 | 1 | PRDATA/PSLVERR hợp lệ; cạnh lên cuối ACCESS hoàn tất |
| Sau completion | 0 hoặc 1 | 0 | IDLE hoặc SETUP giao dịch tiếp |

Write, pop RBR, clear/ack LSR và ack IIR xảy ra **một lần tại cạnh completion**. Master/monitor phải lấy read data trước NBA tại cạnh đó; không đọc lại PRDATA sau khi FIFO đã pop. Giữ ACCESS qua nhiều cạnh khi PREADY=1 là vi phạm của master và có thể lặp side effect; slave không phải tự nhận dạng/xóa giao dịch trùng.

Khi RSTN=0: không transfer/side effect; PRDATA=0, PSLVERR=0, PREADY=1. Bảng reset register ở mục 6 là giá trị quan sát sau release khi truy cập hợp lệ.

### 5.2. Decode và báo lỗi

TARGET-v1.0 chỉ nhận các address chính xác trong bảng register. Yêu cầu word-aligned là **profile của dự án**. Không chỉ decode PADDR[4:2] rồi bỏ qua bit cao; `0x00C`, `0x02C`, `0x80C` không được alias. Các bit PWDATA[31:8] không tác động register, không tạo lỗi.

| Trường hợp ACCESS | PRDATA | PSLVERR | Side effect |
|---|---:|---:|---|
| Read/write register hợp lệ | Theo mục 6 | 0 | Theo register |
| Read RBR khi empty | 0 | 0 | Không pop, không thay pointer/count |
| Write THR có chỗ và D≠0 | 0 | 0 | Enqueue đúng 1 byte |
| Write THR full, không có TX pop cùng cạnh | 0 | 1 | Không enqueue, không đổi dữ liệu cũ, không đặt RX OE |
| Write THR khi D=0 | 0 | 1 | Không enqueue |
| Địa chỉ lệch hàng/unmapped; write LSR | 0 | 1 | Không side effect |
| Read IIR/write FCR tại cùng offset | Theo chiều truy cập | 0 | Không nhầm read với write |
| Không ACCESS | 0 | 0 | Không side effect |

PSLVERR chỉ thông báo lỗi của giao dịch; không phải interrupt UART. DUT không sinh wait-state. Master phải kiểm PSLVERR, không xem PREADY=1 là mặc nhiên thành công.

## 6. Register map, bit fields và side effects

### 6.1. Map chính thức của TARGET-v1.0

| Offset | DLAB | Read | Write | Reset/readback sau reset |
|---:|---|---|---|---|
| `0x000` | 0 | RBR | THR | RBR empty đọc 0 |
| `0x000` | 1 | DLL | DLL | `0x00` |
| `0x004` | 0 | IER | IER | `0x00` |
| `0x004` | 1 | DLM | DLM | `0x00` |
| `0x008` | bất kỳ | IIR | FCR | IIR=`0x01`, FCR internal=`0x00` |
| `0x00C` | bất kỳ | LCR | LCR | `0x00` |
| `0x014` | bất kỳ | LSR | Không hỗ trợ | `0x60` |
| Mọi offset khác | bất kỳ | Không hỗ trợ | Không hỗ trợ | PRDATA=0, PSLVERR=1 |

Các vị trí MCR=`0x010`, MSR=`0x018`, SCR=`0x01C` thuộc hàng “không hỗ trợ”. Không có register readback cho THR/FCR riêng; read cùng offset trả RBR/IIR tùy DLAB/chiều. DLAB không thay đổi cách đọc IIR/LSR/LCR.

### 6.2. DLL/DLM và LCR

DLL/DLM lưu đủ 8 bit mỗi thanh ghi; `D=(DLM<<8)|DLL`. DLAB chỉ chọn bank ở offset 0/4, không tự clear FIFO hoặc stop một frame đang phát/nhận. TX/RX chốt D và LCR[4:0] riêng tại đầu mỗi frame; frame đang chạy không đổi thời gian/format khi CPU ghi register. Queued TX byte chưa vào shift register dùng cấu hình tại lúc bắt đầu frame của byte đó.

Nếu frame bắt đầu đúng cạnh một APB config write hoàn tất, frame đó dùng register value **trước cạnh**; giá trị write mới áp dụng cho lần bắt đầu frame sau. Quy tắc này cũng áp dụng với DLL/DLM và không phụ thuộc thứ tự process trong simulator.

Để thay D an toàn, master phải đợi TX queue/shift rỗng, yêu cầu peer ngừng gửi, sau đó bật DLAB, ghi DLL/DLM và hạ DLAB. Ghi hai byte divisor không có cơ chế commit nguyên tử; nếu vẫn để traffic khởi động giữa hai lần ghi, một frame có thể dùng D trung gian. Wrapper chỉ cấu hình sau reset nên không gặp tình huống này.

| LCR bit | Tên | Hợp đồng |
|---:|---|---|
| [7] | DLAB | 1: DLL/DLM; 0: RBR/THR/IER |
| [6] | Reserved | Read 0, write ignored; không phát break bằng LCR |
| [5] | Reserved | Read 0, write ignored; không stick parity |
| [4] | EPS | Khi PEN=1: 0=odd, 1=even; PEN=0 thì không ảnh hưởng frame |
| [3] | PEN | 0=no parity, 1=có parity |
| [2] | STB | 0=1 stop bit, 1=2 stop bits, áp dụng cả TX/RX |
| [1:0] | WLS | 00/01/10/11 tương ứng 5/6/7/8 data bits |

LCR readback là byte đã mask với `0x9F`; đây là subset được định nghĩa, không hỗ trợ stop 1,5 bit của một số 16550 ở chế độ 5-bit.

| Cấu hình board | LCR khi DLAB=0 | Chú thích |
|---|---:|---|
| 8N1 | `0x03` | Parity tắt |
| 8O1 | `0x0B` | Odd parity |
| 8E1 | `0x1B` | Even parity; khác BASE-PULP chỉ xét PEN |

### 6.3. IER và FCR

| Register/bit | Hợp đồng |
|---|---|
| IER[0] | Cho phép ngắt RX data available/threshold |
| IER[1] | Cho phép ngắt TX holding/FIFO empty |
| IER[2] | Cho phép ngắt receiver line status OE/PE/FE/BI |
| IER[7:3] | Read 0, write ignored; IER effective mask `0x07` |
| FCR[0] | 1: FIFO capacity 16; 0: capacity 1; thay bit này flush cả hai queue |
| FCR[1] | Write-1 clear RX queue và OE/error-ack; không phải bit trạng thái giữ 1 |
| FCR[2] | Write-1 clear TX queue; không cắt ngang frame TX đang chạy |
| FCR[7:6] | 00/01/10/11 chọn RX threshold 1/4/8/14 khi FIFO enable |
| FCR[5:3] | Ignored; không DMA mode |

Write FCR luôn cập nhật bit enable và threshold đồng thời xử lý clear. **Sau khi enable FIFO, ghi `0x02` không phải thao tác “chỉ clear RX”**: bit 0=0 còn tắt FIFO và flush hai queue. Dùng `0x03` để clear RX giữ enable, `0x05` để clear TX giữ enable, `0x07` để clear cả hai giữ enable; giữ thêm [7:6] nếu cần giữ threshold. Khi FIFO disable, threshold effective=1 dù [7:6] lưu giá trị khác. FCR không xóa IER/LCR/divisor.

### 6.4. LSR

| Bit | Tên | Hợp đồng |
|---:|---|---|
| [0] | DR | RX queue có ít nhất 1 entry |
| [1] | OE | Sticky: frame hoàn tất nhưng không có slot nhận; clear-on-read LSR hoặc RX clear/reset |
| [2] | PE | Lỗi parity của entry ở đầu RX queue chưa được acknowledge |
| [3] | FE | Lỗi stop bit của entry đầu queue chưa được acknowledge |
| [4] | BI | Break của entry đầu queue chưa được acknowledge |
| [5] | THRE | TX queue rỗng; **không có nghĩa chỉ cần còn một chỗ trống** |
| [6] | TEMT | TX queue rỗng và shift/FSM đã phát xong cả stop bits |
| [7] | RX_ERR | Có entry mang PE/FE/BI chưa acknowledge trong RX queue |

LSR là ảnh trạng thái trước cạnh completion. Read LSR trả snapshot đó, clear OE cũ và acknowledge lỗi của **entry đầu queue đang tồn tại trước cạnh đó**. Data byte vẫn giữ nguyên cho lần đọc RBR. Mỗi entry phải giữ đúng lỗi của chính nó; không gắn lỗi của byte sau vào byte trước. LSR[7] không bao gồm OE.

Read RBR pop đúng 1 entry nếu nonempty; nếu bỏ qua việc đọc LSR trước, metadata của entry bị pop cũng mất theo entry. Software muốn ghi nhận lỗi phải đọc LSR trước RBR. Khi head thay đổi, PE/FE/BI phản ánh head mới. Nếu LSR read đồng thời nhận entry mới vào queue trước đó rỗng, entry mới **không** được acknowledge nhầm. Các ưu tiên đồng thời được quy định tại mục 9.

### 6.5. IIR và trạng thái ngắt

IIR không lưu mã ngắt cũ bằng cách AND/xóa từng bit. Mã readback được tính từ các nguồn đang pending và IER. `event_o=1` khi có nguồn được enable đang pending; IIR[0]=0 khi đó, bằng 1 khi không có nguồn. IIR[7:6]=11 nếu FCR[0]=1, ngược lại 00; IIR[5:4]=0.

| Nguồn | Điều kiện được enable | Ưu tiên | IIR khi FIFO off/on | Cách giải quyết |
|---|---|---:|---|---|
| Không có | Không nguồn nào hợp lệ | — | `0x01 / 0xC1` | Không có side effect |
| Receiver line status | IER[2] và (OE hoặc head có PE/FE/BI chưa ack) | 1 | `0x06 / 0xC6` | Read LSR; pop/clear/reset theo contract |
| RX data available | IER[0] và RX count ≥ threshold effective | 2 | `0x04 / 0xC4` | Đọc RBR làm count xuống dưới ngưỡng hoặc RX clear |
| TX holding empty | IER[1] và `tx_empty_pending` | 3 | `0x02 / 0xC2` | Read IIR **trả mã TX-empty**, hoặc THR write thành công |

Ba mã và thứ tự ưu tiên được chọn theo quy ước IIR tham chiếu S07. RX timeout/modem không thuộc profile. Toàn bộ handshake, clear và simultaneous-event dưới đây là hợp đồng dự án.

`tx_empty_pending` reset=0; đặt khi TX count chuyển từ >0 sang 0, hoặc IER[1] chuyển 0→1 lúc TX queue rỗng. Clear bởi THR write được nhận, hoặc read IIR trả mã TX-empty. Nếu một sự kiện đặt pending mới xảy ra đúng cạnh acknowledge, **set mới thắng clear cũ**. FCR clear làm count >0→0 cũng là sự kiện queue-empty. IER mask không cần xóa pending nội bộ, nhưng phải loại nguồn đó khỏi IIR/event ngay sau cạnh write.

Read IIR trả RLS/RDA không xóa nguồn đó và không acknowledge nhầm TX-empty đang bị nguồn ưu tiên cao hơn che. RDA là điều kiện mức theo RX occupancy, không lấy TX-empty làm nguồn. Khi mọi nguồn đã mask/clear, bắt buộc event_o=0 và IIR[0]=1; không được còn mã `0x00/0xC0` biểu thị trạng thái không-ngắt.

## 7. Baud generator và giao thức UART

### 7.1. Hợp đồng thời gian

Với D hợp lệ, một tick oversampling cách tick trước **đúng D cạnh CLK**. D=1 phải tạo một tick mỗi clock. Một bit UART dài đúng 16 tick, tức `16×D` clock. Dùng clock-enable, không dùng baud tick làm clock mới. TX và RX có phase counter độc lập để RX có thể căn lại phase theo start bit mà không làm thay đổi TX đang chạy.

Ví dụ counter của một tick có thể đếm `0..D−1` rồi quay về 0; không giữ phép so sánh `count==D` của baseline rồi coi tick vẫn dài D clock. Counter divisor cần chứa đến 65.534, phase 16× cần 16 trạng thái; mọi phép nhân/timeout ở testbench phải đủ rộng cho D=65.535.

```text
fCLK       = 50.000.000 Hz
TCLK       = 20 ns
D          = round(fCLK / (16 × baud_mục_tiêu))
Tbit       = 16 × D × TCLK
baud_thực  = fCLK / (16 × D)
sai_số_%   = 100 × (baud_thực / baud_mục_tiêu − 1)
Tframe     = (1 + N + P + S) × Tbit
```

N=5..8 data bits, P=0/1 parity bit, S=1/2 stop bits. Start bit không được dài thêm một clock so với data bit như BASE-PULP; mọi start/data/parity/stop của bản sửa phải cùng Tbit. Với 8N1 và D=27: **432 clock/bit = 8,64 µs/bit; 4.320 clock/frame = 86,4 µs/frame**. Các số sau là **tính toán thiết kế**, chưa phải waveform của TARGET-v1.0:

| Baud mục tiêu | D | DLM:DLL | Baud theo công thức | Sai số |
|---:|---:|---|---:|---:|
| 9.600 | 326 | `0x01:0x46` | 9.585,8896 | −0,1470% |
| 19.200 | 163 | `0x00:0xA3` | 19.171,7791 | −0,1470% |
| 38.400 | 81 | `0x00:0x51` | 38.580,2469 | +0,4694% |
| 57.600 | 54 | `0x00:0x36` | 57.870,3704 | +0,4694% |
| **115.200** | **27** | **`0x00:0x1B`** | **115.740,7407** | **+0,4694%** |

Sai số lượng tử tại 115200 nhỏ hơn 0,5%. Sai số oscillator thực tế và CP2102 chưa được đo; không cộng chúng vào cột kết quả trên. Profile board phải chạy với terminal cấu hình 115200; 115740,7407 là tốc độ tính từ clock danh định, không phải số cần nhập ở terminal.

D=0: không được bắt đầu frame TX/RX mới; không chia cho 0 hoặc chạy tràn counter; tx_o giữ idle nếu chưa có frame active. Frame đã bắt đầu với D cũ phải hoàn tất theo D đã chốt. TX queue đang có dữ liệu giữ nguyên cho đến khi D hợp lệ; THR write khi D=0 trả PSLVERR=1. RX không báo lỗi/đẩy byte từ tín hiệu xuất hiện trong thời gian bị disable và phải arm lại khi D hợp lệ. Reset abort frame là ngoại lệ có quyền cắt ngang.

### 7.2. TX

Byte vào TX shift register tại handshake pop FIFO. Cấu hình N/P/S/D và parity-select phải chốt cùng byte. Từ cạnh bắt đầu frame, tx_o chuyển 1→0 cho start; sau đúng Tbit phát bit 0, tiếp theo LSB-first. Chỉ N bit thấp có ý nghĩa; bit cao của THR không được phát thêm.

Đặt `x = XOR(data[N−1:0])`. Khi PEN=1: even parity phát `x`, odd parity phát `~x`; tổng XOR của data+parity lần lượt bằng 0/1. Không tính các bit ngoài N vào parity. Stop bit luôn 1; STB=1 phải giữ đủ hai Tbit, kể cả N=5.

Nếu queue còn byte kế tiếp tại biên kết thúc stop cuối, TX phải hỗ trợ bắt đầu frame tiếp theo ngay tại biên đó, không chèn idle bắt buộc. Không đọc lại data từ FIFO khi đang phát và không nhân đôi/mất byte ở biên frame. Nếu hết byte, giữ tx_o=1 vô thời hạn. Clear TX FIFO không được cắt ngang shift register hiện hành; reset thì được.

### 7.3. RX: đồng bộ, lấy mẫu và hoàn tất frame

Đường RX trong DUT giữ synchronizer ba FF như cấu trúc baseline; wrapper thêm hai FF theo hướng dẫn. RX sampling được quy định theo tín hiệu **sau synchronizer trong DUT**. Mọi phần tử synchronizer reset=1. Không đưa đầu ra tầng FF đầu vào logic khác ngoài tầng kế tiếp.

Khi idle đã armed và thấy cạnh xuống, RX chốt cấu hình và khởi động phase riêng. Gọi thời điểm phát hiện cạnh này là t0, tick thứ m xảy ra tại `t0 + m×D×TCLK`. Lấy majority 3 mẫu ở tick **7, 8, 9** của mỗi khoảng bit:

| Thành phần | Các tick lấy mẫu so với t0 |
|---|---|
| Start | 7, 8, 9 |
| Data bit k, k=0..N−1 | `16×(1+k) + {7,8,9}` |
| Parity, nếu có | `16×(1+N) + {7,8,9}` |
| Stop j, j=0..S−1 | `16×(1+N+P+j) + {7,8,9}` |

Nếu majority start=1, hủy false start: không enqueue, không đặt lỗi, chờ idle-high một Tbit để arm lại. Nếu start hợp lệ, thu N bit và zero-extend về 8 bit. Parity và từng stop phải kiểm tra trước khi tạo kết quả frame. Với tất cả stop hợp lệ (FE=0), quyết định hoàn tất ngay sau mẫu thứ ba của stop cuối, tick `16×(N+P+S)+9`; frame có FE được giữ đến cuối khoảng stop cuối, tick `16×(1+N+P+S)`, để quyết định BI. Phát đúng một completion pulse kèm data+PE+FE+BI; queue nhận kết quả tại cạnh CLK ngay sau cạnh quyết định. Không đưa byte vào FIFO trong state DATA rồi mới tính parity như baseline.

PE=1 nếu parity nhận khác expected theo PEN/EPS; PEN=0 thì PE=0. FE=1 nếu majority của **bất kỳ stop bit được yêu cầu** bằng 0. Frame có PE/FE vẫn được enqueue nếu còn chỗ, kèm đúng metadata của nó. RX không backpressure được CP2102 trên đường serial.

Sau reset/disable, receiver chỉ arm sau khi input đồng bộ giữ mức 1 liên tục ít nhất một Tbit của D hiện hành. Với frame FE=0, sau khi stop cuối được xác nhận tốt, receiver được phép chờ cạnh xuống của frame tiếp ngay, không chờ hết một stop bit theo counter nội bộ và không bắt peer chèn thêm idle. Điều này cần thiết khi peer nhanh hơn DUT một ít. Nếu completion của frame cũ và phát hiện cạnh start mới cùng một cạnh CLK, phải giữ cả completion cũ và khởi động nhận frame mới, không dùng một state SAVE_DATA chặn start mới. Frame có PE nhưng FE=0 cũng dùng quy tắc arm sớm này; frame có FE không dùng arm sớm dù stop cuối riêng lẻ có thể đúng.

Mục tiêu kiểm thử sai lệch baud: khi `0,98 ≤ baud_peer/baud_DUT ≤ 1,02`, với phase bắt đầu bất kỳ trong một chu kỳ CLK, receiver phải nhận đúng frame sạch ở các format bắt buộc. Đây là sai lệch **tổng tương đối giữa hai đầu**, không phải mỗi đầu được tự sai ±2%. Phải đo bằng stimulus độc lập, gồm biên ±2%, chứ không chỉ nối TX→RX cùng clock.

### 7.4. Break và phục hồi sau frame lỗi

Break được xác định khi đường RX đồng bộ giữ 0 liên tục từ start qua hết toàn bộ thời gian frame cấu hình. Tại completion, enqueue một byte `0x00` với BI=1 và FE=1; PE vẫn theo phép kiểm parity nếu parity bật. Theo dõi tính liên tục mức 0 ở mỗi CLK, không suy ra break chỉ vì các bit data bằng 0.

Sau break, không tạo thêm byte/BI lặp lại khi đường RX còn thấp. Phải thấy idle-high đủ một Tbit rồi mới arm lại. Sau FE cũng yêu cầu idle-high một Tbit để đồng bộ lại. Error trên entry đã nhận không bị xóa chỉ vì đường RX trở về idle. Nếu break/error xảy ra khi RX queue full, frame mới bị drop theo mục 9 và chỉ OE mới phản ánh sự mất entry; PE/FE/BI của entry bị drop không được gán vào một byte cũ.

## 8. Reset và thay cấu hình

### 8.1. Reset DUT

RSTN assert thấp phải reset register/control/FIFO counters mà không cần một giao dịch APB. Reset thắng mọi transfer, RX completion, FIFO push/pop và interrupt set/clear ở cạnh trùng nhau. TX lập tức trở về idle=1; RX frame dang dở bị bỏ, không tạo byte/PE/FE/OE do việc reset.

| Thành phần sau reset | Giá trị |
|---|---|
| DLL, DLM, LCR, IER | 0 |
| FCR enable, trigger code | 0; capacity=1, threshold effective=1 |
| TX/RX counts và pointers | 0 |
| TX/RX FSM, baud phase | idle, phase=0 |
| RX metadata/ack hợp lệ, OE | Không có entry hợp lệ; OE=0 |
| `tx_empty_pending`, event_o | 0 |
| LSR / IIR sau release | `0x60 / 0x01` |
| tx_o / RX synchronizer | 1 / mọi tầng 1 |

Không bắt buộc reset mọi bit RAM FIFO nếu valid/count đã làm entry cũ vô hiệu; đọc RBR empty vẫn phải trả 0. Reset đang SETUP/ACCESS hủy transfer, master cũng phải reset và khởi động giao dịch mới; không replay âm thầm giao dịch trước reset.

### 8.2. Reset hệ thống

KEY0 active-low là yêu cầu reset bất đồng bộ. Wrapper assert reset nội bộ ngay khi KEY0=0 và chỉ deassert sau hai cạnh CLOCK_50 liên tiếp khi KEY0 đã cao. DUT và wrapper dùng cùng reset nội bộ. Khi KEY0 nảy, mỗi mức thấp được phép assert lại reset; chỉ KEY1 cần debounce 10 ms cho thao tác send.

Sau cấu hình FPGA, quy trình sử dụng bắt buộc nhấn KEY0 ít nhất 1 µs rồi nhả. Không dựa vào giả định mọi FF có power-up value tương đương reset. Khi mô phỏng DUT, reset pulse phải kéo dài ít nhất hai chu kỳ CLK. Việc thêm power-on-reset tự động sau này không được làm mất reset KEY0 hoặc đổi reset register contract.

Reset wrapper xóa init_done, fault, hai pending slot, byte RX hiển thị, các LED lỗi đã giữ và bộ đếm debounce/poll. Byte RX mặc định hiển thị `00`; TX HEX theo SW sau đồng bộ. Gửi/echo đang pending bị hủy; không phát lại chúng sau init mới.

## 9. FIFO, overflow và các sự kiện đồng thời

### 9.1. Hợp đồng queue

Ở mỗi cạnh, mọi quyết định dùng count/valid **trước cạnh đó**, rồi cập nhật state một lần. Capacity C=16 nếu FCR[0]=1, ngược lại C=1. Count luôn nằm trong 0..C. Không có bypass từ một push vào FIFO empty sang pop cùng cạnh.

`pop_ok = pop_req && (count>0)`; `push_ok = push_req && ((count<C) || pop_ok)` nếu không reset/clear. Với RX, push_req là completion pulse; với TX là THR write hợp lệ. TX pop_req do transmitter muốn bắt đầu frame. RX pop_req do APB read RBR. Khi cả push và pop được nhận, read/pop lấy entry cũ ở đầu queue trước khi ghi entry mới.

| Trước cạnh | Push | Pop request | Kết quả |
|---|---:|---:|---|
| Empty | 1 | 1 | Không pop; nhận push; count=1; APB read-empty vẫn trả 0 |
| 0<count<C | 1 | 1 | Pop cũ + push mới; count giữ nguyên |
| Full | 1 | 1 | Nếu pop thật sự hợp lệ: nhận cả hai; count=C; không RX OE |
| Full | 1 | 0 | RX drop mới + OE=1; TX THR trả PSLVERR=1 |
| Bất kỳ | 0 | 1 | Pop chỉ khi nonempty |
| Reset/clear | bất kỳ | bất kỳ | Theo ưu tiên flush bên dưới |

### 9.2. RX overflow

Frame hoàn tất mà không có push_ok phải bị drop ngay và set OE. Giữ nguyên tất cả entry cũ và thứ tự của chúng; receiver trở lại xử lý đường serial, không chờ APB mở slot bằng cách giữ frame trong SAVE_DATA. Do đó khi FIFO enable và không đọc, gửi 17 frame đúng liên tiếp phải giữ **16 frame đầu**, drop frame thứ 17 và OE=1. Đây là thay đổi có chủ đích so với BASE-PULP đã quan sát giữ thêm một frame chờ.

OE là sticky event độc lập với metadata của head. Nếu read LSR clear OE cũ cùng cạnh có overflow mới, OE sau cạnh phải vẫn là 1. Mất nhiều frame khi OE đã 1 không cần đếm số mất; không tự clear OE sau khi queue có chỗ.

### 9.3. Ưu tiên reset/clear/ack

1. **Reset**: xóa tất cả theo mục 8.
2. **FCR queue-clear hoặc đổi enable**: flush queue liên quan, count/pointer/valid về 0; RX flush xóa OE và mọi error-ack/metadata hợp lệ. Completion RX đúng cạnh flush bị bỏ có chủ đích, không tạo OE. TX không khởi động một frame từ entry queue cũ ở cạnh flush; frame đã active vẫn hoàn tất.
3. **Push/pop bình thường**: áp dụng bảng 9.1; frame active RX không bị abort chỉ vì FCR clear trước khi frame hoàn tất.
4. **LSR acknowledge**: chỉ tác động head cũ còn phù hợp; không clear lỗi của entry mới push. Overflow mới thắng OE clear cũ.

Một giao dịch APB không thể đồng thời đọc RBR và đọc LSR/FCR trên cùng bus. Các ca “đồng thời” cần kiểm là side effect APB với sự kiện hardware TX/RX hoặc reset, không giả định có hai master truy cập cùng cạnh.

## 10. Hợp đồng wrapper DE2-115

### 10.1. Đồng bộ input và nút nhấn

KEY1 qua invert và synchronizer 2FF rồi debounce. Khi mẫu đồng bộ khác trạng thái stable, phải đếm đủ **500.000 mẫu clock liên tiếp** của mức mới; mẫu quay về stable phải reset counter. Cả cạnh nhấn và cạnh nhả đều qua điều kiện này. Cạnh stable 0→1 tạo send_pulse dài đúng một CLOCK_50; giữ nút không tạo thêm pulse. Chỉ sau nhả stable rồi nhấn stable mới được gửi tiếp.

SW qua synchronizer hai tầng. SW data không phải bus handshake nguyên tử; điều kiện thao tác là giữ SW[7:0] ổn định ít nhất 1 ms trước lúc bắt đầu nhấn KEY1 và đến khi nút được debounce. Khi nhận send_pulse, wrapper chốt byte dữ liệu vào manual slot; gạt SW sau đó không làm thay đổi byte pending. HEX TX có thể tiếp tục hiển thị SW hiện tại, không bắt buộc hiển thị byte pending.

GPIO_UART_RX qua wrapper 2FF reset=1 trước khi vào DUT; DUT giữ synchronizer nội bộ ba FF. Không thêm clock domain mới; độ trễ chuỗi đồng bộ được tính trong mô phỏng wrapper và CDC/STA review.

### 10.2. Switch mode và cấu hình ban đầu

| Switch | Chức năng và thời điểm có hiệu lực |
|---|---|
| SW[7:0] | Byte TX; chốt tại send_pulse được nhận |
| SW[13:8] | Dự phòng, không có tác dụng |
| SW[14] | Parity enable; chốt một lần trong init sau reset |
| SW[15] | 0=odd, 1=even khi SW14=1; chốt cùng SW14 |
| SW[16] | 1=hold RX: không bắt đầu giao dịch đọc RBR mới; live sau đồng bộ |
| SW[17] | Echo enable; chốt quyết định cho từng RBR read tại SETUP của giao dịch đó |

Đổi SW14/15 lúc đang chạy không tự đổi UART; cần reset lại và đổi terminal tương ứng. SW16 lên 1 trong lúc RBR ACCESS đã bắt đầu không được hủy APB; cho phép hoàn tất tối đa giao dịch đang chạy. SW17 thay đổi sau SETUP không thay quyết định echo của byte đang đọc.

Người thao tác phải giữ SW14/15 ổn định ít nhất 1 ms trước khi nhả KEY0 và trong chuỗi init. SW16/17 chỉ đồng bộ, không có debounce; bài kiểm chức năng phải giữ các switch này ổn định quanh khoảng traffic cần đánh giá.

### 10.3. Chuỗi init

Sau release reset nội bộ, chờ ít nhất bốn clock để SW14/15 qua synchronizer rồi chốt mode. Phát sáu **APB WRITE** theo thứ tự, mỗi write có SETUP/ACCESS và kiểm PSLVERR:

| Bước | Thanh ghi | PADDR | PWDATA[7:0] | Kết quả |
|---:|---|---:|---:|---|
| 1 | LCR | `0x00C` | `0x83` | DLAB=1, 8-bit |
| 2 | DLL | `0x000` | `0x1B` | D=27 low byte |
| 3 | DLM | `0x004` | `0x00` | D=27 high byte |
| 4 | LCR | `0x00C` | `0x03/0x0B/0x1B` | 8N1/8O1/8E1, DLAB=0 |
| 5 | FCR | `0x008` | `0x07` | Enable FIFO, clear RX/TX, threshold=1 |
| 6 | IER | `0x004` | `0x05` | Enable RX-data và RX-error IRQ; không enable TX-empty IRQ |

Sau completion bước 6 thành công, init_done=1. Với clock/inputs hợp lệ, không có APB error, phải hoàn tất init trong **không quá 32 clock sau release reset nội bộ**. Init_done nghĩa là sáu giao dịch đã được slave chấp nhận; không phải chứng nhận baud/pin/PC đang hoạt động. RX peer phải giữ idle ít nhất một Tbit sau cấu hình để receiver arm trước frame đầu.

### 10.4. State machine và lịch xử lý

Giữ 11 trạng thái chức năng theo hướng dẫn: ST_RESET, sáu ST_INIT, ST_IDLE, ST_POLL_LSR, ST_READ_RBR, ST_WRITE_THR. SETUP/ACCESS là phase phụ của mỗi trạng thái giao dịch. Thêm ST_FAULT để kết thúc có kiểm soát khi APB phản hồi lỗi; không ép mọi xử lý vào 11 giá trị state nếu gây thiếu hợp đồng lỗi.

```text
RESET → INIT LCR/DLL/DLM/LCR/FCR/IER → IDLE
                                        │ timer / IRQ / TX pending
                                        v
                                     POLL_LSR
                                    /        \
                       RX được phép          TX pending, THRE=1
                           v                         │
                        READ_RBR ────────────────────┤
                           │                         v
                           └──────→ IDLE ←────── WRITE_THR

APB error tại bất kỳ transaction → FAULT → chỉ thoát bằng reset
```

- Khi idle, bắt đầu POLL_LSR khi timer 5.000 clock hết hạn, có manual/echo pending cần phục vụ, hoặc event_o=1 và SW16=0. Không chờ cạnh lên IRQ duy nhất vì IRQ là mức.
- Timer đo khoảng giữa các lần completion LSR read; reset timer sau mỗi lần đọc. Nếu đang bận APB khi timer hết, thực hiện poll ở cơ hội kế tiếp.
- Mỗi vòng xử lý tối đa một RBR read, sau đó tối đa một THR write rồi về IDLE. Có RX liên tục không được bỏ qua cơ hội TX của vòng đó.
- SW16=1: không đọc RBR mới; vẫn poll LSR định kỳ, gửi manual/echo đã pending và cập nhật lỗi. Không để IRQ RX đang giữ mức 1 ép vòng poll không giới hạn làm ảnh hưởng nút gửi.
- Chỉ phát THR write sau khi một LSR read thấy THRE=1. Với master duy nhất, không có THR write khác xen giữa kiểm tra này và giao dịch dùng kết quả; hardware chỉ làm TX queue giảm. Không suy ra “TX có chỗ” từ các bit không được định nghĩa.
- Khi idle/quiescent, send_pulse hoặc IRQ hợp lệ phải bắt đầu một vòng xử lý trong tối đa 8 clock. Không đưa ra cam kết mỗi byte hoàn tất TX trong thời gian này vì còn thời gian serial.

### 10.5. Gửi tay, echo và backpressure nội bộ

Manual slot chứa `valid` và byte chốt từ SW. send_pulse khi init_done=1 và slot rỗng nhận đúng một byte; khi slot đã đầy phải giữ byte cũ, từ chối byte mới và set fault sticky. Pulse trước init_done bị bỏ, không replay. Với tốc độ nhấn hợp lệ của debounce và không có tắc nghẽn traffic, mỗi lần nhấn phải được nhận một lần.

Ngoại lệ có chủ đích cho cạnh đồng thời: nếu THR write thành công đang tiêu thụ manual slot đúng cạnh send_pulse mới, byte cũ đi vào DUT còn byte mới được nhận vào slot; valid vẫn bằng 1, không báo overflow. Clear của yêu cầu cũ không được xóa yêu cầu mới. Trong ST_FAULT không nhận thêm send_pulse dù một pending slot còn trống.

Khi chuẩn bị đọc RBR và SW17=1, wrapper chỉ được đọc nếu echo slot rỗng. Sau completion RBR thành công, hiển thị byte RX và đưa **đúng byte PRDATA[7:0]** vào echo slot. Không dùng SW thay byte echo. Nếu echo slot đầy, hoãn RBR để bảo toàn byte; RX FIFO có thể đầy và phải báo OE đúng nếu peer tiếp tục gửi.

THR write lấy từ manual hoặc echo slot. Nếu cả hai valid, chọn luân phiên theo nguồn đã được phục vụ gần nhất; nếu chỉ một valid thì chọn nguồn đó. Chỉ clear slot sau completion write với PSLVERR=0. THR trả lỗi phải giữ slot và vào ST_FAULT, không giả vờ byte đã gửi.

SW16 không ngăn TX hoặc nhận serial vào RX FIFO; nó chỉ ngăn master pop RBR. Tắt echo không xóa một echo byte đã được chốt pending. Nhận frame có PE/FE/BI vẫn có thể hiển thị/echo data của frame đó; LED lỗi phải báo lỗi đã đọc. Không có cam kết sửa nội dung byte bị nhiễu.

Không cam kết echo lossless vô hạn khi tốc độ byte vào lớn hơn khả năng TX hoặc tổng lưu lượng echo+manual vượt tốc độ serial ra. Ca nghiệm thu lossless phải dùng traffic hữu hạn/rate trong khả năng hệ thống; ca overload phải quan sát OE và dữ liệu bị drop đúng chính sách, không coi mọi overflow là lỗi triển khai.

### 10.6. Fault và hiển thị

| Tín hiệu | Hiển thị chính thức |
|---|---|
| HEX1:HEX0 | SW[7:4]:SW[3:0] sau đồng bộ |
| HEX5:HEX4 | Byte của RBR read thành công gần nhất; reset=`00` |
| LEDR[0] | LSR[0] của lần POLL_LSR hoàn tất gần nhất |
| LEDR[1] | Sticky OR của OE đã đọc từ LSR từ lần reset gần nhất |
| LEDR[2] | Sticky OR của PE đã đọc |
| LEDR[3] | Sticky OR của FE đã đọc |
| LEDR[4] | Sticky OR của BI đã đọc |
| LEDG[0] | init_done; hạ nếu reset hoặc APB fault |
| LEDG[1] | fault sticky: APB error hoặc manual slot overflow; reset để clear |
| LEDG[7:2] | 0 cố định |
| LEDG[8] | event_o trực tiếp; không giữ sticky |

Giữ lỗi trên LEDR là bổ sung có chủ đích so với snapshot trực tiếp trong hướng dẫn: read LSR có thể acknowledge lỗi rất nhanh, còn LED cần giữ để người thao tác thấy. Đây là register của wrapper, **không thay đổi hành vi clear-on-read LSR của DUT**. Manual slot overflow chỉ bật fault LED; không hạ init_done hoặc dừng UART. APB error thì vào ST_FAULT, hạ init_done, dừng phát APB mới; DUT có thể hoàn tất frame active, chỉ reset mới restart hệ thống.

HEX active-low, `HEX[6:0]={g,f,e,d,c,b,a}`. Pattern nhị phân tương ứng nibble 0..F: `1000000,1111001,0100100,0110000,0011001,0010010,0000010,1111000,0000000,0010000,0001000,0000011,1000110,0100001,0000110,0001110`. B và D hiển thị dạng b/d; không đảo thứ tự index khi gán pin.

## 11. Mục tiêu triển khai Quartus, timing và CDC

Chọn **Cyclone IV E, EP4CE115F29C7**, top `de2_115_apb_uart_bringup`, source SystemVerilog. Compilation list phải chứa đúng bản TARGET-v1.0 và wrapper, không trộn module baseline trùng tên. Tất cả logic chức năng dùng CLOCK_50; không thêm clock gated từ counter/debouncer.

Ràng buộc clock gốc cần có tương đương:

```tcl
create_clock -name CLOCK_50 -period 20.000 [get_ports {CLOCK_50}]
```

Đây là clock requirement, không phải bộ SDC hoàn chỉnh để copy rồi coi đã timing-closed. Bước triển khai phải bổ sung clock uncertainty phù hợp flow, phân loại đường asynchronous RX/KEY/SW và đường reset; chỉ cắt timing tới tầng synchronizer đầu hoặc đường async reset được đánh giá. Không false-path toàn bộ synchronizer chain hoặc mọi đường IO để che vi phạm. Giữ ràng buộc giữa các tầng FF đồng bộ; kiểm recovery/removal của reset release theo cấu trúc đã chọn.

Tiêu chí triển khai: Quartus compile/fitter không error; không có latch ngoài ý muốn; mọi clock được xác định; không có setup/hold violation ở các đường synchronous được ràng buộc tại 50 MHz; mọi path unconstrained/exception phải có giải thích và review. Kiểm pin không trùng, I/O voltage đúng bank/jumper, và toàn bộ bit port đã gán. Không đặt mục tiêu LUT/FF/Fmax/số điện năng như kết quả đã đo; báo cáo resource/timing sẽ được bổ sung ở Yêu cầu 3.

## 12. Kết nối PC–CP2102 và quy trình sử dụng

| CP2102 | Header DE2-115 | Tín hiệu FPGA |
|---|---|---|
| RXD | JP5 chân 1, GPIO[0] | GPIO_UART_TX, PIN_AB22 |
| TXD | JP5 chân 3, GPIO[2] | GPIO_UART_RX, PIN_AB21 |
| GND | JP5 chân 12 hoặc 30 theo hướng dẫn | Ground chung, không phải port HDL |

Dùng UART logic 3.3 V phù hợp bank GPIO; đây không phải cổng RS-232 ± điện áp. Không nối chân nguồn 3V3/5V CP2102 sang board theo S02. CSV S05 gán GPIO 3.3-V LVTTL; manual S06 cho biết GPIO bank do JP6 lựa chọn, vì vậy người thực hiện phải kiểm JP6 và mức logic của module CP2102 thực tế trước khi đấu. Chưa có xác nhận vật lý cho board/module của người dùng.

Quy trình chuẩn: chọn mode SW14/15 → nạp bitstream TARGET-v1.0 → reset bằng KEY0 → mở terminal đúng 115200, 8N1/8O1/8E1, hardware/software flow control off → xác nhận LEDG0 sáng, LEDG1 tắt → thử PC→FPGA, FPGA→PC, echo, hold-RX và fault injection. Tắt local echo của terminal khi đánh giá echo FPGA để tránh nhầm byte do terminal tự hiển thị.


## 13. Bảng gán chân đầy đủ

Nguồn S05, giữ đúng index từng bit và I/O standard. GPIO[0]/GPIO[2] trong CSV là chân đa dụng, nhưng top này cố định TX là output và RX là input. Các chân dự phòng vẫn được gán theo board. Bảng này xác nhận mapping từ tài liệu, chưa thay cho kiểm tra pin planner/JP6 trên phần cứng.

| Port top | Chiều | Signal board | Pin FPGA | I/O standard |
|---|---|---|---|---|
| `CLOCK_50` | input | `CLOCK_50` | `PIN_Y2` | 3.3-V LVTTL |
| `KEY[0]` | input | `KEY[0]` | `PIN_M23` | 2.5 V |
| `KEY[1]` | input | `KEY[1]` | `PIN_M21` | 2.5 V |
| `SW[0]` | input | `SW[0]` | `PIN_AB28` | 2.5 V |
| `SW[1]` | input | `SW[1]` | `PIN_AC28` | 2.5 V |
| `SW[2]` | input | `SW[2]` | `PIN_AC27` | 2.5 V |
| `SW[3]` | input | `SW[3]` | `PIN_AD27` | 2.5 V |
| `SW[4]` | input | `SW[4]` | `PIN_AB27` | 2.5 V |
| `SW[5]` | input | `SW[5]` | `PIN_AC26` | 2.5 V |
| `SW[6]` | input | `SW[6]` | `PIN_AD26` | 2.5 V |
| `SW[7]` | input | `SW[7]` | `PIN_AB26` | 2.5 V |
| `SW[8]` | input | `SW[8]` | `PIN_AC25` | 2.5 V |
| `SW[9]` | input | `SW[9]` | `PIN_AB25` | 2.5 V |
| `SW[10]` | input | `SW[10]` | `PIN_AC24` | 2.5 V |
| `SW[11]` | input | `SW[11]` | `PIN_AB24` | 2.5 V |
| `SW[12]` | input | `SW[12]` | `PIN_AB23` | 2.5 V |
| `SW[13]` | input | `SW[13]` | `PIN_AA24` | 2.5 V |
| `SW[14]` | input | `SW[14]` | `PIN_AA23` | 2.5 V |
| `SW[15]` | input | `SW[15]` | `PIN_AA22` | 2.5 V |
| `SW[16]` | input | `SW[16]` | `PIN_Y24` | 2.5 V |
| `SW[17]` | input | `SW[17]` | `PIN_Y23` | 2.5 V |
| `LEDR[0]` | output | `LEDR[0]` | `PIN_G19` | 2.5 V |
| `LEDR[1]` | output | `LEDR[1]` | `PIN_F19` | 2.5 V |
| `LEDR[2]` | output | `LEDR[2]` | `PIN_E19` | 2.5 V |
| `LEDR[3]` | output | `LEDR[3]` | `PIN_F21` | 2.5 V |
| `LEDR[4]` | output | `LEDR[4]` | `PIN_F18` | 2.5 V |
| `LEDG[0]` | output | `LEDG[0]` | `PIN_E21` | 2.5 V |
| `LEDG[1]` | output | `LEDG[1]` | `PIN_E22` | 2.5 V |
| `LEDG[2]` | output | `LEDG[2]` | `PIN_E25` | 2.5 V |
| `LEDG[3]` | output | `LEDG[3]` | `PIN_E24` | 2.5 V |
| `LEDG[4]` | output | `LEDG[4]` | `PIN_H21` | 2.5 V |
| `LEDG[5]` | output | `LEDG[5]` | `PIN_G20` | 2.5 V |
| `LEDG[6]` | output | `LEDG[6]` | `PIN_G22` | 2.5 V |
| `LEDG[7]` | output | `LEDG[7]` | `PIN_G21` | 2.5 V |
| `LEDG[8]` | output | `LEDG[8]` | `PIN_F17` | 2.5 V |
| `HEX0[0]` | output | `HEX0[0]` | `PIN_G18` | 2.5 V |
| `HEX0[1]` | output | `HEX0[1]` | `PIN_F22` | 2.5 V |
| `HEX0[2]` | output | `HEX0[2]` | `PIN_E17` | 2.5 V |
| `HEX0[3]` | output | `HEX0[3]` | `PIN_L26` | 2.5 V |
| `HEX0[4]` | output | `HEX0[4]` | `PIN_L25` | 2.5 V |
| `HEX0[5]` | output | `HEX0[5]` | `PIN_J22` | 2.5 V |
| `HEX0[6]` | output | `HEX0[6]` | `PIN_H22` | 2.5 V |
| `HEX1[0]` | output | `HEX1[0]` | `PIN_M24` | 2.5 V |
| `HEX1[1]` | output | `HEX1[1]` | `PIN_Y22` | 2.5 V |
| `HEX1[2]` | output | `HEX1[2]` | `PIN_W21` | 2.5 V |
| `HEX1[3]` | output | `HEX1[3]` | `PIN_W22` | 2.5 V |
| `HEX1[4]` | output | `HEX1[4]` | `PIN_W25` | 2.5 V |
| `HEX1[5]` | output | `HEX1[5]` | `PIN_U23` | 2.5 V |
| `HEX1[6]` | output | `HEX1[6]` | `PIN_U24` | 2.5 V |
| `HEX4[0]` | output | `HEX4[0]` | `PIN_AB19` | 3.3-V LVTTL |
| `HEX4[1]` | output | `HEX4[1]` | `PIN_AA19` | 3.3-V LVTTL |
| `HEX4[2]` | output | `HEX4[2]` | `PIN_AG21` | 3.3-V LVTTL |
| `HEX4[3]` | output | `HEX4[3]` | `PIN_AH21` | 3.3-V LVTTL |
| `HEX4[4]` | output | `HEX4[4]` | `PIN_AE19` | 3.3-V LVTTL |
| `HEX4[5]` | output | `HEX4[5]` | `PIN_AF19` | 3.3-V LVTTL |
| `HEX4[6]` | output | `HEX4[6]` | `PIN_AE18` | 3.3-V LVTTL |
| `HEX5[0]` | output | `HEX5[0]` | `PIN_AD18` | 3.3-V LVTTL |
| `HEX5[1]` | output | `HEX5[1]` | `PIN_AC18` | 3.3-V LVTTL |
| `HEX5[2]` | output | `HEX5[2]` | `PIN_AB18` | 3.3-V LVTTL |
| `HEX5[3]` | output | `HEX5[3]` | `PIN_AH19` | 3.3-V LVTTL |
| `HEX5[4]` | output | `HEX5[4]` | `PIN_AG19` | 3.3-V LVTTL |
| `HEX5[5]` | output | `HEX5[5]` | `PIN_AF18` | 3.3-V LVTTL |
| `HEX5[6]` | output | `HEX5[6]` | `PIN_AH18` | 3.3-V LVTTL |
| `GPIO_UART_TX` | output | `GPIO[0]` | `PIN_AB22` | 3.3-V LVTTL |
| `GPIO_UART_RX` | input | `GPIO[2]` | `PIN_AB21` | 3.3-V LVTTL |

## 14. Danh mục yêu cầu và tiêu chí nghiệm thu

### 14.1. Requirement index

Các ID `TGT-*` chỉ dùng cho TARGET-v1.0. ID `REQ_*` của SPEC v0.3 được giữ trong bảng chuyển đổi mục 16; không tái sử dụng một ID cũ cho contract đã đổi. Cột DOC là kiểm tài liệu/cấu hình; AT01..AT08 là nhóm nghiệm thu phải triển khai ở Yêu cầu 2/3. **Tại thời điểm phát hành SPEC, tất cả kết quả thực thi TARGET là NOT_RUN.** Kết quả mới được quản lý riêng trong [DV results](dv/RESULTS.md); danh mục requirement giữ snapshot ban đầu.

| ID | Mục quy định | Yêu cầu bắt buộc | Nhóm nghiệm thu |
|---|---|---|---|
| `TGT-SRC-01` | 1,3 | Giữ nguyên baseline S03; filelist bản sửa không compile trùng module. | DOC |
| `TGT-SRC-02` | 1,15 | Ghi đúng version DUT/TB/tool và không dùng baseline PASS để đóng yêu cầu target. | DOC |
| `TGT-APB-01` | 5.1 | Mọi transfer có SETUP trước ACCESS; control/data giữ ổn định đến completion. | AT01 |
| `TGT-APB-02` | 5.1 | Chỉ side effect một lần tại completion; không side effect ở idle/setup. | AT01 |
| `TGT-APB-03` | 4.1,5 | PRDATA zero-extend byte; ngoài valid read hoặc khi reset phải bằng 0. | AT01 |
| `TGT-APB-04` | 5.2,6.1 | Decode đúng word-aligned/full-address; không alias address cao hoặc misaligned. | AT01 |
| `TGT-APB-05` | 5 | PREADY=1 cố định; master kiểm PSLVERR tại completion. | AT01 |
| `TGT-APB-06` | 5.2 | Invalid address/quyền truy cập trả PSLVERR=1, PRDATA=0, không thay state. | AT01 |
| `TGT-APB-07` | 5.2,9.1 | RBR empty trả 0/no-error; không pop phantom hoặc lấy byte vừa push cùng cạnh. | AT01, AT05 |
| `TGT-APB-08` | 5.2,9.1 | THR full không pop hoặc D=0 bị từ chối, không enqueue hay đặt RX OE. | AT01, AT05 |
| `TGT-REG-01` | 6.1,6.2 | DLAB chọn đúng DLL/DLM hoặc RBR/THR/IER; không ảnh hưởng IIR/FCR/LSR. | AT01 |
| `TGT-REG-02` | 6.2 | LCR WLS/STB/PEN/EPS/DLAB hoạt động; bits 6:5 read-zero/write-ignore. | AT01, AT02, AT03 |
| `TGT-REG-03` | 6.3 | IER chỉ giữ bits 2:0; write khi DLAB=1 không đổi IER. | AT01, AT06 |
| `TGT-REG-04` | 6.3,9 | FCR enable chọn capacity 1/16; đổi enable flush hai queue đúng ưu tiên. | AT05 |
| `TGT-REG-05` | 6.3,9.3 | FCR RX clear xóa queue/OE/metadata; không abort frame RX chưa hoàn tất. | AT05 |
| `TGT-REG-06` | 6.3,9.3 | FCR TX clear xóa queued bytes; không cắt frame active hoặc lấy byte cũ ở cạnh clear. | AT05 |
| `TGT-REG-07` | 6.3 | Threshold effective là 1/4/8/14 khi FIFO on, bằng 1 khi FIFO off. | AT05, AT06 |
| `TGT-REG-08` | 6.4 | LSR DR/THRE/TEMT/OE/head-error/RX_ERR phản ánh đúng state được định nghĩa. | AT01, AT04, AT05 |
| `TGT-REG-09` | 6.4,9.3 | Read LSR clear OE cũ/ack head cũ, không ack byte mới hoặc xóa overflow mới. | AT04, AT05, AT06 |
| `TGT-REG-10` | 6.5 | IIR mã 01/06/04/02 với bits FIFO đúng; read không nhầm side effect. | AT06 |
| `TGT-REG-11` | 6.2 | Frame snapshot config trước cạnh start; config write cùng cạnh áp dụng cho frame sau. | AT07 |
| `TGT-BAUD-01` | 7.1 | Một oversample tick mỗi D clock; một bit đúng 16D clock; không tạo clock domain mới. | AT02 |
| `TGT-BAUD-02` | 7.1 | D=0 không start frame mới; không divide-by-zero; frame active hoàn tất theo D đã chốt. | AT02, AT07 |
| `TGT-BAUD-03` | 7.1,10.3 | Board profile D=27, DLL=1B/DLM=00, bit=432 clock tại 50 MHz. | AT02, AT08 |
| `TGT-BAUD-04` | 3,7.1 | D hợp lệ 1..65535; counter đủ rộng, không overflow ở cực trị. | AT02 |
| `TGT-BAUD-05` | 7.1,7.2 | Start/data/parity/stop cùng Tbit, không thừa một clock ở start. | AT02 |
| `TGT-BAUD-06` | 7.3 | RX nhận đúng frame sạch ở tổng mismatch ±2% và phase bắt đầu khác nhau. | AT03 |
| `TGT-TX-01` | 7.2 | TX idle/reset=1, start=0, dữ liệu LSB-first, phát đúng byte được enqueue. | AT02 |
| `TGT-TX-02` | 7.2 | Chỉ phát 5/6/7/8 data bits theo WLS, không phát bit cao ngoài N. | AT02 |
| `TGT-TX-03` | 7.2 | None/odd/even parity đúng XOR của đúng N data bits. | AT02 |
| `TGT-TX-04` | 7.2 | Giữ đủ 1/2 stop bits; kiểm bằng frame liên tiếp, không chỉ sample idle. | AT02 |
| `TGT-TX-05` | 7.2 | Có queued byte thì cho phép next start ngay sau stop cuối, không mất/nhân đôi byte. | AT02 |
| `TGT-TX-06` | 2,7 | TX và RX hoạt động đồng thời, không dùng chung phase gây dịch timing. | AT02, AT03 |
| `TGT-RX-01` | 4.1,7.3 | Synchronizer RX reset-high; sampling chỉ dùng tín hiệu sau đồng bộ. | AT03, AT07 |
| `TGT-RX-02` | 7.3 | Majority 7/8/9; false start không tạo byte/error. | AT03 |
| `TGT-RX-03` | 7.3 | Nhận đúng N bit, zero-extend data, đúng thứ tự và số lượng frame. | AT03 |
| `TGT-RX-04` | 7.3 | Sai parity odd/even đặt PE trên đúng byte; parity off không đặt PE. | AT04 |
| `TGT-RX-05` | 7.3 | Stop nào sai cũng đặt FE; frame lỗi vẫn được lưu nếu có slot. | AT04 |
| `TGT-RX-06` | 7.4 | Break tạo một entry zero với BI/FE, không lặp byte khi còn thấp; phục hồi sau idle. | AT04 |
| `TGT-RX-07` | 7.3 | Completion chỉ sau khi kiểm parity/stop và đủ quyết định BI; metadata nguyên tử với data. | AT03, AT04 |
| `TGT-RX-08` | 9.2 | Full không slot: drop frame mới, set OE, tiếp tục nhận; không hidden slot thứ 17. | AT05 |
| `TGT-RX-09` | 7.3,7.4 | Arm sau reset/disable/error đúng điều kiện idle; không nhận frame giả từ mức thấp kéo dài. | AT03, AT04, AT07 |
| `TGT-RX-10` | 7.3 | Nhận frame liên tiếp kể cả peer nhanh hơn; completion cũ không chặn start mới. | AT03 |
| `TGT-FIFO-01` | 3,9.1 | Capacity/count đúng 1 hoặc 16; không underflow/overflow counter. | AT05 |
| `TGT-FIFO-02` | 9.1 | Thứ tự byte/metadata FIFO không đổi khi pointer wrap. | AT05 |
| `TGT-FIFO-03` | 9.1 | Full + valid pop + push cùng cạnh nhận cả hai, không báo OE giả. | AT05 |
| `TGT-FIFO-04` | 9.1 | Empty + pop + push không bypass: pop không hợp lệ, byte mới còn trong queue. | AT05 |
| `TGT-FIFO-05` | 9.3 | Reset/clear thắng giao dịch queue; completion tại RX flush bị bỏ không sinh OE. | AT05, AT07 |
| `TGT-FIFO-06` | 6.4,9 | Error-ack gắn đúng entry; head thay đổi không dùng lỗi/ack của head cũ. | AT04, AT05 |
| `TGT-IRQ-01` | 6.5 | IER mask quyết định event/IIR ngay sau write; IRQ active-high dạng mức. | AT06 |
| `TGT-IRQ-02` | 6.5 | Ưu tiên RLS > RDA > THRE; nguồn thấp không mất khi bị nguồn cao che. | AT06 |
| `TGT-IRQ-03` | 6.5 | RDA theo RX count ≥ threshold, không phụ thuộc TX empty. | AT06 |
| `TGT-IRQ-04` | 6.5 | THRE pending set/ack đúng edge; read IIR nguồn khác không ack nhầm. | AT06 |
| `TGT-IRQ-05` | 6.5 | Read LSR/RBR/IIR chỉ giải quyết đúng nguồn; event có thể còn cao nếu còn nguồn khác. | AT06 |
| `TGT-IRQ-06` | 6.5 | Khi không còn nguồn được enable, event=0, IIR bit0=1; không kẹt C0/00. | AT06 |
| `TGT-IRQ-07` | 6.5,9.3 | Sự kiện mới cùng cạnh acknowledge không mất; set mới thắng clear cũ. | AT06 |
| `TGT-RST-01` | 8.1 | Reset register/count/pending đúng bảng; post-release LSR=60/IIR=01. | AT01, AT07 |
| `TGT-RST-02` | 8 | Reset abort frame/transaction, không stale byte hoặc replay sau reset. | AT07 |
| `TGT-RST-03` | 8.2 | KEY0 async assert/sync deassert hai cạnh; DUT/wrapper dùng cùng reset nội bộ. | AT07, AT08 |
| `TGT-RST-04` | 8 | TX reset-high, RX synchronizer high, display/pending/LED lỗi reset đúng. | AT07, AT08 |
| `TGT-SYS-01` | 4.2,13 | Top khai báo 65 bit port và map đủ, không trùng pin. | DOC, AT08 |
| `TGT-SYS-02` | 10.1 | KEY/SW/RX đồng bộ theo contract, không dùng tín hiệu async trực tiếp điều khiển FSM. | AT08 |
| `TGT-SYS-03` | 10.1 | Debounce cả nhấn/nhả đủ 500000 mẫu; một pulse/nhấn, held-key không lặp. | AT08 |
| `TGT-SYS-04` | 10.1,10.5 | Manual byte chốt tại pulse, giữ đến THR success, SW đổi không thay byte pending. | AT08 |
| `TGT-SYS-05` | 10.2 | SW14/15 chốt trong init, no runtime parity change; SW16/17 có thời điểm hiệu lực rõ. | AT08 |
| `TGT-SYS-06` | 10.3 | Đúng 6 init write, địa chỉ/data đúng, init_done chỉ sau success; ≤32 clock. | AT08 |
| `TGT-SYS-07` | 10.4 | Poll 5000 clock và wake sớm; SW16 hold không gây IRQ busy-loop chặn TX. | AT08 |
| `TGT-SYS-08` | 10.5 | Không overwrite manual/echo slot; reject manual overflow có fault indication. | AT08 |
| `TGT-SYS-09` | 10.2,10.5 | SW16 chỉ dừng RBR mới; UART RX/TX vẫn chạy, overflow báo OE. | AT08 |
| `TGT-SYS-10` | 10.5 | Echo dùng PRDATA byte nhận; reserve slot trước pop, không mất byte do pending overwrite. | AT08 |
| `TGT-SYS-11` | 10.4,10.5 | Manual/echo công bằng khi cùng pending; RX liên tục không loại cơ hội TX. | AT08 |
| `TGT-SYS-12` | 10.6 | APB error dừng master vào FAULT; không xóa slot như thể write thành công. | AT08 |
| `TGT-SYS-13` | 10.6 | HEX/LED đúng nibble/polarity; error LED sticky độc lập với LSR clear. | AT08 |
| `TGT-SYS-14` | 4.2,10.6 | SW dự phòng không tác dụng; LEDG chưa dùng xuất 0. | AT08 |
| `TGT-SYS-15` | 10.5 | Lossless chỉ trong traffic budget; overload có expected drop/OE được báo. | AT05, AT08 |
| `TGT-FPGA-01` | 11 | Đúng chip/top/SystemVerilog/filelist; clock constraint 20 ns; không trộn baseline. | DOC, AT08 |
| `TGT-FPGA-02` | 11,13 | Gán đủ pin/I/O standard và kiểm bank/JP6 thực tế. | DOC, AT08 |
| `TGT-FPGA-03` | 12 | Đấu chéo TX/RX, GND chung, mức logic phù hợp, terminal đúng cấu hình. | AT08 |
| `TGT-FPGA-04` | 11 | Compile/fitter/STA đạt tiêu chí, review latch/CDC/unconstrained paths. | AT08 |
| `TGT-FPGA-05` | 12,14.2 | Lưu bằng chứng board TX/RX/echo/mode/error; không dùng simulation thay hardware result. | AT08 |

### 14.2. Tám nhóm nghiệm thu chức năng

Các nhóm dưới đây là tiêu chí ở mức SPEC, không thay DV Plan chi tiết. Một môi trường UVM được chạy nhiều testcase/seed; không yêu cầu tám testbench top-level riêng. Đề bài cung cấp chưa quy định con số 5–8 bắt buộc, nên việc chia tám nhóm là cách tổ chức của dự án.

**AT01 — APB/register/reset baseline.** Kiểm SETUP/ACCESS, valid read/write, DLAB, byte thấp/zero-extension, reserved bits và side effect. Read LCR tại `0x00C` phải hoạt động; truy cập `0x003`, `0x02C` hoặc offset unsupported phải lỗi và không alias. Kiểm IIR=`0x01` sau reset, `0xC1` sau FCR enable khi chưa có IRQ. PASS khi dữ liệu/readback/error đúng, mỗi transfer chỉ tác động một lần và không update ở pha không hợp lệ.

**AT02 — TX/baud/format.** Bao phủ **24 mode** = 4 data widths × 3 parity modes × 2 stop counts; mẫu `00, FF, 55, AA`, one-hot và random. Đo cả start/data/parity/stop; dùng ít nhất hai frame queued để phát hiện thiếu stop thứ hai. Kiểm D=0, 1, 27, 326 và 65535 hoặc test timing tương đương đủ chứng minh cực trị counter. PASS khi bit timing đúng 16D clock, frame đúng thứ tự/parity và không mất/nhân đôi. Watchdog phải tính theo D và độ dài traffic, không giữ cố định 5 ms cho mọi divisor.

**AT03 — RX sạch/full-duplex/tolerance.** BFM độc lập phát đủ 24 mode, nhiều byte liên tiếp và đồng thời TX. Sweep phase tại 0/5/10/15/19 ns đối với clock 20 ns, cùng tỷ lệ baud peer/DUT 0,98/1,00/1,02; thêm false-start và idle/arm cases. PASS khi RBR đúng byte đã mask N bit, số lượng/thứ tự đúng, không PE/FE/BI/OE giả trong traffic không overflow. Không chỉ dựa loopback cùng DUT để kết luận tolerance.

**AT04 — PE/FE/BI và liên kết lỗi với byte.** Gửi good/bad parity ở cả odd/even, lỗi stop thứ nhất/thứ hai, break và phục hồi. Xen kẽ byte sạch/lỗi để phát hiện metadata lệch một entry. Kiểm LSR trước/sau acknowledge, LSR[7] khi lỗi còn ở entry phía sau, và RBR pop không đổi data do đọc LSR. PASS khi lỗi đúng entry, clear đúng và không báo nhiều byte cho một break kéo dài.

**AT05 — FIFO/clear/overflow/concurrency.** Kiểm capacity 1/16, pointer wrap, count 0/1/C−1/C, full+pop+push, empty+read+arrival và clear cùng completion. Với FIFO on, gửi 17 byte không đọc: chỉ 16 byte đầu được giữ, OE=1, byte 17 bị drop; đọc/clear OE đồng thời overflow mới không được làm mất lỗi mới. Kiểm enable toggle flush, TX clear khi active và RX clear khi đang nhận. PASS khi dữ liệu/count/metadata/PSLVERR/OE đúng bảng 9.1–9.3.

**AT06 — IRQ sources/priority/clear.** Bao phủ IER masks, threshold T=1/4/8/14 và count T−1/T/T+1; với T=1, T−1 là empty. Tạo RLS/RDA/THRE riêng và đồng thời. Kiểm clear/read với nguồn mới cùng cạnh, mask tất cả, TX-empty khi RX empty, và read IIR nguồn ưu tiên cao không ack TX nhầm. PASS khi IIR mã/ưu tiên đúng, event=0 khi hết nguồn enabled, không kẹt IIR=`C0/00`.

**AT07 — Reset và thay cấu hình.** Assert reset trong idle, SETUP, ACCESS, TX/RX data/parity/stop, FIFO full và IRQ active. Kiểm abort và post-reset init mới không còn dữ liệu/flags cũ. Đổi config giữa frame để kiểm snapshot cũ, frame sau dùng config mới; tránh coi hai write DLL/DLM là atomic. PASS khi không phát lại byte cũ, reset values đúng, không glitch do cấu hình làm thay một frame đang chạy.

**AT08 — Wrapper và FPGA.** Chạy simulation wrapper với ba mode board N/O/E, bounce ngắn/giữ nút/nhả-nhấn, SW data capture, sáu init write, poll/IRQ, echo, hold-RX, tranh chấp manual/echo và fault. Fault APB có thể dùng stub/fault injection ở giao diện slave của test wrapper; phải gắn nhãn phép thử đó, không coi là phản hồi tự nhiên của DUT đúng. Kiểm HEX/LED polarity và sticky latch. Sau đó chạy Quartus/STA và trên board: gửi tay, nhận PC, echo một burst trong budget, parity mismatch có kiểm soát, hold-RX gây OE, FE/break với nguồn stimulus tạo được lỗi tương ứng. Log test phải chỉ rõ subcase SIM hay BOARD; chưa làm BOARD thì AT08 chưa hoàn tất phần phần cứng.

### 14.3. Oracle, coverage và điều kiện PASS

- Oracle register/FIFO/IRQ phải viết theo SPEC, lấy APB completion và serial stimulus/observations làm đầu vào. Internal state dùng để debug, không thay expected bằng dữ liệu DUT tự xuất.
- TX monitor độc lập đo cạnh/bit time và giải mã serial. RX oracle biết byte/mode/error đã phát; kiểm LSR và RBR theo đúng read side effect.
- Mỗi testcase cần ID requirement, revision DUT/TB, tool/version, seed nếu có, command, expected/observed, log, waveform cần thiết và verdict. Source hash phải ổn định trong một run.
- Functional coverage bắt buộc: 24 TX mode và 24 RX mode; APB direction × mapped register × DLAB với các tổ hợp hợp lệ; FIFO occupancy/boundary × push/pop/clear; IRQ source × mask × priority/clear; reset tại các trạng thái chính; các mode/chức năng wrapper. Bin bất khả thi phải có lý do, không âm thầm xóa. Những nhóm này cần đóng hết bin bắt buộc; không dùng một tỷ lệ tổng hợp để che nhóm thiếu.
- Constrained-random phải có seed tái lập và scoreboard; tối thiểu ba seed khác nhau sau directed cases. Số seed không thay thế coverage closure.
- Normal suite chỉ PASS khi không có unexplained error/fatal, checker đã hoạt động và hoàn thành traffic dự kiến. Kiểm một negative control để xác nhận checker bắt được lỗi có chủ đích.
- Với TARGET-v1.0, parity/IRQ/overflow là chức năng phải đạt. Không tiếp tục dùng nhãn EXPECTED_FAIL của baseline để cho bản sửa qua nghiệm thu. Khi còn lỗi, phải giữ verdict FAIL và issue liên quan.

## 15. Bằng chứng đã có và trạng thái thực hiện

### 15.1. Những gì đã thực sự được kiểm tra

| Hạng mục | Revision/phạm vi | Kết quả có bằng chứng |
|---|---|---|
| Năm RTL và LICENSE/filelist | S03 so với bản lưu S04 | Nội dung trùng upstream |
| Markdown hướng dẫn | Attachment so với `reference/Huongdan_UART.md` | Nội dung trùng |
| UVM source nguyên trạng | S04 | Compile lỗi: 15 backtick `sformatf`, 1 backtick `fatal` |
| UVM sau chỉ sửa cú pháp trên bản sao | BASE-PULP; Verilator 5.055 devel; UVM 2020.3.1; seed 17 | 8 normal testcase PASS, 2 known-gap testcase báo đúng lỗi; chưa coverage closure |
| Baud baseline | BASE-PULP 50 MHz, divisor 27/432/433/434 | D=433 có data bit 8,68 µs; start 8,70 µs; D=27 không phải 115200 |
| Lỗi/giới hạn baseline | BASE-PULP | Tái hiện PE/FE không báo, OE không báo, RX IRQ sai nguồn, IRQ không hạ sau clear/mask, byte thứ 17 giữ chờ |
| Pin map trong hướng dẫn | 52 bit dùng chính so S05 | 52/52 khớp; không phải thử điện áp trên board |
| Bảng pin đầy đủ của SPEC này | 65 bit port so S05 | Kiểm mapping/unique pin ở mức tài liệu |

Tên normal tests đã chạy: `apb_reg_smoke_test`, `apb_reg_alias_test`, `uart_tx_8n1_test`, `uart_rx_8n1_test`, `uart_rx_fifo_order_test`, `uart_rx_fifo_clear_test`, `uart_tx_mode_matrix_test`, `apb_random_regs_test`. Baseline TX matrix mới chạy none/even với 1/2 stop, không phải 24 mode none/odd/even của target.

UVM library của lần review: `verilator/uvm` commit `656f20d087370a7c742e00188d20bbf30fa95339`, `UVM_NO_DPI`; simulator `Verilator 5.055 devel rev v5.054-129-g14bd81f66 (mod)`. Không có kết quả Questa từ lần review. Các phép kiểm độc lập của S08 có VCD/log riêng; không chuyển tên chúng thành kết quả TARGET-v1.0.

### 15.2. Snapshot trạng thái khi phát hành SPEC, trước bước triển khai

| Deliverable | Trạng thái khi phát hành SPEC |
|---|---|
| Hợp đồng SPEC TARGET-v1.0 | Đã định nghĩa trong tài liệu này; kiểm nhất quán ở mức tài liệu/model |
| RTL sửa theo TARGET-v1.0 | NOT_IMPLEMENTED |
| UVM/RAL/checker cập nhật theo TARGET-v1.0 | NOT_IMPLEMENTED |
| Regression/functional coverage TARGET-v1.0 | NOT_RUN |
| Wrapper TARGET-v1.0 | NOT_IMPLEMENTED |
| Quartus synthesis/fitter/STA | NOT_RUN |
| Thử DE2-115 + CP2102 | NOT_RUN |

Trạng thái ở bảng trên là snapshot lịch sử; [DV results](dv/RESULTS.md) ghi trạng thái thực thi mới nhất. Một SPEC có thể hoàn chỉnh về hợp đồng trước khi RTL được viết. Hoàn thành nội dung Yêu cầu 1 không đồng nghĩa Yêu cầu 2/3 đã đạt. Việc tài liệu phù hợp rubric cuối cùng cần đối chiếu với đề bài chính thức; không có dữ kiện về rubric ngoài ảnh và Markdown đã cung cấp.

## 16. Chuyển từ SPEC v0.3/baseline sang TARGET-v1.0

### 16.1. Những thay đổi phải được phản ánh trong RTL và DV Plan

| Mục lịch sử | Baseline/nhận xét trước đây | Contract mục tiêu và công việc sau SPEC |
|---|---|---|
| DIF-01 | Byte offsets 0/1/2/3/5, alias qua bit cao | Word offsets 0/4/8/C/14, decode đủ, cập nhật master/sequence/scoreboard |
| DIF-02 | Direct divider; D=433 gần 115200 | 16× clock-enable; D=27; sửa TX/RX counters và timing checker |
| DIF-03 | Không chọn odd/even thật | EPS hoạt động cả TX/RX, kiểm 24 frame modes |
| DIF-04 | Không báo framing | Kiểm từng stop, FE gắn đúng entry |
| DIF-05 | Không OE, giữ thêm frame chờ | Drop-new khi full + OE sticky; không hidden pending RX |
| DIF-06 | FCR[0] không enable | FCR enable thực sự chọn cap1/16; sửa testcase clear `02` thành giá trị giữ enable |
| DIF-07 | RDA nối TX-empty | RDA theo RX occupancy/threshold |
| DIF-08 | Error-clear cố định, SAVE_DATA trước parity | Hoàn tất kiểm frame trước enqueue data+metadata |
| DIF-09 | Register subset | Giữ subset công khai; reserved/unmapped có phản hồi APB xác định |
| DIF-10 | Wrapper chưa có | Implement theo mục 10–13 |
| DIF-11 | Trigger so sánh bằng | Trigger bằng hoặc lớn hơn ngưỡng |
| DIF-12 | Đồng bộ bên ngoài/trong DUT | Quy định cụ thể 2FF wrapper + 3FF DUT và sampling sau chuỗi |
| DIF-13 | Pin chưa đối chiếu | Bảng 65 bit đã đối chiếu S05; vẫn cần pin planner/JP6 thực tế |
| DIF-14 | Read side effects chưa đủ | Contract LSR ack/head/OE, IIR ack và RBR pop có ưu tiên rõ |
| DIF-15 | Baseline IIR read C1 sau reset | Target reset FIFO off → IIR01; enable FIFO/no IRQ → C1 |
| Lỗi IRQ-clear được review thêm | IIR có thể C0 và IRQ kẹt | Tính mã theo nguồn pending, no IRQ bit0=1 |
| Lỗi DLM trong SPEC v0.3 | D=433 nhưng có câu DLM thường 0 | Ghi lại đúng lịch sử B1/01; target D=27 lại dùng 1B/00 theo cơ chế mới |

Đây là danh sách thay đổi contract, **chưa phải danh sách bug đã sửa xong**. Bộ 8 normal tests cũ cần migrate địa chỉ, divisor, IIR reset và FCR clear trước khi chạy với target; chạy nguyên rồi fail không mặc nhiên chứng minh target sai.

### 16.2. Bảng truy vết ID cũ → ID mục tiêu


| ID SPEC v0.3 | ID TARGET-v1.0 | Quan hệ |
|---|---|---|
| `REQ_APB_001` | `TGT-APB-01` | Giữ nguyên ý nghĩa giao thức |
| `REQ_APB_002` | `TGT-APB-02` | Giữ gating, làm rõ completion |
| `REQ_APB_003` | `TGT-APB-03` | Giữ đọc hợp lệ/zero |
| `REQ_APB_004` | `TGT-APB-05`, `TGT-APB-06` | Thay đổi: có PSLVERR cho lỗi |
| `REQ_APB_005` | `TGT-APB-04` | Thay đổi: không alias, word-aligned |
| `REQ_REG_001` | `TGT-APB-04`, `TGT-REG-01` | Thay register offsets |
| `REQ_REG_002` | `TGT-REG-01` | Giữ phân bank DLAB |
| `REQ_REG_003` | `TGT-APB-03`, `TGT-REG-02` | Giữ byte thấp, thêm mask |
| `REQ_REG_004` | `TGT-RST-01` | Thay IIR reset theo FIFO-off |
| `REQ_REG_005` | `TGT-APB-06` | Thay unsupported từ no-error sang error |
| `REQ_TX_001` | `TGT-TX-01`, `TGT-APB-08` | Thêm handling THR full/D0 |
| `REQ_TX_002` | `TGT-TX-01`, `TGT-TX-05` | Giữ frame, chốt back-to-back |
| `REQ_TX_003` | `TGT-TX-02` | Giữ 5..8 bit |
| `REQ_TX_004` | `TGT-TX-03`, `TGT-TX-04` | Thêm odd parity |
| `REQ_TX_005` | `TGT-BAUD-01`, `TGT-BAUD-03`, `TGT-BAUD-05` | Thay cơ chế divisor sang 16× |
| `REQ_RX_001` | `TGT-RX-03`, `TGT-RX-10` | Giữ chức năng, thêm continuous/tolerance |
| `REQ_RX_002` | `TGT-APB-07`, `TGT-FIFO-02` | Giữ pop đúng một byte |
| `REQ_RX_003` | `TGT-REG-08` | Giữ DR |
| `REQ_RX_004` | `TGT-RX-04`, `TGT-RX-07` | Guide-gap chuyển thành phải PASS |
| `REQ_RX_005` | `TGT-RX-05`, `TGT-RX-06`, `TGT-RX-08` | FE/OE/BI thành yêu cầu bắt buộc |
| `REQ_FIFO_001` | `TGT-FIFO-01`, `TGT-FIFO-05` | Thêm enable cap1/16 và clear |
| `REQ_FIFO_002` | `TGT-FIFO-02`, `TGT-FIFO-03`, `TGT-FIFO-04` | Chốt order/full/concurrency |
| `REQ_FIFO_003` | `TGT-REG-07`, `TGT-IRQ-03` | Thay == thành >= |
| `REQ_INT_001` | `TGT-IRQ-01`, `TGT-IRQ-02`, `TGT-IRQ-04`, `TGT-IRQ-05` | Chốt source/priority/ack |
| `REQ_INT_002` | `TGT-IRQ-03`, `TGT-IRQ-06` | Guide-gap chuyển thành phải PASS |
| `REQ_SYS_001` | `TGT-RST-03`, `TGT-FPGA-01` | Clock/reset/constraints |
| `REQ_SYS_002` | `TGT-SYS-02`, `TGT-SYS-03` | Debounce và CDC rõ cycle |
| `REQ_SYS_003` | `TGT-SYS-06` | Sáu init write của target |
| `REQ_SYS_004` | `TGT-SYS-07`, `TGT-SYS-11` | Poll và fairness |
| `REQ_SYS_005` | `TGT-SYS-04`, `TGT-SYS-08` | Send latch/pending |
| `REQ_SYS_006` | `TGT-SYS-09`, `TGT-RX-08` | Hold-RX phải có OE thật |
| `REQ_SYS_007` | `TGT-SYS-10` | Echo có backpressure slot |
| `REQ_SYS_008` | `TGT-RX-01`, `TGT-SYS-02` | CDC RX |
| `REQ_SYS_009` | `TGT-SYS-13`, `TGT-SYS-14` | Thêm error LED sticky/fault |
| `REQ_SYS_010` | `TGT-APB-04`, `TGT-SYS-06` | Thay offsets để bám guide trên RTL sửa |
| `REQ_SYS_011` | `TGT-BAUD-03`, `TGT-SYS-05`, `TGT-TX-03` | 16× baud và odd/even hoạt động |

## 17. Điều kiện hoàn thành SPEC và bàn giao

### 17.1. Nội dung Yêu cầu 1 được cung cấp

| Thành phần SPEC | Vị trí |
|---|---|
| Mục tiêu/phạm vi/nguồn chuẩn/revision | 1–3 |
| Sơ đồ hệ thống và phân định DUT/wrapper/UVM | 2 |
| Port/width/direction/clock/reset | 3–4, 8 |
| APB phases, sampling, errors, address map | 5–6 |
| Register fields/reset/read/write/side effects | 6, 8–9 |
| Baud, TX/RX, parity/stop/break/tolerance | 7 |
| FIFO boundaries, overflow, simultaneous events | 9 |
| IRQ source/priority/clear/mask/reassert | 6.5, 9.3 |
| FSM init/poll/send/receive/echo/hold/fault | 10 |
| Pin map, I/O voltage, CP2102, Quartus/STA/CDC | 11–13 |
| Yêu cầu định danh và acceptance criteria | 14 |
| Bằng chứng hiện có/giới hạn và migration | 15–16 |

Tài liệu này khóa **80 yêu cầu TGT**, 36 liên kết từ ID cũ, tám nhóm nghiệm thu và 65 bit port có pin assignment. Các hành vi quan trọng đã có expected và giới hạn rõ; không còn mục TBD về địa chỉ, baud, parity, reset, FIFO, interrupt, mode switch hoặc echo.

### 17.2. Những việc còn thuộc Yêu cầu 2/3

Phải triển khai và review RTL mục tiêu, cập nhật UVM theo contract mới, chạy regression/coverage, xây wrapper/Quartus và thử board. Source/version/tool/project của người hướng dẫn đã chạy trên board chưa được cung cấp; SPEC này mô tả **thiết kế mục tiêu mới đã chọn**, không tự nhận tái tạo chính xác project chưa nhìn thấy đó.

Những điều kiện vật lý cần xác minh khi triển khai: đúng board/chip, JP6 ở mức điện áp phù hợp, CP2102 logic level, clock thực tế, pin planner và timing constraints. Các điều kiện này không làm thay đổi số liệu đã khóa trong SPEC; nếu phần cứng thực tế khác giả định, phải phát hành revision điều chỉnh và cập nhật các yêu cầu bị ảnh hưởng.

### 17.3. Quản lý thay đổi và bằng chứng

Mỗi sửa contract phải ghi lý do, ID yêu cầu bị ảnh hưởng, thay đổi RTL/TB cần thiết và kết quả chạy lại. Thay register address, divisor semantics, FIFO policy hoặc pinout cần tăng version tài liệu; sửa lỗi chính tả không được âm thầm làm đổi expected. Không ghi đè bằng chứng baseline hoặc đổi nhãn NOT_RUN thành PASS chỉ vì đã viết source.

Bản Markdown này tự chứa pin map, register map và acceptance contract; các file CSV/JSON đi kèm nếu có chỉ hỗ trợ sử dụng máy, không phải điều kiện bắt buộc để hiểu SPEC. Hoàn tất kiểm tra tài liệu/model chỉ chứng minh tính nhất quán đã kiểm tra, không phải formal proof, UVM coverage closure hoặc FPGA sign-off.
