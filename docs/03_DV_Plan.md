# Yêu cầu 2 · Kế hoạch kiểm chứng IP APB UART

Đối tượng kiểm chứng là `apb_uart_sv` với hai FIFO mặc định sâu 16, APB 12/32 bit, clock 50 MHz và reset tích cực thấp. Filelist gọi trực tiếp năm tệp PULP tại `dfad6e04d19cc9481d3cd2750b45b970dc61271b`. Mã chấp nhận dưới đây lấy từ hợp đồng `main2`. `SYS-01`, `SYS-02`, `SYS-03` thuộc wrapper. `BOARD-01`, `BOARD-02`, `BOARD-03` thuộc hồ sơ FPGA và nghiệm thu vật lý. [Hợp đồng](01_System_Specification.md) · [Chỉ mục ID](spec/requirements.json) · [Filelist mô phỏng](../dv/files.f)

## Điểm đo và mô hình tham chiếu

| Quan sát | Trigger và oracle |
|---|---|
| APB | Sequencer phát item cho driver. Driver đổi tín hiệu ở cạnh xuống. Monitor độc lập lưu SETUP, so địa chỉ/chiều/dữ liệu ghi tại ACCESS, xuất đúng một item ở cạnh lên hoàn tất. Lấy `PRDATA` và `event_o` trước NBA. Kiểm `PREADY=1, PSLVERR=0` mỗi cạnh hoạt động và `PRDATA=0` ngoài READ ACCESS. |
| Thanh ghi | Scoreboard cập nhật LCR/IER/DLL/DLM từ ghi đã quan sát, dùng bank **trước** giao dịch. So toàn bộ word đọc và top 24 bit. Một lượt đọc RBR rỗng có chủ đích chỉ kiểm acknowledge và trạng thái IRQ, byte trả về không có valid. |
| THR → `tx_o` | Ghi THR hợp lệ vào hàng đợi độc lập. Cạnh xuống start lấy đầu cũ vào mô hình thanh ghi dịch. Monitor kiểm start, giải mã LSB-first ở giữa từng bit, tính XOR từ các bit thực thấy và kiểm từng stop. So với N bit thấp của byte APB. Khi clear TX, mô hình giữ khung đã bắt đầu và bỏ hàng chờ. |
| `rx_i` → RBR | BFM phát khung từ yêu cầu. Monitor thứ hai bắt cạnh xuống ngay trên `rx_i` và tự giải mã payload, parity và stop. So quan sát dây với stimulus, sau đó xếp **quan sát dây** làm oracle cho RBR. Mỗi lần đọc có dữ liệu phải khớp đầu hàng đợi. Kiểm DR quanh cả cụm đọc. |
| Khung đầy và lỗi | Mô hình đầy dành riêng cho burst quiescent giữ được 16 byte trong FIFO và một byte RX chờ, hoặc một byte TX đang dịch. Các ca áp đồng thời đúng cạnh push/pop, reset giữa khung và ranh giới lấy mẫu dùng phép thử directed bổ sung riêng. |
| Điểm dừng | UVM objection kéo dài qua các lần decode/pop cuối. `check_phase` kiểm hàng chờ RX, TX, intent và injection còn sót. Runner kiểm DONE, số khung từng ca, số ACCESS, counter, summary UVM và exit. |

Monitor nối vào cổng APB và chân serial của IP. Hai decoder lấy format và chu kỳ danh định từ cấu hình test. Nhánh đo baud lấy **timestamp cạnh thật**. Nhánh RX danh định dùng `1 s/115200` cho mỗi symbol. Mã nguồn theo trách nhiệm nằm ở [APB agent](../dv/uvm/apb_agent.svh), [serial driver và monitor](../dv/uvm/serial_agent.svh), [scoreboard](../dv/uvm/scoreboard.svh) và [môi trường cùng testcase](../dv/uvm/tests.svh).

## Test case, kích thích và tiêu chí

| Ca / ID `main2` | Kích thích và điều kiện kích hoạt | Quan sát quyết định verdict |
|---|---|---|
| `registers` · APB-01, APB-02, APB-03, REG-01 | Sau reset đọc hai bank. Giữ byte RX `62`, phát ghi khi bỏ chọn, SETUP ghi LCR và SETUP đọc RBR không tới ACCESS. Quét đọc/ghi offsets 0…7 với từng DLAB. Ghi cùng byte IER với hai upper word, alias `00B/003`, `008/000`, `00C/014`. Giữ PSEL qua cặp ghi/đọc liên tiếp. | LCR và RBR giữ giá trị qua probe, đọc DLL giữ byte RX, không có cạnh start TX do ghi DLL. IER phục hồi, mỗi THR/RBR hữu hiệu cho đúng một khung/pop. Unmapped đọc zero. Hai SETUP-only giải thích chênh lệch SETUP và ACCESS. |
| `registers` · REG-02, REG-03, IRQ-01 | Đọc LCR/IER/DLL/DLM/LSR/IIR sau reset. Giữ `IER[2:0]=0` với các bit cao bằng 1. Quét đủ tám mã `LCR[6:4]` trên 8E1, đọc lại rồi phát `41,01`. | Sau reset đọc `00/00/00/00/60/C1`, TX idle cao và IRQ thấp. Mỗi cặp byte có parity 0 rồi 1 theo XOR, idle vẫn cao với bit break set. Reset động được ghi riêng ở kết quả bổ sung. |
| `baud` · BAUD-01, BAUD-02, BAUD-03, TX-02, RX-01 | Ở 50 MHz, ghi D=433 và D=27, phát `55` ở 8N1. D=433 thêm 8E1. Ở D=433 lái RX đồng thời bằng peer 115200 độc lập. | Bắt start TX rồi **chín cạnh liên tiếp**. Đối chiếu cực tính và delta ns từng cạnh. Start dài `D+2`, tám khoảng sau dài `D+1`. Cả hai hướng phải hoàn tất ở N và E. Phép đo này chỉ định thời TX và kiểm payload nhận ở RX. |
| `modes` · TX-01, TX-02, TX-03, RX-01 | Với mỗi 5/6/7/8 data × N/E × 1/2 stop, xếp sẵn `41,A6` vào TX và phát hai byte RX bất đối xứng. D=433 cho 8N1/8N2, D=31 cho các tổ hợp còn lại. | So 32 khung TX và 32 RBR. Khoảng cách giữa hai cạnh xuống start phải đúng `(1+n+p+s)×(D+1)+2`. Phép đo trên cặp khung phân biệt stop thứ hai với idle. Bên RX, “2 stop” là độ dài stop của peer. |
| `fifo` · APB-02, REG-04, REG-05, FIFO-01, FIFO-02, FIFO-03, FIFO-04, RX-03 | Giữ trước hai byte khi FCR bit 0 lần lượt 0/1, bật các bit bỏ qua [5:3]. Clear RX khi TX còn hàng đợi, clear TX khi RX còn byte, rồi thử cả `06/07`. Phát `40…51` trên RX trước lần pop đầu, mỗi khung có một bit idle. Ghi 18 THR liên tiếp trong khi byte đầu đang phát. | So FIFO order và số khung, lấy LSR trước mỗi RBR. RX phải đọc `40…50`, OE=0 và DR hạ sau khi rút 17. TX phải phát `80…90`, APB vẫn ready khi mất lần ghi thứ 18. Clear giữ đúng phía độc lập và khung TX đang dịch. Kiểm THRE/TEMT khi queued, khi chỉ còn khung đang phát và khi idle. |
| `errors` · RX-02, RX-03, REG-04, REG-05, IRQ-01 | 8E1, bật riêng IER bit 2. Xếp bốn byte `31,32,33,34` tương ứng sạch, đảo parity, kéo stop thấp, cả hai. Đọc LSR/IIR trước RBR **từng byte**. | `WIRE` chứng minh loại lỗi ở chân. So từng RBR với byte giải mã, ghi nhận PE/FE, IIR và IRQ. DUT này dự kiến giữ LSR=61 và IIR=C1 dù có lỗi. Nếu quan sát đổi, ca characterization phải mở lại. |
| `irq` · REG-05, IRQ-01, IRQ-03, IRQ-04 | Bật IER riêng/đồng thời khi rỗng. Giữ nguồn THRE qua lần đọc IIR, sau đó mask IER và đọc IIR hai lần. Bật nguồn RDA khi RX rỗng, khi RX có byte. Mask rồi đọc các bank, RBR rỗng/có dữ liệu, hoặc LSR. Reset giữa các điểm cần mã no-pending. | Lấy IIR và `event_o` cùng cạnh READ ACCESS. Phân biệt C1/0, C4/1, C8/1 và C0/1. Kiểm đọc không liên quan giữ C8, LSR vẫn giữ dữ liệu, RBR pop byte cũ. C0/1 sau acknowledge là giới hạn RTL. |
| `thresholds` · IRQ-02, IRQ-03, FIFO-03 | Mỗi điểm bắt đầu từ reset với IER=0. Nạp RX đến T−1/T/T+1 với T=1/4/8/14. Ghi hai THR để **TX FIFO còn phần tử**, kiểm LSR[5]=0 trước khi bật IER[0]. | Khi số RX còn ổn định, đọc IIR và sample `event_o`. Đúng T phải là C8/1, hai lân cận là C1/0. Rút hết RX theo thứ tự và đợi hết TX trước điểm tiếp. |
| `random` · APB-01…03, REG-01, TX-01…03, RX-01 | Mỗi seed randomize 48 register items (cả chiều đọc/ghi, ô 1/3/4/6/7, bank địa chỉ cao 0/1/15h), rồi 32 frame items (hướng, byte, format, bit [5:4], alias và khoảng nghỉ). Mỗi frame đổi cấu hình ở trạng thái rỗi. | Cùng scoreboard với ca directed. Bản ghi `STIM` lưu từng item. Seed 17 chạy lặp, cả trace hash, bin counts, số giao dịch và số khung phải trùng. Ba seed 17/29/101 phải có ba hash stimulus khác nhau. |
| Hai control `baud` | Giữ nguyên APB và dây, lật bit 0 đúng một lần ở kỳ vọng TX hoặc RBR. | Yêu cầu đúng `TX_DATA: 55/54` hoặc `RBR_DATA: 96/97` (thực thấy/kỳ vọng đã đảo), đúng 1 UVM_ERROR, 0 UVM_FATAL, có `DV_CHECKS_FAILED` và process thoát khác 0. Ca không tiêm phải thành công. |

## Coverage và phạm vi kết luận

Hai SystemVerilog covergroup lấy mẫu trên sự kiện thực. `apb_cg.access_cross` có 32 bin đọc/ghi × offset × DLAB. `serial_cg.frame_cross` có 32 bin hướng × data bits × parity × stop, lấy sau khi kiểm khung TX hoặc byte RBR có frame sạch. Số đếm portable cho từng cell phải khớp file coverage gốc của Verilator. Các coverpoint thành phần có thêm 22 bin.

Các nhóm procedural bổ sung là alias (4), `LCR[6:4]` (8), LSR (5), FIFO/FCR (8), lỗi parity × stop ở RX (4), IRQ/acknowledge (12) và T với ba occupancy (12). Mỗi case có check tương ứng trước khi hợp nhất kết quả. Chỉ lần chạy thông thường thành công được tính vào tổng. Replay và hai control có sổ kết quả riêng. Đây là mẫu số cho các hành vi đã định nghĩa trong plan. Coverage toggle/line/branch và kiểm chứng hình thức có phạm vi khác. [Định nghĩa từng bin và điều kiện PASS](../dv/results.py)

## Phép thử directed bổ sung

| ID | Kích thích, trigger và oracle riêng của probe |
|---|---|
| FIFO-01, FIFO-02 | Trên primitive 8/9 bit, dùng hàng đợi tham chiếu, đi qua pre-count 0…16, wrap và push/pop đồng thời. Ở top, đặt ACCESS đọc RBR trước/cùng/sau cạnh byte đến. Đặt ghi THR lúc FIFO đầy đúng cạnh dequeue hoặc trễ một clock. Dùng tín hiệu handshake nội bộ để xác định cạnh collision rồi kiểm RBR/chuỗi TX ở ngoài. Control lật bit 8 của một word ở nhánh 9 bit. |
| FIFO-03, REG-04 | Căn RX offer và thời điểm TX lẽ ra lấy đầu FIFO ở 0, 1 hoặc 2 clock sau cạnh ghi FCR. Kiểm LSR, byte cũ còn/biến mất và byte refill. Control bỏ bit clear RX trên cùng lịch kích thích. |
| REG-02 | Có RX chờ, TX đang dịch và còn byte TX xếp hàng, một frame RX khác đang đến. Assert reset trước cạnh lên của WRITE ACCESS. Kiểm TX/IRQ ngay khi reset, readback hai bank, FIFO, khoảng rỗi và một frame mới ở mỗi hướng. |
| BAUD-01 | Ghi D=0 và D=65535, xếp `55,A6`. Đo cạnh start, tám khoảng data, stop+idle, khoảng start→start và decode cả hai frame để kiểm hai đầu bộ đếm. |
| BAUD-03, RX-01, REG-04 | Lái 48 khung 8E1 ở D=432/433. Trên từng bit 0…7, dịch cạnh dữ liệu −1/0/+1 clock với mốc lấy mẫu ở chân RX. So bit nhận qua RBR, đọc DR tại hai cạnh kế tiếp và đọc RBR trước parity ở một phần ba số khung. |
| APB-01 | Cố ý giữ READ/WRITE ACCESS qua hai cạnh lên. Dùng hai byte khác nhau trong RX và decode hai khung TX để xác định số lần pop/ghi. |
| RX-02, RX-03 | Ở D=433, thay khung bằng xung thấp 4 clock hoặc giữ thấp liên tục qua độ dài khung. Poll LSR bằng APB, kiểm FE/BI, số byte, RBR và frame hồi phục. |

Các probe có runner, nguồn và sổ kết quả riêng. Kết quả UVM chỉ cộng các nhóm đã định nghĩa ở bảng coverage. [Runner probe](../dv/probes/run.py) · [Log probe đã chạy](../dv/probes/main.log) · [Kết quả và phần còn mở](DV_RESULTS.md) · [Cách chạy Verilator và Questa](../dv/README.md)
