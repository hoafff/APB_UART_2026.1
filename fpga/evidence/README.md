# Bằng chứng FPGA main2 trên Linux

**DUT** là board top `de2_115_pulp_uart` với năm RTL gốc của PULP `dfad6e04d19cc9481d3cd2750b45b970dc61271b` và hai RTL tích hợp. Bảng dưới đây tóm tắt lần chạy lịch sử trong `board.log` và `static.log`, với HEAD nền `407b29c08f1a724980ac183081eac01e45bcdd5a` và phần FPGA trong working tree lúc đó. Manifest của lần chạy ấy có ở `git show 5d96a7f:fpga/evidence/inputs.sha256`. Manifest trong cây hiện tại nhận dạng các script và test đã cập nhật. [Danh mục hash hiện tại](inputs.sha256)

| Phép kiểm | Kết quả đã chạy |
|---|---|
| `SYS-01…03`, `BAUD-02`, mô phỏng chân bo | **9 ca**, ba lần init. Tại cạnh lên quan sát **44.630 SETUP, 44.630 ACCESS**, gồm 18 init write, 44.200 LSR, 205 RBR và 207 THR. Peer độc lập giải mã **206 khung TX hoàn chỉnh**, một khung còn lại bị reset có chủ ý. |
| Truyền liên tiếp | Gói **4, 16 và 64 byte** liền nhau ở 115200 trong từng mode 8N1 và 8E1, không chèn idle ngoài stop bit. Mỗi gói echo đúng số lượng, giá trị và thứ tự. Ở 8E1 quan sát parity 0 và 1 trên TX. |
| Baud, phím, hold, giới hạn IP | `55` có start 8.700 ns, tám khoảng cạnh tiếp theo mỗi khoảng 8.680 ns (434 clock). Chạy debounce đủ 500.000 clock, poll mặc định 5.000 clock. Giữ RX đầy 16 mục vẫn gửi tay được. Ca `FIFO-04` giữ 18 khung có timing xác định rồi đọc lại 17 byte. Khung sai parity vẫn được nhận với PE=0. |
| Master độc lập | **5 ca, 21 giao dịch, 24 cạnh ACCESS chờ**. Kiểm dữ liệu chỉ lấy ở cạnh hoàn tất, echo đã cam kết, hai yêu cầu cạnh tranh, nạp lại ô phím cùng cạnh tiêu thụ, báo đầy và dừng khi PSLVERR ở init/runtime. |
| Độ nhạy oracle | Lặp với `+negative-pin`. Riêng phía giải mã TX kỳ vọng `54` trong khi kích thích và APB vẫn đúng `55`. Test dừng ở thông báo `TX pin expected 54 got 55` với exit 1. |
| `BOARD-01/02`, kiểm tĩnh | Khớp 65 pad (22 vào, 43 ra) và I/O standard của CSV Terasic. 130 assignment vật lý khớp project tham chiếu. Elaboration tìm được một clock, 31 thanh ghi CDC thuộc 14 chuỗi và 17 cạnh nối. Chạy Tcl SDC trên tên RTL, kiểm 15 đường miễn trừ pad→FF và 43 budget output. |
| Kiểm script build | Bản sao ở đường dẫn có dấu cách vượt `--check-only` từ ngoài repo. Thay một byte trong `uart_tx.sv` bị chặn ở checkout và ở bản chụp trước Quartus. 20 fixture Tcl kiểm đủ ba góc, số path và slack hữu hạn ≥ 0. |
| `BOARD-02/03`, Windows và phần cứng | **NOT_RUN** cho Quartus, fitter, TimeQuest, SOF, nạp JTAG và UART vật lý của revision này. |

Testbench có clock 20 ns và driver RX theo thời gian riêng `1 s / 115200`. Monitor TX phát hiện cạnh start rồi lấy mẫu giữa bit. Scoreboard APB độc lập quan sát bus tại cạnh lên trước khi FIFO đổi đầu đọc. Toàn bộ ca board dùng tham số sản xuất. Ca master nối responder có thể giữ PREADY hoặc phát PSLVERR. [Log Verilator nguyên lần chạy](board.log) · [Lệnh, phiên bản và kiểm tĩnh](static.log)

## Rà soát tổng hợp và guard trên nền `5d96a7f`

Archive chứa 21 lệnh cùng mã thoát, phiên bản tool, log gốc và SHA-256. Ba probe strict đều trả 1 ở cả lõi và board top. Luồng `sv2v` → Yosys generic giữ đủ 8 latch, so sánh được 83.968 mẫu cổng trên lõi. Backend Cyclone IV E của Yosys trả 1 khi legalize latch. [Archive bằng chứng](synthesis-review.zip) · [Kết quả, giới hạn và lệnh tái lập](../../docs/02_Synthesis_Review.md)

Fixture Python chạy helper thực với `--check-only` trên cây có dấu cách, kiểm các phản ví dụ về QSF/pin, giải mã summary/`.pin` dạng CRLF và xác minh tiến trình con trả 37 thì helper giữ 37 cùng log gốc. Fixture Tcl bổ sung bảy trường hợp cho hai dòng `loops/latches` bên cạnh 20 trường hợp góc, path và slack. Đây là kiểm tra parser và điều kiện dừng trên Linux. [Fixture Python](../sim/test_build_contract.py) · [Fixture Tcl](../sim/test_timing_checks.tcl)

## Tái lập từ gốc repo

```bash
EDA="$HOME/.local/bin/ic-eda"
python3 fpga/scripts/build_windows.py --check-only
python3 fpga/sim/run.py --ic-eda "$EDA"
mkdir -p fpga/build
"$EDA" yosys -m slang -Q -T -q -p 'read_slang --top de2_115_pulp_uart -F fpga/de2_115/rtl.f; memory_collect; write_json fpga/build/board.json'
python3 fpga/scripts/check_project.py --netlist fpga/build/board.json
python3 fpga/sim/test_upstream_guard.py
python3 fpga/sim/test_build_contract.py
tclsh fpga/sim/test_timing_checks.tcl
sha256sum -c fpga/evidence/inputs.sha256
```

`run.py` chạy Verilator `--binary --timing --assert --timescale 1ns/1ps` với top `tb_de2_115_pulp_uart` và `-F fpga/de2_115/rtl.f`, sau đó chạy top `tb_de2_pulp_uart_master`. Log biên dịch, mô phỏng và negative control được giữ trong thư mục riêng dưới `fpga/build`. `--netlist` dùng Tcl qua Python tkinter để đối chiếu các ràng buộc trước technology mapping. Bước preflight Windows dùng thư viện chuẩn Python và manifest trong repo.

Pin đối chiếu độc lập ở lần bàn giao đến từ `rc1-verified/fpga/de2_115/pins.qsf` và `rc1-verified/build/fpga/output_files/de2_115_apb_uart.pin`. So sánh 130 dòng assignment theo thứ tự sau chuẩn hóa xuống dòng, rồi dùng `check_pad_report` kiểm tên, hướng, location, I/O standard trong file fitted tham chiếu. Hash hai đầu vào tham chiếu nằm trong log tĩnh. Giữ riêng mọi kết quả PPA/timing của revision cũ.

Verilator báo latch của `uart.fifo_tx_data` tại `apb_uart_sv.sv:195`. Slang báo nhánh reset thiếu giá trị cho một phần `uart.regs_q` khi xuất netlist. Các probe tổng hợp Yosys độc lập của repo có kết quả lỗi đã ghi nhận. Bước đối chiếu topology ở đây chỉ cần elaboration và không tạo netlist Quartus sau fit. [Phân tích tổng hợp](../../docs/02_Synthesis_Review.md) · [Quy trình Windows và phiếu nghiệm thu](../../docs/05_FPGA_Windows.md)
