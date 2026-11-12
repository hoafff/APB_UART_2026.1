# Ma trận truy vết SPEC → RTL → testcase → observer → evidence

Trạng thái chạy nằm trong RESULTS.md và evidence JSON; bảng này không tự chuyển PASS thành sign-off.

| Requirement | Mục SPEC | Testcases | Phạm vi | Nghĩa cần kiểm |
|---|---|---|---|---|
| `TGT-SRC-01` | 1,3 | TC17 | DOC | Giữ nguyên baseline S03; filelist bản sửa không compile trùng module. |
| `TGT-SRC-02` | 1,15 | TC18 | DOC | Ghi đúng version DUT/TB/tool và không dùng baseline PASS để đóng yêu cầu target. |
| `TGT-APB-01` | 5.1 | TC01 | SIM | Mọi transfer có SETUP trước ACCESS; control/data giữ ổn định đến completion. |
| `TGT-APB-02` | 5.1 | TC01, TC13 | SIM | Chỉ side effect một lần tại completion; không side effect ở idle/setup. |
| `TGT-APB-03` | 4.1,5 | TC01 | SIM | PRDATA zero-extend byte; ngoài valid read hoặc khi reset phải bằng 0. |
| `TGT-APB-04` | 5.2,6.1 | TC01 | SIM | Decode đúng word-aligned/full-address; không alias address cao hoặc misaligned. |
| `TGT-APB-05` | 5 | TC01, TC15 | SIM | PREADY=1 cố định; master kiểm PSLVERR tại completion. |
| `TGT-APB-06` | 5.2 | TC01 | SIM | Invalid address/quyền truy cập trả PSLVERR=1, PRDATA=0, không thay state. |
| `TGT-APB-07` | 5.2,9.1 | TC06, TC13 | SIM | RBR empty trả 0/no-error; không pop phantom hoặc lấy byte vừa push cùng cạnh. |
| `TGT-APB-08` | 5.2,9.1 | TC06, TC09, TC10 | SIM | THR full không pop hoặc D=0 bị từ chối, không enqueue hay đặt RX OE. |
| `TGT-REG-01` | 6.1,6.2 | TC01 | SIM | DLAB chọn đúng DLL/DLM hoặc RBR/THR/IER; không ảnh hưởng IIR/FCR/LSR. |
| `TGT-REG-02` | 6.2 | TC01, TC02, TC03 | SIM | LCR WLS/STB/PEN/EPS/DLAB hoạt động; bits 6:5 read-zero/write-ignore. |
| `TGT-REG-03` | 6.3 | TC01, TC07 | SIM | IER chỉ giữ bits 2:0; write khi DLAB=1 không đổi IER. |
| `TGT-REG-04` | 6.3,9 | TC06 | SIM | FCR enable chọn capacity 1/16; đổi enable flush hai queue đúng ưu tiên. |
| `TGT-REG-05` | 6.3,9.3 | TC06, TC13 | SIM | FCR RX clear xóa queue/OE/metadata; không abort frame RX chưa hoàn tất. |
| `TGT-REG-06` | 6.3,9.3 | TC06, TC13 | SIM | FCR TX clear xóa queued bytes; không cắt frame active hoặc lấy byte cũ ở cạnh clear. |
| `TGT-REG-07` | 6.3 | TC07 | SIM | Threshold effective là 1/4/8/14 khi FIFO on, bằng 1 khi FIFO off. |
| `TGT-REG-08` | 6.4 | TC01, TC05, TC06 | SIM | LSR DR/THRE/TEMT/OE/head-error/RX_ERR phản ánh đúng state được định nghĩa. |
| `TGT-REG-09` | 6.4,9.3 | TC05, TC13 | SIM | Read LSR clear OE cũ/ack head cũ, không ack byte mới hoặc xóa overflow mới. |
| `TGT-REG-10` | 6.5 | TC07 | SIM | IIR mã 01/06/04/02 với bits FIFO đúng; read không nhầm side effect. |
| `TGT-REG-11` | 6.2 | TC09 | SIM | Frame snapshot config trước cạnh start; config write cùng cạnh áp dụng cho frame sau. |
| `TGT-BAUD-01` | 7.1 | TC02, TC10 | SIM | Một oversample tick mỗi D clock; một bit đúng 16D clock; không tạo clock domain mới. |
| `TGT-BAUD-02` | 7.1 | TC09, TC10 | SIM | D=0 không start frame mới; không divide-by-zero; frame active hoàn tất theo D đã chốt. |
| `TGT-BAUD-03` | 7.1,10.3 | TC10, TC14 | SIM | Board profile D=27, DLL=1B/DLM=00, bit=432 clock tại 50 MHz. |
| `TGT-BAUD-04` | 3,7.1 | TC10 | SIM | D hợp lệ 1..65535; counter đủ rộng, không overflow ở cực trị. |
| `TGT-BAUD-05` | 7.1,7.2 | TC02, TC10 | SIM | Start/data/parity/stop cùng Tbit, không thừa một clock ở start. |
| `TGT-BAUD-06` | 7.3 | TC04 | SIM | RX nhận đúng frame sạch ở tổng mismatch ±2% và phase bắt đầu khác nhau. |
| `TGT-TX-01` | 7.2 | TC02, TC08 | SIM | TX idle/reset=1, start=0, dữ liệu LSB-first, phát đúng byte được enqueue. |
| `TGT-TX-02` | 7.2 | TC02, TC16 | SIM | Chỉ phát 5/6/7/8 data bits theo WLS, không phát bit cao ngoài N. |
| `TGT-TX-03` | 7.2 | TC02, TC16 | SIM | None/odd/even parity đúng XOR của đúng N data bits. |
| `TGT-TX-04` | 7.2 | TC02 | SIM | Giữ đủ 1/2 stop bits; kiểm bằng frame liên tiếp, không chỉ sample idle. |
| `TGT-TX-05` | 7.2 | TC02, TC13 | SIM | Có queued byte thì cho phép next start ngay sau stop cuối, không mất/nhân đôi byte. |
| `TGT-TX-06` | 2,7 | TC11 | SIM | TX và RX hoạt động đồng thời, không dùng chung phase gây dịch timing. |
| `TGT-RX-01` | 4.1,7.3 | TC08, TC14 | SIM | Synchronizer RX reset-high; sampling chỉ dùng tín hiệu sau đồng bộ. |
| `TGT-RX-02` | 7.3 | TC12 | SIM | Majority 7/8/9; false start không tạo byte/error. |
| `TGT-RX-03` | 7.3 | TC03, TC11 | SIM | Nhận đúng N bit, zero-extend data, đúng thứ tự và số lượng frame. |
| `TGT-RX-04` | 7.3 | TC05 | SIM | Sai parity odd/even đặt PE trên đúng byte; parity off không đặt PE. |
| `TGT-RX-05` | 7.3 | TC05 | SIM | Stop nào sai cũng đặt FE; frame lỗi vẫn được lưu nếu có slot. |
| `TGT-RX-06` | 7.4 | TC05, TC14 | SIM | Break tạo một entry zero với BI/FE, không lặp byte khi còn thấp; phục hồi sau idle. |
| `TGT-RX-07` | 7.3 | TC05, TC13 | SIM | Completion chỉ sau khi kiểm parity/stop và đủ quyết định BI; metadata nguyên tử với data. |
| `TGT-RX-08` | 9.2 | TC06 | SIM | Full không slot: drop frame mới, set OE, tiếp tục nhận; không hidden slot thứ 17. |
| `TGT-RX-09` | 7.3,7.4 | TC05, TC09, TC12 | SIM | Arm sau reset/disable/error đúng điều kiện idle; không nhận frame giả từ mức thấp kéo dài. |
| `TGT-RX-10` | 7.3 | TC04 | SIM | Nhận frame liên tiếp kể cả peer nhanh hơn; completion cũ không chặn start mới. |
| `TGT-FIFO-01` | 3,9.1 | TC06 | SIM | Capacity/count đúng 1 hoặc 16; không underflow/overflow counter. |
| `TGT-FIFO-02` | 9.1 | TC06 | SIM | Thứ tự byte/metadata FIFO không đổi khi pointer wrap. |
| `TGT-FIFO-03` | 9.1 | TC13 | SIM | Full + valid pop + push cùng cạnh nhận cả hai, không báo OE giả. |
| `TGT-FIFO-04` | 9.1 | TC13 | SIM | Empty + pop + push không bypass: pop không hợp lệ, byte mới còn trong queue. |
| `TGT-FIFO-05` | 9.3 | TC08, TC13 | SIM | Reset/clear thắng giao dịch queue; completion tại RX flush bị bỏ không sinh OE. |
| `TGT-FIFO-06` | 6.4,9 | TC05, TC13 | SIM | Error-ack gắn đúng entry; head thay đổi không dùng lỗi/ack của head cũ. |
| `TGT-IRQ-01` | 6.5 | TC07 | SIM | IER mask quyết định event/IIR ngay sau write; IRQ active-high dạng mức. |
| `TGT-IRQ-02` | 6.5 | TC07 | SIM | Ưu tiên RLS > RDA > THRE; nguồn thấp không mất khi bị nguồn cao che. |
| `TGT-IRQ-03` | 6.5 | TC07 | SIM | RDA theo RX count ≥ threshold, không phụ thuộc TX empty. |
| `TGT-IRQ-04` | 6.5 | TC07, TC13 | SIM | THRE pending set/ack đúng edge; read IIR nguồn khác không ack nhầm. |
| `TGT-IRQ-05` | 6.5 | TC07 | SIM | Read LSR/RBR/IIR chỉ giải quyết đúng nguồn; event có thể còn cao nếu còn nguồn khác. |
| `TGT-IRQ-06` | 6.5 | TC07 | SIM | Khi không còn nguồn được enable, event=0, IIR bit0=1; không kẹt C0/00. |
| `TGT-IRQ-07` | 6.5,9.3 | TC07, TC13 | SIM | Sự kiện mới cùng cạnh acknowledge không mất; set mới thắng clear cũ. |
| `TGT-RST-01` | 8.1 | TC01, TC08 | SIM | Reset register/count/pending đúng bảng; post-release LSR=60/IIR=01. |
| `TGT-RST-02` | 8 | TC08 | SIM | Reset abort frame/transaction, không stale byte hoặc replay sau reset. |
| `TGT-RST-03` | 8.2 | TC14 | SIM | KEY0 async assert/sync deassert hai cạnh; DUT/wrapper dùng cùng reset nội bộ. |
| `TGT-RST-04` | 8 | TC08, TC14 | SIM | TX reset-high, RX synchronizer high, display/pending/LED lỗi reset đúng. |
| `TGT-SYS-01` | 4.2,13 | TC17, TC18, TC14 | SIM | Top khai báo 65 bit port và map đủ, không trùng pin. |
| `TGT-SYS-02` | 10.1 | TC14 | SIM | KEY/SW/RX đồng bộ theo contract, không dùng tín hiệu async trực tiếp điều khiển FSM. |
| `TGT-SYS-03` | 10.1 | TC14 | SIM | Debounce cả nhấn/nhả đủ 500000 mẫu; một pulse/nhấn, held-key không lặp. |
| `TGT-SYS-04` | 10.1,10.5 | TC14, TC15 | SIM | Manual byte chốt tại pulse, giữ đến THR success, SW đổi không thay byte pending. |
| `TGT-SYS-05` | 10.2 | TC14, TC15 | SIM | SW14/15 chốt trong init, no runtime parity change; SW16/17 có thời điểm hiệu lực rõ. |
| `TGT-SYS-06` | 10.3 | TC14, TC15 | SIM | Đúng 6 init write, địa chỉ/data đúng, init_done chỉ sau success; ≤32 clock. |
| `TGT-SYS-07` | 10.4 | TC15 | SIM | Poll 5000 clock và wake sớm; SW16 hold không gây IRQ busy-loop chặn TX. |
| `TGT-SYS-08` | 10.5 | TC15 | SIM | Không overwrite manual/echo slot; reject manual overflow có fault indication. |
| `TGT-SYS-09` | 10.2,10.5 | TC14, TC15 | SIM | SW16 chỉ dừng RBR mới; UART RX/TX vẫn chạy, overflow báo OE. |
| `TGT-SYS-10` | 10.5 | TC14, TC15 | SIM | Echo dùng PRDATA byte nhận; reserve slot trước pop, không mất byte do pending overwrite. |
| `TGT-SYS-11` | 10.4,10.5 | TC15 | SIM | Manual/echo công bằng khi cùng pending; RX liên tục không loại cơ hội TX. |
| `TGT-SYS-12` | 10.6 | TC15 | SIM | APB error dừng master vào FAULT; không xóa slot như thể write thành công. |
| `TGT-SYS-13` | 10.6 | TC14, TC17 | SIM | HEX/LED đúng nibble/polarity; error LED sticky độc lập với LSR clear. |
| `TGT-SYS-14` | 4.2,10.6 | TC14 | SIM | SW dự phòng không tác dụng; LEDG chưa dùng xuất 0. |
| `TGT-SYS-15` | 10.5 | TC06, TC14, TC15 | SIM | Lossless chỉ trong traffic budget; overload có expected drop/OE được báo. |
| `TGT-FPGA-01` | 11 | TC19 | HARDWARE_PENDING | Đúng chip/top/SystemVerilog/filelist; clock constraint 20 ns; không trộn baseline. |
| `TGT-FPGA-02` | 11,13 | TC17, TC19 | HARDWARE_PENDING | Gán đủ pin/I/O standard và kiểm bank/JP6 thực tế. |
| `TGT-FPGA-03` | 12 | TC19 | HARDWARE_PENDING | Đấu chéo TX/RX, GND chung, mức logic phù hợp, terminal đúng cấu hình. |
| `TGT-FPGA-04` | 11 | TC19 | HARDWARE_PENDING | Compile/fitter/STA đạt tiêu chí, review latch/CDC/unconstrained paths. |
| `TGT-FPGA-05` | 12,14.2 | TC19 | HARDWARE_PENDING | Lưu bằng chứng board TX/RX/echo/mode/error; không dùng simulation thay hardware result. |
