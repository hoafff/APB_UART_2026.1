# Bàn giao Yêu cầu 3 sang Windows 11

Ngày ghi nhận: 12/11/2026. Chủ dự án quyết định dùng **Windows 11 trên cùng máy tính
đang dual boot Arch Linux / Windows 11**, do phân vùng Linux thiếu dung lượng cho
Quartus. Đây là ghi chú kế hoạch; chưa xác nhận đã cài công cụ hoặc kết nối bo trên Windows.

## 1. Mốc được bàn giao

- [SPEC TARGET-v1.0](01_System_Specification.md) là hợp đồng thiết kế đang dùng.
- [DV Plan](03_DV_Plan.md), [kết quả Linux](dv/RESULTS.md) và
  [lần review bổ sung](dv/REVIEW_2026-11-12.md) chứa bằng chứng Yêu cầu 1–2.
- RTL đã qua mô phỏng nằm trong `rtl/modified/pulp_apb_uart_sv/`; wrapper/master nằm
  trong `rtl/fpga/`. Baseline `rtl/vendor/` được giữ để đối chiếu nguồn gốc.
- Yêu cầu 3 vẫn **NOT_RUN / HW_PENDING**: chưa có project Quartus, báo cáo fitter/STA,
  bitstream `.sof` hoặc log thử bo DE2-115 + CP2102.

## 2. Tiếp nhận repo trên Windows

Clone repo ở phân vùng Windows còn đủ dung lượng; dùng revision mới nhất đã push:

```powershell
git clone https://github.com/hoafff/APB_UART_2026.1.git
cd APB_UART_2026.1
git rev-parse HEAD
git status --short
py -3 -X utf8 tools/check_spec.py
py -3 -X utf8 tools/check_dv.py
```

Hai lệnh kiểm tài liệu dùng Python 3.10 trở lên nếu đã cài; `-X utf8` bảo đảm đọc đúng
tài liệu tiếng Việt dù Windows dùng code page khác. Chúng không thay cho compile/simulation.
`.gitattributes` giữ LF cho source và giữ nguyên byte CSV/raw logs để hash không đổi
khi Git for Windows bật `core.autocrlf`. Không sửa hash baseline để bỏ qua một lỗi checkout.
Việc chuyển đổi xuống dòng đã được kiểm bằng Git trên Linux; Python/Quartus thực thi
trên Windows vẫn phải kiểm tại môi trường mới.

Môi trường UVM hiện được nghiệm thu trên Linux. Các script Bash và runner có phụ thuộc
Unix không phải lệnh PowerShell chạy trực tiếp. Yêu cầu 3 có thể dùng Quartus native
Windows độc lập với runner UVM; nếu cần chạy lại UVM ở Windows phải chọn và kiểm riêng
luồng simulator đó, không đổi nhãn kết quả Linux thành kết quả Windows/Questa.

## 3. Công cụ cần chuẩn bị trên Windows

| Thành phần | Công việc | Bằng chứng cần có |
|---|---|---|
| Quartus Prime Lite và gói Cyclone IV | Chọn phiên bản có hỗ trợ Windows 11 và Cyclone IV E; kiểm dung lượng trước khi cài | Ghi version; chọn được `EP4CE115F29C7` |
| Programmer và driver USB-Blaster | Nạp FPGA qua cổng USB-Blaster/JTAG của bo | Device Manager nhận thiết bị; Programmer/`jtagconfig` quét được chain |
| Driver CP210x và terminal UART | Giao tiếp dữ liệu qua CP2102 | Nhận cổng COM; terminal cấu hình baud/parity/flow control đúng |
| Python + pyserial, nếu dùng | Tự động gửi/nhận và ghi log trên COM | Script thực tế chạy được; không bắt buộc khi thử tay bằng terminal |

USB-Blaster là đường nạp FPGA. CP2102 là đường trao đổi UART sau khi nạp. Driver và
ứng dụng đã có ở Arch không tự được cài sang Windows khi chuyển hệ điều hành.

## 4. Project Quartus cần tạo

Chip: **Cyclone IV E / EP4CE115F29C7**. Top: **`de2_115_apb_uart_bringup`**.
Clock: **50 MHz**, chu kỳ yêu cầu **20 ns**. Source SystemVerilog của phiên bản hiện tại:

```text
rtl/modified/pulp_apb_uart_sv/uart_fifo.sv
rtl/modified/pulp_apb_uart_sv/uart_tx.sv
rtl/modified/pulp_apb_uart_sv/uart_rx.sv
rtl/modified/pulp_apb_uart_sv/apb_uart_sv.sv
rtl/fpga/de2_uart_controller.sv
rtl/fpga/de2_115_apb_uart_bringup.sv
```

Không đưa `dv/` hoặc baseline vendor vào danh sách tổng hợp TARGET. IRQ được tích hợp
trong bản target và FIFO đã đổi module; danh sách trên khác tên file của baseline trong guide.

Cần tạo `.qpf`, `.qsf`, `.sdc`: gán đủ 65 bit port từ SPEC và `docs/spec/pins.json`,
đối chiếu `reference/DE2_115_pin_assignments.csv`, thêm clock/CDC/reset constraints theo
mục 11 của SPEC. Chưa có bộ constraints được Quartus kiểm chứng ở mốc bàn giao này.

## 5. Checklist tiếp tục Yêu cầu 3

| Việc cần làm | Điều kiện đạt | Trạng thái |
|---|---|---|
| Cài Quartus/device support/driver trên Windows | Tool chạy, chọn đúng chip, nhận USB-Blaster và COM | NOT_RUN |
| Tạo project và constraints | Đúng top/filelist; đủ pin, I/O standard, clock/CDC/reset constraints | NOT_RUN |
| Compile, fitter và STA | Không lỗi, review latch/CDC/unconstrained paths; synchronous timing đạt 50 MHz | NOT_RUN |
| Tạo/nạp `.sof` | Ghi tên bitstream, commit RTL, version Quartus; Programmer báo thành công | NOT_RUN |
| Thử board + CP2102 | TX, RX, echo, hold-RX/overrun, N/O/E, lỗi phù hợp; log/capture theo SPEC | NOT_RUN |

Trước đấu UART, kiểm JP6/mức logic GPIO và CP2102 thực tế theo mục 12 SPEC; nối chéo
TX/RX và GND chung, không nối chân nguồn CP2102 sang bo. Profile mặc định: terminal
**115200, 8N1**, flow control tắt; chọn parity bằng SW14/15 trước reset khi thử 8O1/8E1.
Mọi kết quả phần cứng phải ghi mới từ phép thử thực tế, không lấy simulation PASS để đóng mục FPGA.
