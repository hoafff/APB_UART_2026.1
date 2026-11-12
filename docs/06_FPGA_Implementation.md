# Yêu cầu 3 — gói nạp SRAM DE2-115

Trạng thái bàn giao ngày **12/11/2026**: **SOFTWARE_READY / HARDWARE_PENDING**.
Project Quartus, fitter, assembler, STA và mô phỏng wrapper được chạy thật trên
Windows. Việc nạp DE2-115 và thử CP2102 chưa thực hiện. `jtagconfig` trả về
`No JTAG hardware available`; máy không liệt kê cổng COM tại lúc kiểm tra.

## 1. Mở và kiểm tra gói

Repo làm việc: `D:\uart\APB_UART_2026.1`, nhánh `codex/yc3-fpga-ready`.
Quartus Lite: `D:\uart\25.1std\quartus\bin64`.
Giải nén gói vào một thư mục có quyền ghi nếu dùng trên máy khác.

```powershell
Set-Location D:\uart\APB_UART_2026.1
python -X utf8 tools/build_fpga.py verify
```

Python **3.11 trở lên**, chỉ dùng thư viện chuẩn. Có thể thay `python` bằng
`py -3.11`. Lệnh `verify` không cần Quartus/Git, kiểm toàn bộ hash đã niêm phong,
65 chân sau fitter, ba corner timing và cảnh báo. Thành công phải có
`RELEASE_VERIFY_PASS ... BOARD_NOT_TESTED`. Nếu FAIL, không dùng bitstream đó;
khôi phục gói nguyên vẹn hoặc build lại từ nguồn đã được review.

| Thành phần | Đường dẫn trong gói/repo |
|---|---|
| Mở bằng Quartus GUI | `fpga/de2_115/de2_115_apb_uart.qpf` |
| File nạp SRAM | `build/fpga/output_files/de2_115_apb_uart.sof` |
| Hash nguồn/cấu hình/SOF/báo cáo, version và verdict | `build/fpga/release_manifest.json` |
| Báo cáo Quartus nguyên bản | `build/fpga/output_files/` |
| STA từng corner, chuỗi đồng bộ, ngoại lệ | `build/fpga/reports/` |
| Nhật ký build/kiểm tra/mô phỏng | `build/fpga/logs/` |
| Phiếu thử bo còn để NOT_RUN | `docs/07_FPGA_Board_Acceptance.csv` |

Archive có `PACKAGE_SHA256.json` cho mọi file được đóng gói và file SHA-256 cạnh
ZIP. Hash phát hiện thay đổi file; đây không phải chữ ký số xác thực người phát hành.
Các database Quartus, bộ cài, license và phần mềm Questa không nằm trong gói.

## 2. Build lại

```powershell
python -X utf8 tools/build_fpga.py build --quartus-bin D:\uart\25.1std\quartus\bin64 --questa-bin E:\Apps\QuestaSim-10.7c\win64
python -X utf8 tools/build_fpga.py verify
python -X utf8 tools/build_fpga.py package --output D:\uart\work\APB_UART_DE2_115_new.zip
```

`--questa-bin` là tùy chọn và phải trỏ tới bản Questa có license hợp lệ. Bỏ tùy
chọn này vẫn chạy đầy đủ Quartus nhưng ghi simulation của lần build đó là
`NOT_RUN`. Không cài thêm simulator và không thay thế kết quả UVM Linux bằng
nhãn Questa Windows. `package` cần chạy trong **Git checkout** (ZIP giải nén
không có `.git`), ghi file ZIP mới ngoài repo và từ chối
ghi đè archive đang có. Chạy build trực tiếp bằng GUI không cập nhật manifest:
phải chạy lệnh build ở trên để tạo lại gói có bằng chứng đồng bộ.

Flow tự chạy kiểm SPEC/DV, unit test bộ phát hành, Quartus project preflight,
full compile, post-fit audit, rồi mô phỏng nếu được chọn. Manifest cũ bị vô hiệu
ngay khi bắt đầu; build lỗi hoặc bị ngắt không được giữ verdict PASS cũ.
Nguồn/cấu hình được hash trước và sau build. Không có thao tác nạp bo, ghi flash,
push hoặc publish trong script. Profile cảnh báo được review cho Quartus Lite
**25.1std.0 Build 1129**; phiên bản khác phải được review lại.

## 3. Bằng chứng đã kiểm

- Device `EP4CE115F29C7`, top `de2_115_apb_uart_bringup`, đúng sáu file TARGET/wrapper.
- 65 bit port: 22 input, 43 output; JSON, CSV Terasic, RTL, assignment Quartus và
  file `.pin` sau fitter khớp. TX = AB22, RX = AB21, CLOCK_50 = Y2, KEY0 = M23.
- Fitter: 1.422 logic elements, 667 registers, 0 PLL, 0 embedded memory bits.
- Một clock CLOCK_50, 50 MHz / 20 ns; không có latch hoặc clock không xác định.
- 33 thanh ghi trong 18 cạnh chuỗi đồng bộ được kiểm setup/hold ở cả ba corner.
  Quartus nhận 15 synchronizer chains. Chỉ cắt input bất đồng bộ tới tầng đầu;
  recovery/removal từ `reset_sync[1]` tới logic nội bộ vẫn được kiểm.
- Không có unconstrained path và không có SDC bị bỏ qua. 15 input async và 43
  output không có ngoại vi đồng bộ được kiểm theo danh sách tên chính xác.
  Output có budget min/max 0..20 ns; đó không phải thông số setup/hold của CP2102.

Worst slack sau fitter, đơn vị ns (số liệu đầy đủ trong `reports/timing.tsv`):

| Corner | Setup | Hold | Recovery | Removal | Minimum pulse width |
|---|---:|---:|---:|---:|---:|
| Slow 1200 mV 85°C | 5.016 | 0.401 | 13.217 | 5.997 | 9.676 |
| Slow 1200 mV 0°C | 6.335 | 0.353 | 13.867 | 5.428 | 9.688 |
| Fast 1200 mV 0°C | 12.177 | 0.181 | 16.262 | 3.077 | 9.264 |

Setup gồm cả output budget. Không coi MTBF do công cụ ước tính là đo tuổi thọ
thực tế; tốc độ đổi input và điều kiện điện trên bo còn phải kiểm.

Mô phỏng Questa của các testbench hiện hữu: system 4.027.274 checks, controller
46 checks, TX onehot 2.361 checks / 192 frames, không lỗi. Unit test phát hành
thử cả dữ liệu bị lỗi: thiếu báo cáo/corner/category/chain, slack âm/NaN/Inf,
sai pin, warning mới và file bị thay đổi. Kết quả cụ thể nằm trong log cùng gói.

`tools/check_spec.py` và `tools/check_dv.py` đạt. Toàn bộ `unittest discover -s
tools/tests` trên Windows có **một module cũ không import được**:
`test_report_dv` → `run_dv.py` → `resource` (module chỉ có trên Unix).
Đây là giới hạn runner DV cũ, được giữ nguyên để không thay nguồn/bằng chứng
Yêu cầu 1–2. Bộ test phát hành FPGA chạy riêng, không bỏ qua lỗi của nó.

## 4. Review 20 cảnh báo Quartus

Không có Error hoặc Critical Warning. Không che warning bằng bộ lọc Quartus.

| ID / số lần | Đánh giá và điều kiện |
|---|---|
| 10335 / 3 | Quartus không nhận thuộc tính `async_reg` trong RTL. QSF dùng thuộc tính Quartus tương ứng; kiểm post-fit xác nhận giữ đúng 33 register, topology và timing từng cạnh. Giữ nguyên RTL đã qua DV. |
| 13024 / 1, 13410 / 6 | LEDG[7:2] được SPEC quy định luôn 0. Không có output chức năng khác bị constant. |
| 21074 / 1, 15610 / 6 | SW[13:8] là sáu input dự phòng, không điều khiển logic. |
| 292013 / 1 | LogicLock cần subscription; thiết kế không sử dụng region LogicLock. Full compile Lite vẫn thành công. |
| 15714 / 1 | 43 output dùng mặc định drive strength; 28 output 2.5 V còn dùng slew mặc định. Không phải thiếu location/I/O standard. Báo cáo Output Pins ghi 3.3-V LVTTL 8 mA, nhóm 2.5 V theo mặc định/series termination và slew 2. Giữ profile hiện hữu; kiểm mức điện/sườn tín hiệu khi có bo, không tự chọn dòng để chỉ xóa warning. |
| 169177 / 1 | CLOCK_50 và GPIO_UART_RX là input 3.3-V LVTTL. Điều kiện điện áp/overshoot của Cyclone IV theo AN447 còn thuộc nghiệm thu phần cứng. |

Fitter báo unused pins là **input tri-state với weak pull-up**; không được mô
tả thành ngõ ra GND hoặc tri-state không có pull-up. Không cắm thêm peripheral
vào header khi thử nghiệm UART ban đầu. Tham chiếu điều kiện giao tiếp:
[Altera AN447](https://docs.altera.com/r/docs/683295/current/an-447-interfacing-fpga-devices-with-3.3/3.0/2.5-v-lvttl/lvcmos-i/o-systems).

## 5. Chuẩn bị bo và nối dây

Tắt nguồn khi kiểm/chuyển jumper và đấu dây. Xác minh bo DE2-115 dùng đúng
EP4CE115F29C7, vị trí pin 1/header và các jumper trên chính bo mượn.

- JP7 nối **5–6 = 2.5 V** (VCCIO5/6); JP6 nối **7–8 = 3.3 V** (VCCIO4).
- CP2102 phải có **logic UART 3.3 V** phù hợp; nhãn chân nguồn 3V3 không tự
  chứng minh mức TXD. Kiểm tài liệu/module và đo khi cần. Không dùng RS-232 ±V.
- Nối CP2102 **TXD → GPIO[2] / FPGA AB21**, **RXD ← GPIO[0] / FPGA AB22**,
  **GND ↔ GND**. GPIO[0] và GPIO[2] là tên tín hiệu, không phải số chân header.
  Đối chiếu sơ đồ header của đúng bo; không đếm pin theo hướng nhìn tùy ý.
- Không nối chân nguồn 3V3/5V CP2102 sang bo. Bo dùng nguồn riêng đúng hướng dẫn.
- Nạp qua USB-Blaster của bo; CP2102 dùng truyền dữ liệu, không dùng nạp FPGA.

Nguồn mapping/jumper/header: [Terasic DE2-115 User Manual, bảng 4-8 và
4-11](https://www.terasic.com.tw/attachment/archive/502/DE2_115_User_manual.pdf),
CSV nguyên bản và SPEC §12–13 trong gói. Ghi jumper, điện áp và ảnh vào phiếu
nghiệm thu; các mục này hiện là NOT_RUN.

## 6. Nạp bằng Quartus Programmer

1. Kết nối nguồn và USB-Blaster theo manual; kiểm driver nhận thiết bị. Chạy
   `D:\uart\25.1std\quartus\bin64\jtagconfig.exe` để đọc chain.
2. Mở project `.qpf`, vào **Tools → Programmer**, chọn **Hardware Setup →
   USB-Blaster** và **Mode: JTAG**. Chọn Auto Detect, xác nhận chip EP4CE115.
   Nếu chip/chain khác dự kiến thì dừng để đối chiếu bo.
3. Gán `.sof` trong `build/fpga/output_files/` vào đúng FPGA. Chọn
   **Program/Configure**, nhấn **Start**, lưu ảnh/log khi báo **100% Successful**.
   Nếu có nhiều thiết bị trong chain, chọn đúng FPGA, không mặc định vị trí đầu.
4. Đây là nạp SRAM tạm thời, mất khi tắt nguồn; không dùng `.pof`, `.jic` hoặc
   thao tác ghi flash. Mở terminal CP2102 ở cổng COM thực tế, **115200, 8N1**,
   hardware/software flow control tắt, local echo tắt.
5. Ban đầu để SW14=0, SW16=0, SW17=0. Giữ mode switch ổn định ≥1 ms, nhấn
   KEY0 ít nhất 1 µs rồi nhả (nhấn tay thông thường đủ lâu). Sau init,
   LEDG0 sáng, LEDG1 tắt; phải reset sau mỗi lần nạp, không dựa vào power-up FF.

## 7. Thử chức năng và lưu kết quả

| Thử | Thao tác | Kết quả mong đợi, chưa phải kết quả đo |
|---|---|---|
| PC → FPGA | Gửi riêng byte `41` hex (`A`) | HEX5:HEX4 = `41` |
| FPGA → PC | Đặt SW[7:0]=`41`, giữ ổn định ≥1 ms; nhấn/nhả KEY1 ≥10 ms | PC nhận đúng một `A`; giữ KEY1 không lặp gửi |
| Echo | SW17=1, gửi `55 AA 00 FF` ở chế độ gửi hex/raw | PC nhận lại đúng thứ tự; local echo terminal tắt |
| Hold/overflow | SW16=1, gửi 17 byte, chờ poll; rồi SW16=0 | LEDR1 (OE sticky) sáng; TX vẫn hoạt động; các byte giữ trong FIFO được đọc tiếp |
| Odd parity | SW14=1, SW15=0 trước KEY0; terminal 115200 8O1 | TX/RX/echo đúng, LEDR2 không báo PE với frame hợp lệ |
| Even parity | SW14=1, SW15=1 trước KEY0; terminal 115200 8E1 | TX/RX/echo đúng, LEDR2 không báo PE với frame hợp lệ |
| PE injection | Chọn parity trái nhau ở bo và terminal, gửi byte đã biết | LEDR2 (PE sticky) sáng; reset để xóa |
| FE/BI | Dùng nguồn phát có khả năng điều khiển stop/break và mức điện đã kiểm | LEDR3/4 theo SPEC; không mặc định terminal nào cũng tạo được fault |
| Reset | KEY0 khi idle và khi có traffic | LED lỗi xóa, init chạy lại, UART phục hồi sau khi đồng bộ mode |

HEX1:HEX0 hiển thị SW TX; HEX5:HEX4 hiển thị byte RX mới nhất. LEDR[4:1]
lần lượt BI/FE/PE/OE sticky; LEDR0 là DR snapshot, LEDG8 là IRQ trực tiếp.
Không đo baud từ số cài terminal: danh định 50 MHz / (16×27) = 115740.74 baud,
lệch khoảng +0.469% so với 115200; oscillator thực tế vẫn chưa đo.

Điền thời điểm, người thử, board/module ID, SHA-256 `.sof`, cấu hình terminal,
byte gửi/nhận và đường dẫn ảnh/log vào CSV. Mục không đủ thiết bị fault injection
giữ `NOT_RUN`, mục khác kết quả mong đợi ghi `FAIL`. Chỉ đóng Yêu cầu 3 hoàn toàn
khi có đủ bằng chứng phần cứng; compile và simulation không thay thế việc này.
