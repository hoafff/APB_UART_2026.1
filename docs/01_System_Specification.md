# Đặc tả hệ thống và IP APB UART — nhánh `main2`

Hệ thống dùng IP `apb_uart_sv` nguyên bản của PULP, nhánh `pulpinov1` tại commit `dfad6e04d19cc9481d3cd2750b45b970dc61271b`. Master truy cập thanh ghi theo **offset byte**. Trên DE2-115, clock 50 MHz và divisor `0x01B1` cho tốc độ danh định 115200 baud. Wrapper hỗ trợ 8N1 và 8E1, dùng LSR để quyết định khi nào đọc hoặc ghi dữ liệu.

Đây là hợp đồng cho driver, DV và tích hợp FPGA của `main2`. Năm tệp SystemVerilog trong filelist xác định IP. Các yêu cầu `SYS` và `BOARD` áp dụng cho phần tích hợp bên ngoài IP. Hướng dẫn gốc và bản `TARGET-v1.0` trong lịch sử chỉ dùng để đối chiếu. [Filelist PULP](../rtl/vendor/pulp_apb_uart_sv/src_files.yml) · [SHA-256 của nguồn](spec/baseline_hashes.json) · [Hướng dẫn gốc](../reference/Huongdan_UART.md) · [Sai khác giữa hướng dẫn và RTL](00_RTL_Guide_Discrepancies.md)

Mỗi ID dưới đây có điều kiện kích thích và quan sát mong đợi. Với mục ghi **giới hạn** hoặc **lỗi**, tái hiện được triệu chứng chỉ xác nhận đặc điểm của revision này. Kế hoạch giữ ánh xạ ID → testcase, sổ kết quả giữ log, cấu hình và phạm vi thực sự đã chạy. [Chỉ mục ID](spec/requirements.json) · [Kế hoạch DV](03_DV_Plan.md) · [Kết quả DV](DV_RESULTS.md) · [Build Windows và nghiệm thu FPGA](05_FPGA_Windows.md)

## 1. Biên IP và giao dịch APB

| Cổng của `apb_uart_sv` | Chiều | Ý nghĩa tại giao diện |
|---|---|---|
| `CLK`, `RSTN` | Vào | Một miền clock, cập nhật ở cạnh lên. Reset tích cực thấp, tác động bất đồng bộ và ưu tiên trước cập nhật giao dịch. |
| `PADDR[11:0]`, `PSEL`, `PENABLE`, `PWRITE` | Vào | Độ rộng mặc định `APB_ADDR_WIDTH=12`. Master ngoài IP chọn slave bằng `PSEL`. `PWRITE=1` là ghi. |
| `PWDATA[31:0]` / `PRDATA[31:0]` | Vào / ra | Dữ liệu ghi / đọc. Chỉ byte thấp hữu hiệu, không có `PSTRB`. |
| `PREADY`, `PSLVERR` | Ra | Luôn lần lượt bằng 1 và 0. |
| `rx_i` / `tx_o` | Vào / ra | Hai đường nối tiếp độc lập, mức nghỉ 1. TX và RX đều được bật cố định bên trong IP. |
| `event_o` | Ra | Mức ngắt từ bit 0 của mã IIR đã chốt. Hành vi sau ngắt xem mục 6. |

| ID | Yêu cầu | Tiêu chí chấp nhận |
|---|---|---|
| <a id="apb-01"></a>`APB-01` | Pha và cạnh hoàn tất | Master phát SETUP (`PSEL=1, PENABLE=0`), kế tiếp ACCESS (`PSEL=1, PENABLE=1`), giữ địa chỉ, chiều và dữ liệu ghi. Khi `RSTN=1`, chỉ cạnh lên ở ACCESS mới tạo tác dụng giao dịch. Hai lệnh liên tiếp vẫn có SETUP riêng. Giữ ACCESS trái giao thức qua hai cạnh có thể ghi/pop hai lần. |
| <a id="apb-02"></a>`APB-02` | Phản hồi và độ rộng dữ liệu | Quan sát `PREADY=1, PSLVERR=0` cả khi truy cập ô bỏ trống hoặc THR đầy. `PRDATA=0` ngoài READ ACCESS. Khi đọc, `PRDATA[31:8]=0`. Đổi `PWDATA[31:8]` và giữ byte thấp phải cho cùng hiệu ứng ghi. |
| <a id="apb-03"></a>`APB-03` | Địa chỉ byte và alias | Trong mọi giao dịch có `PSEL`, chỉ `PADDR[2:0]` chọn ô. Cứ 8 byte lặp lại toàn bộ bản đồ. Ghi `0x00B` rồi đọc `0x003` phải thấy cùng LCR. `0x00C` và `0x014` cùng chọn ô 4 bỏ trống. `0x008` chọn ô 0 và có đầy đủ tác dụng theo chiều và DLAB. |

Nguồn giải mã, chốt trạng thái và phản hồi bus nằm trong [apb_uart_sv.sv](../rtl/vendor/pulp_apb_uart_sv/apb_uart_sv.sv).

## 2. Thanh ghi, reset và tác dụng đọc

`DLAB = LCR[7]`. Các offset dưới đây tính từ địa chỉ cơ sở có ba bit thấp bằng 0. Bảng dùng tham số mặc định của IP.

| Offset | Đọc khi DLAB=0 | Ghi khi DLAB=0 | Đọc / ghi khi DLAB=1 |
|---|---|---|---|
| `0x0` | RBR, byte đầu RX FIFO | THR, yêu cầu thêm byte vào TX FIFO | DLL, byte thấp divisor, R/W |
| `0x1` | IER | IER, lưu đủ 8 bit | DLM, byte cao divisor, R/W |
| `0x2` | IIR, mã ngắt hiện hành | FCR, lệnh clear và chọn ngưỡng | Cũng đọc IIR / ghi FCR |
| `0x3` | LCR | LCR, lưu đủ 8 bit | Cũng đọc / ghi LCR |
| `0x4` | `0` | Bỏ qua | Như DLAB=0 |
| `0x5` | LSR, trạng thái đã chốt | Bỏ qua | Như DLAB=0 |
| `0x6`, `0x7` | `0` | Bỏ qua | Như DLAB=0 |

Tên MCR, MSR và SCR có trong khai báo ở các ô 4, 6 và 7. Decoder không thực thi các thanh ghi này. IP không cung cấp modem control/status, scratch register hay điều khiển luồng RTS/CTS.

| ID | Yêu cầu | Tiêu chí chấp nhận |
|---|---|---|
| <a id="reg-01"></a>`REG-01` | Bản đồ và hai bank DLAB | Ghi IER, mở DLAB và ghi/đọc hai byte khác nhau tại 0/1, đóng DLAB và đọc lại IER ban đầu. Một byte RX đang chờ phải còn nguyên qua lần đọc DLL. Ghi DLL không tạo khung TX. Kiểm tra cả hai chiều của các ô 2–7 theo bảng. |
| <a id="reg-02"></a>`REG-02` | Reset và hủy công việc đang dở | Hạ `RSTN` giữa khung và khi còn dữ liệu chờ. TX trở về 1, hai FIFO rỗng, TX/RX về IDLE, đường đồng bộ RX về `111`, `event_o=0`. Sau nhả reset với bus nghỉ và `rx_i=1`, đọc các bank tương ứng để kiểm `LCR=IER=DLL=DLM=0`, `LSR=0x60` và `IIR=0xC1`. Ngưỡng về 1, hai lệnh clear về 0. Master hủy SETUP/ACCESS cũ, cấu hình lại rồi gửi/nhận byte mới, không phát lại dữ liệu trước reset. |
| <a id="reg-03"></a>`REG-03` | Bit cấu hình và phạm vi readback | `LCR[1:0]=00/01/10/11` chọn 5/6/7/8 bit, `[2]` chọn stop TX, `[3]` bật parity chẵn, `[7]` chọn bank. `[4]` không chọn odd/even, `[5]` không tạo stick parity, `[6]` không ép TX xuống thấp để phát break. Ghi rồi đọc lại các bit này, so khung thực với cùng dữ liệu. IER lưu cả byte, chỉ `[2:0]` đi tới bộ ngắt. |
| <a id="reg-04"></a>`REG-04` | DR, THRE và TEMT | Tại mỗi cạnh lên, `LSR[0]` lấy `RX_count≠0`, `[5]` lấy `TX_count=0`, `[6]` lấy `TX_count=0` và TX đang IDLE, đều từ trạng thái **trước cạnh**. So DR quanh cạnh push/pop cuối. Sau khi TX lấy byte cuối, phải thấy `LSR[6:5]=01` (THRE=1, TEMT=0), rồi `11` sau khi phát xong. |
| <a id="reg-05"></a>`REG-05` | Dữ liệu đọc và acknowledge | Lấy `PRDATA` tại cạnh hoàn tất **trước** cập nhật FIFO/IIR. Đọc RBR với DLAB=0 lấy đầu cũ, chỉ pop khi FIFO có dữ liệu và luôn phát mask `1000` kể cả khi rỗng. Đọc LSR giữ FIFO, phát `1100`. Đọc IIR phát `0100` với mọi mã trả về. Đọc DLL/DLM/LCR/IER không phát các mask này. Thử hai byte khác nhau và các lần đọc xen kẽ để phân biệt. |

LSR là ảnh chụp theo clock. Chẳng hạn, push vào RX rỗng ở cạnh `k` làm DR được chốt ở cạnh `k+1`. Đọc RBR khi rỗng trả byte từ ô nhớ tại con trỏ hiện tại. Byte đó có thể là dữ liệu cũ, không có giá trị nhận mới. Reset phần cứng xóa bộ nhớ FIFO. FCR chỉ đặt lại trạng thái hàng đợi. Đường đọc IIR ghép `0xC0` với mã từ `uart_interrupt`. Ô `regs_q[IIR]` reset bằng `0x01` không cấp dữ liệu cho APB. Nếu master giữ ACCESS qua lúc nhả reset, IP có thể thực hiện nó ngay tại cạnh lên đầu tiên có `RSTN=1`.

## 3. Baud và định dạng phát

Đặt `D = 256 × DLM + DLL` (16 bit), `P = D + 1` tính bằng số nguyên đủ rộng. Cả hai máy trạng thái đọc trực tiếp cấu hình hiện hành. Hai lần ghi DLL và DLM có hiệu lực riêng. Nếu giảm D xuống dưới số đếm đang chạy, phép so bằng có thể phải đợi bộ đếm 16 bit quay vòng. Để truyền theo định dạng xác định, chờ TX hoàn tất, giữ đầu gửi ngoài ở idle và chỉ bắt đầu khung mới sau khi cấu hình xong. Không có thao tác chốt toàn bộ cấu hình tại đầu mỗi khung.

| ID | Yêu cầu | Tiêu chí chấp nhận |
|---|---|---|
| <a id="baud-01"></a>`BAUD-01` | Chu kỳ bit TX | Với D cố định, bộ đếm chạy từ 0 đến D kể cả hai đầu. `bit_done` qua một thanh ghi. Từ IDLE, start TX dài `P+1` clock, mỗi bit data, parity và mỗi stop dài `P` clock. Đo trên `tx_o` với mẫu đổi mức. `D=0` vẫn cho TX tiến (start 2 clock, data 1 clock), `D=65535` cho data 65536 clock. Không có hệ số chia 16. |
| <a id="baud-02"></a>`BAUD-02` | Điểm làm việc 50 MHz / 115200 | Ghi `DLL=0xB1, DLM=0x01`, gửi `0x55` ở 8N1. Từ cạnh xuống start đến cạnh lên bit 0 là 435 clock (8,700 µs). Các cạnh data cách nhau 434 clock (8,680 µs), tương ứng `50 000 000 / 434 ≈ 115 207,37` baud (+0,0064%). Với `D=27`, data chỉ dài 28 clock (0,560 µs). |
| <a id="baud-03"></a>`BAUD-03` | Pha lấy mẫu RX | RX dịch `rx_i` qua ba FF, nhận cạnh xuống khi `reg_rx_sync[2]=1, reg_rx_sync[1]=0`. Trong cửa sổ start, so bộ đếm với `D >> 1`, tương ứng `floor(D/2)+1` clock đếm từ 0. Các nhịp data so với D, mẫu lấy từ `reg_rx_sync[2]` bằng `bit_done` đã chốt. Đối chiếu ở D chẵn và lẻ, chẳng hạn 432/433, với khung từ nguồn nối tiếp độc lập. Độ trễ đồng bộ và nhịp FSM phải được tính riêng khi quy về chân `rx_i`. Giá trị đếm ở D rất nhỏ không bảo đảm RX bắt được mọi khung ở tốc độ đó. |

| ID | Yêu cầu | Tiêu chí chấp nhận |
|---|---|---|
| <a id="tx-01"></a>`TX-01` | Đường THR → FIFO → TX | Với DLAB=0 và FIFO còn chỗ, mỗi lần ghi THR tạo một byte chờ. Từ IDLE, TX lấy đầu FIFO vào thanh ghi dịch. Ghi liên tiếp `0x41, 0xA6` ở 8N1, đối chiếu đúng hai khung theo thứ tự trên `tx_o`, kể cả khi RX đang nhận. |
| <a id="tx-02"></a>`TX-02` | Bit dữ liệu và parity | Dây nghỉ 1, một start=0, tiếp theo n bit thấp của byte theo thứ tự bit 0 trước, thêm một bit parity nếu bật, cuối cùng là stop=1. Ở chế độ E, parity là XOR của đúng n bit đã phát. So đủ 16 tổ hợp của n=5/6/7/8, parity N (tắt) hoặc E (chẵn), và một/hai stop. Ví dụ `LCR=0x0B` và `0x1B` đều cho 8E1. |
| <a id="tx-03"></a>`TX-03` | Số stop trên hai khung kề nhau | `LCR[2]=0/1` cho 1/2 stop **nguyên bit**, cả khi dữ liệu dài 5 bit. Xếp sẵn byte kế, giữ cấu hình và đo khoảng cách giữa hai cạnh xuống start. Với n bit data, p=0/1 parity và s=1/2 stop, khoảng cách bằng `(1+n+p+s)×P+2` clock (thêm 1 ở start và 1 ở IDLE giữa hai khung). Tại D=433, 8N1 cho 4342 clock, 8N2 cho 4776. |

Nguồn bộ đếm, đường dịch và trạng thái stop nằm trong [uart_tx.sv](../rtl/vendor/pulp_apb_uart_sv/uart_tx.sv) và [uart_rx.sv](../rtl/vendor/pulp_apb_uart_sv/uart_rx.sv).

## 4. Nhận dữ liệu và giới hạn báo lỗi

| ID | Yêu cầu | Tiêu chí chấp nhận |
|---|---|---|
| <a id="rx-01"></a>`RX-01` | Khung sạch tới RBR | Lái `rx_i` từ một bộ phát độc lập với clock bit phù hợp, ở 5–8 bit, N/E. Khi còn chỗ, RX đưa dữ liệu vào FIFO tại `SAVE_DATA` ngay sau data cuối, trước xử lý parity/stop. Truyền bit 0 trước. RBR trả đúng giá trị phần dữ liệu, các bit cao ngoài độ dài bằng 0. Dùng mẫu bất đối xứng, burst và TX/RX đồng thời để so số byte lẫn thứ tự. |
| <a id="rx-02"></a>`RX-02` | Giới hạn xác nhận start, stop và break | Cạnh xuống ở IDLE đủ để RX bắt đầu. FSM không kiểm lại mức thấp ở giữa start, chỉ đợi một nhịp stop và không lấy mẫu để kiểm mức stop. `LCR[2]` không nối tới RX. Ở 8N1, D=433, RX đang rảnh và FIFO còn chỗ, kéo thấp 4 clock rồi giữ mức 1 quá một khung. RBR nhận `0xFF`. Ở ca riêng, kéo thấp từ idle quá một khung tạo byte `0x00`, BI vẫn bằng 0. Không có chức năng phát hiện break hay kiểm stop thứ hai. |
| <a id="rx-03"></a>`RX-03` | Lỗi PE và các cờ thiếu | RX có so parity chẵn nhưng `err_clr_i=1` cố định và ưu tiên clear, nên sau reset `err_o=0`. FIFO đã nhận `{err_o,data}` trước phép so parity. `LSR[2]` lấy bit 8 của ô đầu FIFO và không báo PE. `LSR[1]/[3]/[4]/[7]` lần lượt không báo overrun, framing error, break hay tổng lỗi FIFO. Chèn parity sai, stop thấp, đường thấp kéo dài và burst khi đầy. Quan sát RBR cùng LSR trên từng ca, kể cả dữ liệu đã nhận sai chuẩn mà không có cờ. |

RX cần một cạnh xuống mới khi đã về IDLE để bắt đầu khung tiếp theo. IP dùng một mẫu cho mỗi bit data. Hợp đồng không ấn định tỷ lệ lệch baud tối đa giữa hai đầu. [Máy thu và đường báo lỗi](../rtl/vendor/pulp_apb_uart_sv/uart_rx.sv) · [Kết nối tại top IP](../rtl/vendor/pulp_apb_uart_sv/apb_uart_sv.sv)

## 5. FIFO và lệnh FCR

Mặc định TX FIFO có 16 mục × 8 bit, RX FIFO có 16 mục × 9 bit gồm byte dữ liệu và bit parity-error. Hai FIFO luôn hoạt động. Tại cạnh lên khi không reset/clear, `push = valid_i && count < 16`, `pop = ready_i && count > 0`, tính theo **count trước cạnh**. Khi có cả yêu cầu vào và ra, kết quả như sau.

| Count trước cạnh | Tác dụng | Count sau cạnh |
|---|---|---|
| 0 | Chỉ nhận phần tử mới. Đầu ra chưa có phần tử hợp lệ tại cạnh đó. | 1 |
| 1…15 | Trả đầu cũ, ghi phần tử mới xuống cuối. | Như trước |
| 16 | Chỉ lấy đầu cũ. Phần tử mới chưa được nhận trong cạnh này. | 15 |

| ID | Yêu cầu | Tiêu chí chấp nhận |
|---|---|---|
| <a id="fifo-01"></a>`FIFO-01` | Dung lượng và thứ tự | Lấp đầy, rút bớt, nạp lại qua một vòng con trỏ rồi rút hết. So từng byte với hàng đợi độc lập, đủ 16 vị trí ở mỗi FIFO. Tách byte đang ở thanh ghi dịch TX hoặc đang chờ trong máy thu khỏi số phần tử FIFO. |
| <a id="fifo-02"></a>`FIFO-02` | Push/pop ở biên | Thử ba hàng của bảng trên. Tại RX rỗng, RBR đọc đồng thời với byte đến không tiêu thụ byte mới. Tại TX đầy, ghi THR bị mất dù TX lấy đầu FIFO cùng cạnh. APB vẫn hoàn tất, không báo lỗi và không tự ghi lại. So chuỗi đầu ra để phát hiện mất byte cũ, nhân đôi hoặc nhận nhầm byte mới. |
| <a id="fifo-03"></a>`FIFO-03` | Clear và các bit FCR | Mọi lần ghi FCR cập nhật ngưỡng `[7:6]`. `[1]` yêu cầu clear RX, `[2]` clear TX. `[0]` và `[5:3]` bị bỏ qua. Một lần WRITE ACCESS ở cạnh k chốt xung clear tự hạ. FIFO đặt count và hai con trỏ về 0 tại cạnh k+1, ưu tiên trước cập nhật count do push/pop. Bộ nhớ không được xóa bởi FCR. Kiểm hai FIFO độc lập và `0x06/0x07` tương đương. Khung TX đã nạp vẫn phát tiếp, RX đang nhận vẫn có thể đưa byte vào sau clear. |
| <a id="fifo-04"></a>`FIFO-04` | RX đầy và byte đang chờ | Khi FIFO chứa 16 mục, RX giữ byte kế ở `SAVE_DATA` với valid=1. Một lần đọc RBR ở trạng thái đầy chỉ mở chỗ cho cạnh sau. Trong khi chờ, máy thu bỏ lỡ các start tiếp theo. Phát `0x40…0x51` ở 8N1 với chu kỳ bit khớp divisor, thêm một bit nghỉ sau mỗi khung, không đọc đến hết burst. Khi rút phải thấy `0x40…0x50` theo thứ tự, OE=0. Đây là một tình huống định thời cụ thể, dung lượng FIFO vẫn là 16. |

Clear không che tín hiệu ready/valid tổ hợp. Nếu TX đang IDLE và thấy đầu FIFO hợp lệ ở cạnh clear, nó vẫn có thể nạp đầu cũ. Ở RX, nếu FIFO đầy thì byte đang chờ có thể vào ở cạnh sau clear. Nếu FIFO còn chỗ và RX đang có valid ngay cạnh clear, máy thu thấy ready và rời `SAVE_DATA`. Mạch nhớ vẫn có thể ghi ô đó nhưng count về 0, nên byte ấy không còn là phần tử hợp lệ. [Con trỏ, bộ nhớ và count](../rtl/vendor/pulp_apb_uart_sv/io_generic_fifo.sv) · [Đường clear FCR](../rtl/vendor/pulp_apb_uart_sv/apb_uart_sv.sv)

## 6. IER, IIR và ngắt

`IIR[7:4]=1100` cố định với mọi giá trị FCR. `IIR[3:0]=q` là **một mã** đã chốt. Khi đọc IIR, master nhận `0xC0 + q`. `event_o = ~q[0]`. Mỗi cạnh, bộ ngắt lấy `q` cũ, xóa các bit được chỉ định bởi mask đọc ở `REG-05`, sau đó nguồn đang đủ điều kiện có thể ghi đè **toàn bộ mã**, theo thứ tự dưới đây.

| Ưu tiên | Điều kiện thực hiện trong top IP | Mã đọc APB |
|---|---|---|
| 1 | `IER[2]` và lỗi từ `regs_n[LSR][2]`. Đường PE luôn bằng 0 sau reset. | `0xCC` theo bộ mã hóa, không tạo được bằng khung lỗi ở chân RX của IP này |
| 2 | `IER[0]` và (RX_count **bằng** ngưỡng hoặc TX FIFO rỗng do nối RDA sai nguồn) | `0xC8` |
| 3 | `IER[0]` và timeout ký tự. Đầu vào `CTI_i` nối 0. | Nhánh này cũng mã hóa `0xC8`, không có timeout hoạt động |
| 4 | `IER[1]` và TX FIFO rỗng, kể cả khi thanh ghi dịch còn phát | `0xC4` |

| ID | Yêu cầu | Tiêu chí chấp nhận |
|---|---|---|
| <a id="irq-01"></a>`IRQ-01` | Mã IIR và ưu tiên | Sau reset đọc `0xC1`, `event_o=0`. Với hai FIFO rỗng, thử độc lập `IER=0x02` rồi `IER=0x03` sau mỗi reset. Sau cạnh cập nhật IRQ, lần lượt đọc `0xC4` và `0xC8`, `event_o=1`. Ghi bit FIFO enable hoặc chỉ `IER[7:3]` không đổi nibble cao IIR. Nguồn không tới được phải truy được tới kết nối cố định của top. |
| <a id="irq-02"></a>`IRQ-02` | Ngưỡng RX bằng đúng số phần tử | `FCR[7:6]=00/01/10/11` chọn T=1/4/8/14. Với TX FIFO còn phần tử, RX ổn định ở T−1, T hoặc T+1 rồi mới bật `IER[0]`. Bắt đầu từng ca ở trạng thái chưa ngắt. Chỉ đúng T tạo `0xC8`. Nếu đi xuyên T với IER đã bật, mã đã chốt sẽ che mất khác biệt. |
| <a id="irq-03"></a>`IRQ-03` | Lỗi ngắt RX giả | `RDA_i` lấy `regs_n[LSR][5]` (TX FIFO rỗng), trong khi DR thật là `LSR[0]`. Với RX rỗng, TX FIFO rỗng, bật riêng `IER[0]`. Chờ cạnh cập nhật rồi kiểm `LSR[0]=0` đồng thời `IIR=0xC8, event_o=1`. Chỉ nhìn TX đang phát chưa đủ để loại ảnh hưởng của RDA vì TX FIFO có thể đã rỗng. |
| <a id="irq-04"></a>`IRQ-04` | Lỗi ngắt không hạ sau mask/clear | Giữ nguồn đang bật qua lần acknowledge để thấy mã được ưu tiên ghi lại. Sau ngắt TX `0xC4`, ghi `IER=0`, đọc IIR hai lần. Lần đầu còn thấy `0xC4`, lần kế thấy `0xC0` nhưng `event_o=1`. Xóa bit trong mã không đặt lại bit 0 về 1. Sau ngắt đầu tiên, chỉ reset khôi phục `0xC1` và hạ `event_o`. |

Nguồn xác định mã, ưu tiên và thao tác clear nằm trong [uart_interrupt.sv](../rtl/vendor/pulp_apb_uart_sv/uart_interrupt.sv). Nguồn RDA, PE và CTI do [top APB UART](../rtl/vendor/pulp_apb_uart_sv/apb_uart_sv.sv) kết nối.

## 7. Hợp đồng hệ thống DE2-115

Top `de2_115_pulp_uart` nối `de2_pulp_uart_master` với đúng IP ở mục 1. `KEY[0]` nhấn thấp để reset, nhả reset qua hai FF. Wrapper đồng bộ `GPIO_UART_RX` qua hai FF trước ba FF trong máy thu. `KEY[1]` và các bit SW dùng cho điều khiển cũng được đồng bộ vào `CLOCK_50`.

| Thứ tự | Ghi APB trong lúc khởi tạo |
|---|---|
| 1–3 | `0x3 ← 0x83` mở DLAB, `0x0 ← 0xB1` ghi DLL, `0x1 ← 0x01` ghi DLM. |
| 4–6 | `0x3 ← 0x03` (8N1) hoặc `0x0B` (8E1), `0x2 ← 0x07` clear hai FIFO và chọn ngưỡng 1, `0x1 ← 0x05` ghi IER khi DLAB đã đóng. |

| ID | Yêu cầu | Tiêu chí chấp nhận |
|---|---|---|
| <a id="sys-01"></a>`SYS-01` | Reset, cấu hình, polling | Đặt `SW[14]` trước khi nhả reset, 0 chọn N, 1 chọn E. Master chốt một lần lúc khởi động. `SW[15]` dự phòng, `SW[13:8]` cũng không điều khiển UART. Kiểm sáu giao dịch trên, `init_done` sau giao dịch thứ sáu và LSR tại `0x5`. Khi idle, bộ đếm thăm dò có ngưỡng 5000 clock (100 µs), có yêu cầu gửi thì thăm dò sớm, sau RBR/THR thì đọc lại LSR ngay. `event_o` không điều khiển master. |
| <a id="sys-02"></a>`SYS-02` | Gửi tay, nhận và hiển thị | Sau init, `KEY[1]` nhấn và nhả ổn định 500000 clock mỗi chiều (10 ms ở 50 MHz). Một lần nhấn hợp lệ chốt `SW[7:0]` vào ô chờ, giữ phím không lặp. Khi `LSR[5]=1`, ghi THR và kiểm đúng một byte trên TX. Khi `LSR[0]=1` và cho phép đọc, RBR cập nhật byte nhận cuối. HEX1/0 hiển thị byte SW hiện tại, HEX5/4 hiển thị byte RX cuối, nibble cao/thấp tương ứng, đoạn tích cực thấp. |
| <a id="sys-03"></a>`SYS-03` | Hold, echo và trạng thái | `SW[16]=1` ngăn chọn lần đọc RBR mới. Hạ xuống để rút dữ liệu còn lại. `SW[17]=1` tại lúc quyết định đọc dành một ô echo cho byte đọc được. Với `SW[16]=0`, echo bật và không có yêu cầu phím, gửi burst 4 rồi 16 byte liền nhau, đối chiếu mỗi byte trở về đúng một lần và đúng thứ tự ở cả 8N1/8E1. Khi tắt echo, vẫn cập nhật HEX RX. Quan sát được hiện tượng đầy RX theo `FIFO-04` khi giữ đọc đủ lâu. |

Master giữ một yêu cầu phím và một yêu cầu echo. Khi cả hai cùng chờ, lượt gửi ưu tiên nguồn khác với lần ghi trước. Một lần nhấn trong khi ô phím còn bận sẽ giữ byte cũ và đặt `fault`, trừ cạnh đang ghi xong byte phím cũ. Lỗi `PSLVERR` nếu được chèn trong test master sẽ đặt `fault`, hạ `init_done` và dừng master. IP nguyên bản luôn trả `PSLVERR=0`.

`LEDR[4:0]` hiển thị `last_lsr[4:0]`. `LEDG[0]` báo init, `[1]` báo fault chốt đến reset, `[2]` báo mode E đã chốt, `[3]` báo giữ đọc, `[4]` báo echo, `[6:5]` hiển thị `last_lsr[6:5]`, `[7]=0`, `[8]` nối trực tiếp `event_o`. Sau khi khởi tạo với hai FIFO rỗng và `IER=0x05`, lần chốt ngắt kế tiếp tạo `0xC8`. LEDG[8] sáng dù `LSR[0]=0` và giữ sáng đến reset, theo `IRQ-03` và `IRQ-04`. [Top và hiển thị](../rtl/fpga/de2_115_pulp_uart.sv) · [Master APB](../rtl/fpga/de2_pulp_uart_master.sv)

## 8. Biên vật lý, bản build và nghiệm thu

| ID | Yêu cầu | Tiêu chí chấp nhận |
|---|---|---|
| <a id="board-01"></a>`BOARD-01` | Chân và điện áp | Đối chiếu 65 chân tín hiệu của top với bảng pin và QSF. `CLOCK_50=PIN_Y2`. `GPIO_UART_TX` ở `GPIO[0]/PIN_AB22` đi tới RXD của CP2102. TXD của CP2102 đi tới `GPIO_UART_RX` ở `GPIO[2]/PIN_AB21`. Hai đường UART dùng logic 3,3 V, GND chung. Kiểm jumper thực tế theo profile (JP6 7–8 cho 3,3 V và JP7 5–6 cho 2,5 V), để hở dây nguồn CP2102. |
| <a id="board-02"></a>`BOARD-02` | Nhận dạng và chấp nhận bản build | Build phải chọn `EP4CE115F29C7` (Cyclone IV E), top `de2_115_pulp_uart`, đúng năm file PULP và hai file wrapper, clock constraint 20 ns. Để nghiệm thu bản nạp, fitter phải hoàn tất, chân/I/O phải khớp profile và STA phải đáp ứng 50 MHz tại các góc phân tích của project. Kiểm slack setup/hold và recovery/removal khi nhả reset, lưu revision và SHA-256 của `.sof`. Trong `always_comb`, `fifo_tx_data` chỉ được gán khi ghi THR. Truy các chẩn đoán latch/vòng tổ hợp về đúng frontend trong báo cáo tổng hợp. Nghiệm thu Quartus cần log Quartus của chính revision này. |
| <a id="board-03"></a>`BOARD-03` | Đường truyền trên bo thật | Với đúng `.sof`, ghi nhận board, thiết lập jumper, CP2102/COM, 115200, flow control tắt và mode terminal khớp SW14 sau reset. Dùng các byte biết trước như `0x01` và `0x55` để đối chiếu PC→HEX và KEY→PC. Bật echo, tắt local echo của terminal, so từng byte hai chiều ở 8N1 và 8E1. Bằng chứng vật lý cần nhận dạng thiết bị, cấu hình và dữ liệu thực nhận cho từng hướng. |

Nguồn gán chân, nguồn project, báo cáo công cụ và quy trình thao tác được quản lý tại [bảng pin](spec/pins.json) · [CSV DE2-115](../reference/DE2_115_pin_assignments.csv) · [project Quartus](../fpga/de2_115/de2_115_pulp_uart.qsf) · [đánh giá tổng hợp](02_Synthesis_Review.md) · [hướng dẫn Windows/FPGA](05_FPGA_Windows.md).

## 9. Bằng chứng lịch sử dùng để đối chiếu

Audit ngày 12/11/2026 dùng `audit_tb.sv` trên năm RTL cùng revision PULP. Gói `APB_UART_review_evidence.zip` có SHA-256 `4752c70578ae7e1c904584b09292ce25f5acf9c1121856fce5ef7f7f8865f301`. Các quan sát sau là số liệu mô phỏng đã lưu của lần audit ấy.

| Hồ sơ trong thư mục `evidence/` của gói | Phạm vi quan sát |
|---|---|
| `baud_sweep.vcd`, `baud_sweep.log` | TX `0x55`, 50 MHz, D=433. Khoảng cạnh start là 8700 ns, tám khoảng data kế tiếp đều 8680 ns. |
| `rx_overflow.log` | Gửi 18 byte `0x40…0x51` trước khi đọc, rút được 17 byte `0x40…0x50`, OE=0. |
| `parity_gap.log`, `framing_gap.log`, `irq_empty_gap.log`, `irq_clear_gap.log` | Sai parity vẫn đọc `0x41` với PE=0, stop thấp vẫn đọc `0xA6` với FE=0. Hai ca IRQ riêng ghi nhận `IIR=0xC8` khi RX rỗng và `IIR=0xC0` với ngắt còn ở mức 1 sau mask/clear. |

Bộ test UVM lịch sử cung cấp stimulus và checker để tham khảo. Ví dụ, lấy mẫu mức cao ở stop thứ hai trên một khung đơn cũng có thể lấy trúng mức idle. `TX-03` vì vậy yêu cầu hai khung đã xếp hàng. Sổ kết quả `main2` là nơi xác định ID nào đã có bằng chứng mới, kể cả phần còn thiếu. [Audit PULP lưu trong lịch sử](https://github.com/hoafff/APB_UART_2026.1/blob/7173ec73cf7a0ecb90808515168ca69780a4e318/docs/history/APB_UART_2026.1_REVIEW.md) · [Test UVM baseline đã lưu](https://github.com/hoafff/APB_UART_2026.1/blob/7173ec73cf7a0ecb90808515168ca69780a4e318/dv/baseline/uvm/apb_uart_uvm_pkg.sv) · [Kết quả của main2](DV_RESULTS.md)
