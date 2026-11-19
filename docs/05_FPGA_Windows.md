# Nạp UART PULP nguyên bản lên DE2-115 bằng Windows

Project, revision và top cùng tên **`de2_115_pulp_uart`**. Chip đích là **Cyclone IV E EP4CE115F29C7**. Mô phỏng chân GPIO chạy với clock thật của thiết kế, 50 MHz, và peer độc lập ở 115200 baud. **Quartus trên Windows, SOF, fitter, TimeQuest, nạp JTAG và thử bo thật của revision này đều `NOT_RUN` tại thời điểm bàn giao.** [Bằng chứng và lệnh chạy Linux](../fpga/evidence/README.md)

## 1. Build đúng revision

Dùng Quartus Prime Lite 25.1std có gói Cyclone IV và driver USB-Blaster. Profile thời gian bên dưới dùng tên góc của 25.1std. Giải nén toàn bộ cây nguồn vào đường dẫn ngắn, ví dụ `C:\uart\main2`. Giữ nguyên vị trí tương đối của `rtl`, `fpga`, `reference`, `tools` và `docs/spec`. Từ PowerShell tại gốc repo, thay đường dẫn ví dụ bằng thư mục thực sự chứa `quartus_sh.exe` và `quartus_sta.exe`.

```powershell
py -3 fpga\scripts\build_windows.py --check-only
py -3 fpga\scripts\build_windows.py --quartus-bin "D:\uart\25.1std\quartus\bin64"
```

Lệnh `--check-only` gọi `tools/check_upstream.py` để đối chiếu SHA-256 và danh mục đủ bảy đầu vào PULP (năm RTL, `src_files.yml`, `LICENSE`) với `docs/spec/baseline_hashes.json`. Lệnh build lặp phép kiểm trên bản chụp mới, trước khi gọi Quartus. Đổi một byte sẽ dừng preflight. [Bộ kiểm nguồn](../tools/check_upstream.py) · [Manifest](spec/baseline_hashes.json)

Preflight đọc từng lệnh trong QSF chính và `pins.qsf`. Thêm một `VERILOG_FILE` ngoài filelist hoặc gán GPIO_UART_RX lần hai sang AB22 sẽ bị chặn cả khi chạy từ ngoài repo. Kết quả `--check-only` chỉ xác nhận đầu vào tĩnh. Khi một tiến trình build trả lỗi, helper giữ nguyên mã thoát và stdout/stderr trong log của bước đó. [Kiểm tra preflight và báo cáo fit](../fpga/sim/test_build_contract.py)

Nếu hai chương trình đã có trên `PATH`, bỏ đối số `--quartus-bin`. Mỗi lần build tạo một thư mục mới `fpga\build\q-…`, chạy `quartus_sh --flow compile de2_115_pulp_uart`, đối chiếu device/top/revision và 65 pad trong báo cáo fitter, rồi chạy `quartus_sta`. Giữ lại cả thư mục được in sau **Fresh run**, kể cả lần lỗi.

| Trong thư mục của lần chạy | Dùng để đối chiếu |
|---|---|
| `inputs.sha256`, `preflight.log`, `version.log`, `compile.log` | Đầu vào đã chụp, kết quả đối chiếu project, phiên bản và toàn bộ thông báo biên dịch |
| `fpga\build\output_files\de2_115_pulp_uart.*` | `.map.rpt`, `.fit.summary`, `.fit.rpt`, `.pin`, `.sta.rpt`, `.asm.rpt`, `.sof` mà lần chạy thực sự tạo được |
| `timequest.log`, `fpga\build\timing\` | Clock, CDC, slack từng góc, reset, mục kiểm tra timing, ngoại lệ, unconstrained paths |
| `sof.sha256` | Hash và đường dẫn SOF sau khi các kiểm tra tự động hoàn tất |

**Qua GUI**, mở `fpga\de2_115\de2_115_pulp_uart.qpf`. Xác nhận chip, top, bảy file SystemVerilog và SDC. Chọn **Processing → Start Compilation**. Khi mở project ngay tại repo, Assembler xuất `fpga\build\output_files\de2_115_pulp_uart.sof`. Từ `fpga\de2_115`, có thể chạy `quartus_sta -t ..\scripts\report_timing.tcl` và dùng `Get-FileHash -Algorithm SHA256 ..\build\output_files\de2_115_pulp_uart.sof`. Project dùng năm file trong manifest PULP tại commit `dfad6e04d19cc9481d3cd2750b45b970dc61271b` và hai file trong `rtl/fpga`. [QSF](../fpga/de2_115/de2_115_pulp_uart.qsf) · [Filelist tương đối, dùng với Verilator -F](../fpga/de2_115/rtl.f)

### Đọc kết quả trước khi nạp

- Trong Analysis & Synthesis, tìm **latch**, **combinational loop** và **fifo_tx_data**. Ở `rtl/vendor/pulp_apb_uart_sv/apb_uart_sv.sv:195`, khối `always_comb` chỉ gán byte khi ghi THR. Verilator báo `LATCH`. Probe Yosys `read_verilog -sv …; proc` dừng với exit 1 ở latch của `fifo_tx_data`. Probe `read_slang; synth_intel -family cycloneive` dừng với exit 1 ở vòng tổ hợp qua `fifo_tx_data[7]`. Ghi lại hành vi thực tế của Quartus, kể cả tên node và mã message. Giữ nguyên RTL, cảnh báo và constraint để truy nguyên. Nếu mapping lỗi hoặc ảnh hưởng latch/loop đến timing còn mở, ghi trạng thái cùng log và dừng trước bước nạp. [Phân tích tổng hợp của PULP](02_Synthesis_Review.md)
- Đọc Fitter Summary và `.pin` của chính lần chạy. Helper đối chiếu tên revision/device trong dòng `CHIP` của `.pin`, 65 pin vật lý và 0 virtual pin trong summary. Cả 65 pad (22 vào, 43 ra) phải có `User Assignment = Y`, đúng hướng, vị trí và I/O standard. File pin từ RC1 sẽ dừng bước kiểm fit dù hai revision dùng chung bảng chân. [Profile chân](../fpga/de2_115/pins.qsf) · [CSV gốc](../reference/DE2_115_pin_assignments.csv)
- TimeQuest phải thấy đúng một `CLOCK_50`, chu kỳ 20 ns. Đọc setup, hold, recovery, removal, minimum pulse width tại **cả ba góc** `7_slow_1200mv_85c`, `7_slow_1200mv_0c`, `MIN_fast_1200mv_0c`. Mỗi mục cần đường đo và slack hữu hạn ≥ 0 ns. Kiểm riêng recovery/removal từ `reset_sync[1]` và setup/hold của 17 cạnh đồng bộ. Lưu các báo cáo kể cả khi script trả lỗi. [Script TimeQuest](../fpga/scripts/report_timing.tcl)
- Đối chiếu `ignored_sdc.rpt`, `unconstrained.rpt`, `check_timing.rpt` và `exceptions.rpt`. Xác minh không có constraint bị bỏ qua, đường chưa ràng buộc, clock thiếu hoặc loop chưa giải quyết. Chỉ miễn trừ từ các pad bất đồng bộ đến tầng bắt đầu, gồm cả KEY0 đến hai FF reset. Các đường sau tầng đầu và đường nhả reset nội bộ phải được phân tích. Chân TX/LED/HEX có budget triển khai 0…20 ns. Khi rà các mục thiếu input/output delay, đối chiếu từng pad với cách lấy mẫu bất đồng bộ và budget này. [SDC](../fpga/de2_115/de2_115_pulp_uart.sdc) · [Danh sách thanh ghi CDC](../fpga/de2_115/synchronizers.qsf)
- Helper chỉ ghi `sof.sha256` sau khi bảng `PULP Check || Summary` có đúng một dòng `loops` và một dòng `latches`, cả hai có 0 vấn đề, cùng các phép kiểm timing đã nêu. Dù TimeQuest trả hai số 0, vẫn đọc toàn bộ message Analysis & Synthesis về latch/loop. [Chính sách kiểm bảng TimeQuest](../fpga/scripts/timing_checks.tcl)

## 2. Đấu dây và nạp SRAM

1. Tắt nguồn bo trước khi đấu dây. Đối chiếu mã chip, hướng chân 1 của **JP5** và vị trí jumper trên bo. Profile cần **JP6 nối 7–8** cho VCCIO4 = 3,3 V và **JP7 nối 5–6** cho VCCIO5/6 = 2,5 V. Kiểm tra mức logic TXD/RXD 3,3 V của module CP2102 đang dùng. [Terasic DE2-115 User Manual, hình 4-15, bảng 4-8, 4-11 và 4-12](https://www.terasic.com.cn/attachment/archive/502/DE2_115_User_manual.pdf)
2. Nối **CP2102 TXD → JP5 chân 3 / GPIO[2] / AB21** (FPGA RX). Nối **CP2102 RXD ← JP5 chân 1 / GPIO[0] / AB22** (FPGA TX). Nối **GND ↔ JP5 GND** (chân 12 hoặc 30). Để hở dây nguồn 3V3/5V của CP2102. Bo dùng nguồn riêng. Dùng ngõ UART mức logic ở JP5.
3. Đặt công tắc **RUN/PROG (SW19) → RUN**, cấp nguồn và cắm cáp vào cổng **USB-Blaster**. Trong Quartus, mở **Tools → Programmer → Hardware Setup**, chọn cáp, chọn **JTAG** và **Auto Detect**. Đối chiếu thiết bị EP4CE115 trong chain. Có thể chạy `jtagconfig.exe` trong thư mục bin để kiểm tra cáp/driver.
4. Gán đúng SOF của lần build vừa kiểm cho FPGA ở đúng vị trí trong chain. Chọn **Program/Configure → Start**, lưu kết quả **100% Successful** và SHA-256. SOF nạp SRAM có hiệu lực đến khi mất điện. CP2102 dùng riêng cho dữ liệu COM.
5. Mở COM ở **115200, 8 data, 1 stop**, chọn parity theo bảng dưới, tắt RTS/CTS, XON/XOFF và local echo. Chỉ một ứng dụng mở COM. Sau khi cài pySerial, chạy `py -3 host/uart_gui.py --profile pulp`, chọn cổng COM của CP2102 rồi nhấn **Kết nối**. [Hướng dẫn giao diện](../host/README.md)

## 3. Công tắc và đèn

| Tín hiệu | Chức năng trên revision PULP |
|---|---|
| `KEY[0]` | Reset mức thấp, assert bất đồng bộ, nhả qua hai FF. Giữ mode ổn định trước khi nhả. Master chờ đường SW đồng bộ rồi chốt một lần. |
| `SW[14]`, `SW[15]` | SW14 = 0 chọn **8N1**, = 1 chọn **8E1**. SW15 dự phòng, cả `SW14:SW15=10` và `11` chọn even. Đổi mode bằng KEY0. SW[13:8] dự phòng. |
| `SW[7:0]`, `KEY[1]` | Byte gửi tay. Phím mức thấp, cần ổn định 500.000 clock cho cả nhấn và nhả (10 ms mỗi chiều). Mỗi lần nhấn hợp lệ sau init chốt một byte. Giữ phím chỉ gửi một lần. |
| `SW[16]` | Mức 1 tạm dừng chọn lần đọc RBR tiếp theo. Giao dịch đã vào SETUP được hoàn tất. TX tay và byte echo đã cam kết vẫn chạy. |
| `SW[17]` | Mức 1 tại lúc chọn đọc RBR dành một ô echo cho byte đó. Thay công tắc sau khi đã chọn đọc vẫn giữ quyết định cho byte này. |
| `HEX1:HEX0`, `HEX5:HEX4` | Byte SW hiện tại và byte RBR gần nhất, nibble cao ở HEX1/HEX5, hiển thị tích cực thấp. Sau reset RX hiện `00`. |
| `LEDR[4:0]` | Ảnh chụp `LSR[4:0]` ở lần poll gần nhất. LEDR0 = DR, dễ quan sát khi giữ RX. OE/FE/BI thiếu logic phát hiện, PE bị xóa trong IP gốc. Các bit 4…1 quan sát bằng 0 trong các phép thử này. |
| `LEDG[0]`, `LEDG[1]` | Init xong sau write IER. LEDG1 sáng giữ nếu lỗi APB hoặc có lần nhấn khi ô gửi tay đã đầy, xóa bằng reset. Lỗi APB làm master dừng và tắt LEDG0. PULP cố định PREADY=1, PSLVERR=0. |
| `LEDG[2]`, `LEDG[3]`, `LEDG[4]` | Lần lượt là mode even đã chốt, hold RX và echo đã đồng bộ. |
| `LEDG[5]`, `LEDG[6]`, `LEDG[7]`, `LEDG[8]` | Hai bit đầu là ảnh chụp LSR5 (FIFO TX rỗng) và LSR6 (FIFO cùng bộ dịch rỗng). LEDG7 = 0. LEDG8 = `event_o` trực tiếp. Do nối RDA tới TX-empty trong IP, LEDG8 có thể sáng ngay khi RX rỗng. |

Master phát sáu giao dịch ghi theo **offset byte**. Theo thứ tự, `(PADDR, PWDATA)` ở hệ hex là `(03,83) (00,B1) (01,01) (03,03 hoặc 0B) (02,07) (01,05)`. Hai byte divisor ghép thành `0x01B1 = 433`. Với chu kỳ data đo trong mô phỏng là 434 clock, tốc độ danh định bằng 50.000.000 / 434 = **115.207,37 baud** (lệch +0,0064% so với 115200). FCR[2:1] xóa hai FIFO. IER bật bit 0 và 2.

Master chốt PRDATA ở cạnh lên hoàn tất ACCESS, đọc `LSR@05` định kỳ khoảng 100 µs lúc rỗi, poll sớm khi có byte chờ và poll lại ngay sau RBR/THR. `LSR[0]` cho phép đọc RBR, `LSR[5]` cho phép ghi THR kể cả khi bộ dịch TX đang bận. Quyết định đọc/ghi độc lập với IRQ.

## 4. Phiếu nghiệm thu bo

Cửa sổ `host/uart_gui.py --profile pulp` hiển thị tám ca dưới đây. Có thể ghi số đo từng ca và xuất CSV ngay tại bàn. [Chương trình PC](../host/README.md) · [Phiếu 8 ca](07_FPGA_Board_Acceptance.csv)

Tất cả các ca dưới đây đang **`NOT_RUN` trên phần cứng main2**. Mỗi lần thử ghi ngày, người thử, board ID, ảnh jumper/dây, CP2102/COM, chế độ, revision/hash SOF, byte phát/thu theo hex, kết quả và đường dẫn ảnh/log. Đánh dấu `PASS` khi đối chiếu đủ quan sát của ca, `FAIL` khi có sai khác, `NOT_RUN` nếu thiếu thiết bị.

| ID | Thao tác | Quan sát cần lưu |
|---|---|---|
| HW01 | Kiểm jumper, dây, mức logic, JTAG chain, nạp SOF theo mục 2 | Ảnh bo/dây và kết quả Programmer 100%, đúng SOF đã hash |
| HW02 | SW14/16/17=0, nhả KEY1, giữ KEY0 rồi nhả. Đợi ≥1 ms | Sau init LEDG0=1, LEDG1/2=0, HEX5:4=`00`, LEDR0=0. LEDG5/6 sáng khi rỗi. |
| HW03 | Echo tắt, gửi từ PC lần lượt `01`, `55`, mỗi lần quan sát rồi gửi tiếp. Đặt SW=`41` ổn định ≥1 ms, giữ KEY1 ≥20 ms rồi nhả ≥20 ms. Lặp với `A6`. | HEX5:4 hiện `01` rồi `55`. HEX1:0 theo SW. PC thu đúng `41 A6`, một byte mỗi lần bấm, kể cả khi giữ phím lâu. |
| HW04 | 8N1, SW17=1, SW16=0. Gửi gói nhị phân `55 AA 00 FF`, tiếp đến một gói liền `00 01 … 0F`. | Log thu khớp từng gói 4 và 16 byte, đúng thứ tự, không thiếu/thừa. |
| HW05 | SW17=1, SW16=1, gửi `10 20 30 40`. Đợi ≥1 ms, bấm KEY1 với SW=`5A`. Hạ SW16. | Lúc giữ, HEX RX giữ byte cũ, LEDR0 sáng, PC vẫn thu byte tay `5A`. Khi nhả, PC thu `10 20 30 40`, HEX5:4=`40`, sau poll LEDR0 tắt. |
| HW06 | Đặt SW14=1, SW15=1, reset, đặt PC 8E1. Lặp HW03 và HW04, gửi thêm `00 01`. Gạt SW15 và lặp một gói. | LEDG2 sáng. Cả hai chiều và echo đúng byte. Nếu có logic analyzer, parity của `00` là 0, của `01` là 1. |
| HW07 | Khi đang truyền một chuỗi dài, giữ KEY0 rồi ngừng phát PC và để dây RX idle. Nhả KEY0, chờ LEDG0, bắt đầu lượt ghi log mới rồi gửi `5A` với echo bật. | Reset có thể cắt khung đang truyền. Trong lượt mới thu một `5A`, HEX5:4=`5A`, LEDG1 tắt. |
| HW08 (nếu có máy đo) | 8N1, gửi tay `55`, đo GPIO[0] so với GND, ghi tốc độ lấy mẫu. | Khoảng cạnh data danh định 8,680 µs (434 clock). Start đầu 8,700 µs (435 clock). Đối chiếu dung sai dao động và độ phân giải máy đo. |

FIFO RX có 16 mục. Trong một kích thích xác định (giữ RX, 18 khung `40…51` với bit 8,680 µs và thêm một bit idle mỗi khung), mô phỏng trả `40…50`. Trong khi byte thứ 17 chờ tại `SAVE_DATA`, RX bỏ qua start tiếp theo. Với CP2102, lịch phát thực tế có thể khác. Dùng gói ngắn như HW05 để quan sát riêng chức năng hold trên bàn. RTL lưu byte trước pha parity và giữ `err_clr_i=1`, nên tiêm sai parity có thể vẫn nhận/echo byte với PE=0. Profile cung cấp hai chế độ N/E. [Log mô phỏng trên chân](../fpga/evidence/board.log)
