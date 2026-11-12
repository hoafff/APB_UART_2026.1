# Rà soát APB_UART_2026.1 cho bài tập UART/APB và FPGA DE2-115

Ngày kiểm tra: 12/11/2026. Repo được kiểm tra tại commit `e0b17bfadaebefa578e2141ee57c32ed9a5d6f56` trên nhánh `main`. RTL tham chiếu PULP: `dfad6e04d19cc9481d3cd2750b45b970dc61271b`.

**Kết luận: repo có nền tảng SPEC và DV Plan phù hợp, nhưng bản hiện tại chưa sẵn sàng để nạp DE2-115 hoặc kết luận đã hoàn thành bài tập.** Có lỗi cú pháp chặn UVM compile, một lỗi giá trị DLM trong SPEC, phần tích hợp FPGA còn thiếu, và các giới hạn/lỗi chức năng của RTL gốc. Kết quả mô phỏng trong báo cáo này không thay thế Quartus timing analysis hoặc thử board thật.

**Phạm vi đã kiểm tra**

- Đọc đề bài trong ảnh, toàn bộ tài liệu đính kèm, README/SPEC/DV Plan/discrepancy register và toàn bộ RTL/UVM/runner của repo.
- So sánh từng byte: 5 file RTL, `src_files.yml` và LICENSE trong repo khớp upstream. `reference/Huongdan_UART.md` khớp nội dung người dùng dán.
- Đọc `/home/hoaff/Downloads/DE2_115_pin_assignments.csv`; đối chiếu 52 chân được hướng dẫn sử dụng và chuẩn I/O tương ứng.
- Thử runner gốc, kiểm tra compile, thử bản sao chỉ sửa cú pháp, chạy thêm các phép kiểm tra trực tiếp RTL và lưu log/waveform.
- Không thay đổi checkout repo gốc, không commit/push/deploy. Bản sửa UVM dùng để kiểm tra nằm ngoài checkout; patch được bàn giao riêng.

**1. Các việc cần sửa hoặc bổ sung, theo ưu tiên**

| Mục | Mức độ | Bằng chứng và hậu quả | Sửa tối thiểu / kiểm chứng |
|---|---|---|---|
| R01 — UVM không compile nguyên trạng | Chặn mô phỏng | `dv/uvm/apb_uart_uvm_pkg.sv` có 15 chỗ dùng backtick trước `sformatf` (bắt đầu dòng 317); `dv/uvm/tb_top.sv:47` dùng backtick trước `fatal`. Verilator báo `Define or directive not defined`. Đây là lỗi cú pháp SystemVerilog, độc lập với việc máy có Questa hay không. | Đổi thành `$sformatf(...)` và `$fatal(...)`. Patch đính kèm chỉ sửa 16 chỗ này. Sau sửa, chạy lại normal suite và known-gap suite. |
| R02 — Chưa có hệ thống FPGA | Chặn bring-up | Repo chỉ có 5 RTL DUT; không có `de2_115_apb_uart_bringup.sv`, APB master, debouncer/HEX decoder, `.qpf`, `.qsf`, `.sdc`, `.sof` hoặc kết quả Quartus. README cũng xác nhận chưa triển khai Yêu cầu 3. | Viết wrapper + project Quartus cho `EP4CE115F29C7`, thêm clock 50 MHz/20 ns, map chân, kiểm reset/CDC, mô phỏng wrapper rồi chạy fitter/STA trước khi nạp. UVM là môi trường mô phỏng, không đưa lên FPGA. |
| R03 — SPEC hướng dẫn sai byte cao divisor | Cao | `docs/01_System_Specification.md:307` ghi DLM “thường 0 ... divisor ~433”. Thực tế `433 = 0x01B1`; DLM phải là `0x01`. `init_uart_8n1()` trong UVM dòng 465–468 đang ghi đúng. Nếu người viết wrapper làm theo câu này, UART sẽ chạy sai baud. | Sửa bảng init thành DLL=`0xB1`, DLM=`0x01` cho divisor 433; ghi rõ số đo bit dữ liệu và start bit bên dưới. |
| R04 — Ngắt không trở về trạng thái không-ngắt sau clear | Cao, lỗi upstream mới được tái hiện | `uart_interrupt.sv:62–81` clear bằng phép AND các bit mã IIR nhưng không đặt lại bit 0 về 1. `event_o=~iir_q[0]` ở dòng 97. Thử IER=2 → IRQ TX-empty; sau đó IER=0 và đọc IIR hai lần: vẫn `IIR=0xC0`, `event_o=1`. | Bổ sung issue/test vào SPEC/DV Plan. Nếu yêu cầu sử dụng IRQ đúng, sửa logic mã hóa/clear ở revision DUT riêng và chạy regression. Polling có thể dùng cho bring-up cơ bản, nhưng không đóng yêu cầu kiểm thử ngắt. |
| R05 — Normal suite chưa chứng minh đủ các yêu cầu | Khoảng trống kiểm chứng | Chưa có kiểm tra đầy đủ FIFO 16/17, TX FIFO clear/full, IRQ/threshold, reset đang truyền, nhiều seed và coverage closure trong repo. `run_questa.sh` không cấu hình lưu coverage database hoặc waveform phục vụ sign-off. | Hoàn thiện theo ma trận REQ→TC trong DV Plan, bật và lưu coverage/log/waveform; mỗi requirement phải có checker và kết quả riêng. Có tên test hoặc covergroup chưa đồng nghĩa đã đạt coverage. |
| R06 — Test stop=2 còn có thể lọt lỗi | Khoảng trống checker | `uart_tx_mode_matrix_test` dòng 655–680 gửi từng byte rồi chờ dài; TX monitor dòng 232–235 chỉ kiểm mức 1 ở vị trí stop. Nếu DUT chỉ phát 1 stop rồi về idle=1, phép kiểm stop thứ hai vẫn thấy 1. | Queue ít nhất 2 frame và đo khoảng cách start-to-start hoặc thời lượng phần stop, sao cho DUT phát thiếu stop thứ hai sẽ bị báo lỗi. Đây là nhận xét từ source, chưa chạy mutation trên UVM checker. |

Các source chính có thể mở trên GitHub: [testbench UVM](https://github.com/hoafff/APB_UART_2026.1/blob/e0b17bfadaebefa578e2141ee57c32ed9a5d6f56/dv/uvm/apb_uart_uvm_pkg.sv#L317), [watchdog](https://github.com/hoafff/APB_UART_2026.1/blob/e0b17bfadaebefa578e2141ee57c32ed9a5d6f56/dv/uvm/tb_top.sv#L47), [SPEC DLM](https://github.com/hoafff/APB_UART_2026.1/blob/e0b17bfadaebefa578e2141ee57c32ed9a5d6f56/docs/01_System_Specification.md#L307), [logic ngắt upstream](https://github.com/pulp-platform/apb_uart_sv/blob/dfad6e04d19cc9481d3cd2750b45b970dc61271b/uart_interrupt.sv#L62).

**2. Hướng dẫn của giảng viên cần được đối chiếu với DUT thực tế**

Repo của bạn đã ghi nhận đúng hai khác biệt quan trọng trong `docs/00_RTL_Guide_Discrepancies.md`:

| Thanh ghi | Địa chỉ hướng dẫn | PADDR thực tế của DUT |
|---|---:|---:|
| RBR / THR / DLL | `0x00` | `0x0` |
| IER / DLM | `0x04` | `0x1` |
| IIR / FCR | `0x08` | `0x2` |
| LCR | `0x0C` | `0x3` |
| LSR | `0x14` | `0x5` |

DUT giải mã `PADDR[2:0]`, nên không được dùng nguyên bảng word-aligned trong hướng dẫn. Phép thử chạy đúng 6 lần ghi theo hướng dẫn xác nhận LCR/DLL/DLM vẫn bằng 0; những lần ghi 0x00 và 0x08 đi vào THR vì DLAB chưa được bật.

Đo TX bằng dữ liệu `0x55` tại clock 50 MHz, quan sát các cạnh nối tiếp:

| Divisor | DLL/DLM | Thời gian start bit | Thời gian bit dữ liệu | Baud theo bit dữ liệu |
|---:|---|---:|---:|---:|
| 27 | `1B / 00` | 580 ns | 560 ns | 1.785.714,286 |
| 432 | `B0 / 01` | 8.680 ns | 8.660 ns | 115.473,441 |
| **433** | **`B1 / 01`** | **8.700 ns** | **8.680 ns** | **115.207,373** |
| 434 | `B2 / 01` | 8.720 ns | 8.700 ns | 114.942,529 |

Trong phạm vi phép đo này, các bit dữ liệu dài `D+1` clock; start bit dài `D+2` clock. Divisor 433 có sai số bit dữ liệu khoảng **+0,0064%** so với 115200. Loopback 8N1 với `00, FF, 55, AA` đã kiểm tra đúng. Đây là bằng chứng RTL simulation ở 50 MHz; chưa phải phép đo CP2102/clock thực trên board và chưa khảo sát đầy đủ sai lệch baud giữa hai thiết bị.

Các tính năng sau của RTL gốc **chưa đáp ứng đầy đủ mục tiêu hướng dẫn**:

- Chọn odd/even qua SW[15] không thực hiện được chỉ bằng LCR; DUT chỉ sử dụng parity-enable và tạo even parity.
- Khung sai parity vẫn nhận nhưng PE không bật; `err_clr_i` bị nối cố định 1, và dữ liệu còn được đẩy vào FIFO trước state PARITY.
- Stop bit sai không tạo FE; OE cũng không bật khi vượt khả năng nhận.
- RDA nối với TX FIFO empty: bật IER[0] khi RX rỗng vẫn thu `IIR=0xC8`, `event_o=1`.
- Thêm lỗi IRQ không hạ sau mask/clear như R04 ở trên.

Nếu bài yêu cầu demo đúng odd parity, PE/FE/OE và ngắt, chỉ làm wrapper sẽ không đủ. Cần giữ nguyên baseline để đối chiếu và có revision RTL sửa lỗi được kiểm thử riêng; hoặc ghi rõ giới hạn trong phạm vi bài được chấp nhận. Không đổi nhãn các lỗi này thành PASS của yêu cầu hướng dẫn.

**3. Kết quả chạy và giới hạn bằng chứng**

Runner gốc `bash dv/sim/run_smoke.sh 17` dừng ở bước kiểm tra môi trường (exit 2: không có `vlog/vsim/vlib`). Vì vậy chưa có kết quả chạy trên Questa/ModelSim. Kiểm tra UVM nguyên trạng bằng Verilator tái hiện lỗi cú pháp R01.

Trên **bản sao chỉ sửa 15 `$sformatf` và 1 `$fatal`**, giữ nguyên RTL và logic test: build thành công với **Verilator 5.055 devel rev v5.054-129-g14bd81f66 (mod)**, thư viện `verilator/uvm` commit `656f20d087370a7c742e00188d20bbf30fa95339` (UVM 2020.3.1), `UVM_NO_DPI`, seed **17**. Các cảnh báo UVM NO_DPI liên quan kiểm tra tên component đã được giữ trong log.

| UVM testcase | Kết quả | UVM_ERROR / UVM_FATAL |
|---|---|---|
| `apb_reg_smoke_test` | PASS | 0 / 0 |
| `apb_reg_alias_test` | PASS | 0 / 0 |
| `uart_tx_8n1_test` | PASS | 0 / 0 |
| `uart_rx_8n1_test` | PASS | 0 / 0 |
| `uart_rx_fifo_order_test` | PASS | 0 / 0 |
| `uart_rx_fifo_clear_test` | PASS | 0 / 0 |
| `uart_tx_mode_matrix_test` | PASS | 0 / 0 |
| `apb_random_regs_test` | PASS | 0 / 0 |
| `uart_rx_parity_gap_test` | EXPECTED_GUIDE_GAP | 1 / 0 |
| `uart_irq_rda_gap_test` | EXPECTED_GUIDE_GAP | 1 / 0 |

**8/8 normal tests PASS**, trong đó TX mode matrix báo `TX verified=16`; random APB chạy 80 giao dịch với seed 17. Hai known-gap test mỗi ca báo đúng 1 UVM_ERROR với issue ID tương ứng; không tính là PASS của chức năng parity/IRQ. Kết quả thuộc bản sao đã sửa cú pháp, không phải source nguyên trạng trên GitHub.

Chưa thu coverage database hoặc waveform cho UVM suite; không kết luận đạt coverage targets, không coi đây là kết quả Questa hay sign-off FPGA. Waveform được lưu cho 9 phép kiểm RTL độc lập bên dưới. Build UVM ban đầu phải dừng vì áp lực RAM; bản build chia nhỏ (`--output-groups 64`, `-j1`, `-O0`) hoàn tất. Log thất bại và log thành công đều được giữ riêng.


Các phép kiểm tra bổ sung dùng `audit_tb.sv` riêng, kết nối APB/UART vào nguyên 5 RTL upstream, không force state nội bộ. Mỗi ca có log và VCD:

| Ca bổ sung | Quan sát thực tế | Phân loại |
|---|---|---|
| `baud_sweep` | 4 divisor, 9 khoảng cạnh mỗi divisor; số đo như bảng trên | Đã đo và kiểm tra |
| `guide_init` | 6 write theo guide không thiết lập LCR/DLL/DLM | Sai khác guide tái hiện |
| `loopback_8n1` | `00/FF/55/AA` đúng dữ liệu, LSR DR và pop | PASS phạm vi ca |
| `parity_gap` | RBR=`41`, LSR=`61`, PE=0 dù parity sai | Lỗi/giới hạn tái hiện |
| `framing_gap` | RBR=`A6`, LSR=`61`, FE=0 dù stop sai | Lỗi/giới hạn tái hiện |
| `irq_empty_gap` | RX trống, IIR=`C8`, IRQ=1 | Lỗi tái hiện |
| `irq_clear_gap` | IER=0, IIR=`C0`, IRQ vẫn 1 sau clear | Lỗi tái hiện |
| `rx_overflow` | Gửi 18 byte không đọc: sau đó lấy được 17 byte đầu, OE=0 | Hành vi biên và mất dữ liệu tái hiện |
| `reset_mid_frame` | Reset giữa khung RX, khởi tạo lại rồi nhận `3C`, không có byte cũ | PASS phạm vi ca |

Chi tiết overflow cần đưa vào SPEC/test: FIFO thực sự sâu 16; byte thứ 17 được giữ chờ trong receiver ở `SAVE_DATA` và chỉ chuyển vào FIFO sau khi APB đọc mở chỗ trống. Với stimulus đã chạy, byte thứ 18 mất. Không nên mô tả đơn giản rằng byte thứ 17 chắc chắn bị drop. Test giữ nguyên RTL và kiểm thứ tự qua RBR.

Tổng cộng 9 phép kiểm bổ sung hoàn tất các assertion của chúng: **3 ca chức năng/đo lường và 6 ca xác nhận sai khác/lỗi**. Không báo “9 tính năng của hướng dẫn PASS”. Negative control ngắt dây loopback TX→RX ở bản sao testbench đã bị checker phát hiện (`loopback RX DR`, exit khác 0).

Verilator cũng cảnh báo latch ở `apb_uart_sv.sv:195` do `fifo_tx_data` không được gán trên mọi nhánh tổ hợp. Cảnh báo này thuộc RTL upstream. Chưa có bằng chứng Quartus để khẳng định cách tổng hợp/timing cụ thể; nên kiểm tra trong synthesis review và xử lý riêng nếu sửa DUT.

**4. Pin map và mức sẵn sàng DE2-115**

Đã đối chiếu **52/52 chân và I/O standard** giữa hướng dẫn và CSV trong Downloads: CLOCK_50, KEY0/1, GPIO0/2, SW0..7/SW14..17, LEDR0..4, LEDG0/8, HEX0/1/4/5. Không phát hiện sai khác trong các mục này. File `DE2_115_UART_pin_map_checked.csv` đính kèm chỉ chứa subset cần dùng; đây chưa phải `.qsf` cho một wrapper đã compile.

Kết nối mục tiêu: FPGA TX=`GPIO[0]/PIN_AB22` tới CP2102 RXD; CP2102 TXD tới FPGA RX=`GPIO[2]/PIN_AB21`; GND chung. CSV chọn 3.3-V LVTTL cho GPIO. [Manual Terasic](https://www.terasic.com.tw/attachment/archive/502/DE2_115_User_manual.pdf) ghi chuẩn I/O GPIO phụ thuộc JP6, nên phải kiểm tra jumper trên board thực tế tương ứng với cấu hình 3.3 V. Chưa quan sát board/jumper/CP2102 của bạn. Thực hiện quy định không nối nguồn CP2102 vào board trong hướng dẫn.

Để chốt Yêu cầu 3 còn cần: wrapper thực thi init/poll/TX/RX/echo, debounce một lần bấm→một byte, hiển thị HEX đúng bit order, reset release đồng bộ và xử lý input bất đồng bộ; project Quartus, pin assignment cho mọi port được giữ lại, clock constraint; compile/fitter/STA và thử truyền hai chiều/echo trên board. Không có Quartus hoặc kết quả nạp board trong lượt kiểm tra này.

**5. “5–8 testbench” nên hiểu thế nào?**

Ảnh đề bài và phần Markdown được cung cấp không ghi con số tối thiểu 5–8 testbench. Những gì thể hiện rõ là SPEC; DV Plan có testcase, UVM, directed/automatic/random/coverage; kiểm thử trên DE2-115. Nếu có rubric khác thì cần đối chiếu thêm rubric đó.

Về kỹ thuật, **một môi trường UVM chạy nhiều testcase** là cách hợp lý; không cần tạo 8 file top-level độc lập. Repo đã có 8 normal test classes và 2 known-gap test classes. Số test chưa thay thế coverage/yêu cầu: 16 mode TX trong một testcase có thể bao phủ nhiều cấu hình, nhưng vẫn cần checker phân biệt được lỗi như trường hợp stop=2 ở R06.

Thứ tự hoàn thiện phù hợp: sửa cú pháp và SPEC DLM → chạy/ghi bằng chứng normal suite, đo baud, ghi known gaps → hoàn thiện test FIFO/IRQ/reset/random và coverage → triển khai/mô phỏng wrapper → Quartus compile/STA → kiểm thử trên DE2-115. Các phép kiểm độc lập của lượt review này là bằng chứng bổ sung, không tự cập nhật trạng thái sign-off trong repo.

**Bàn giao:** báo cáo này, patch sửa cú pháp UVM, bảng pin đã đối chiếu và gói evidence chứa log, VCD, testbench, metadata/hash và script tái lập. Gói evidence không chứa binary build hoặc toàn bộ thư viện UVM. Trạng thái repo gốc vẫn sạch tại thời điểm đối chiếu cuối.
