# APB UART trên DE2-115

Đồ án tích hợp một UART trên bus APB với kit DE2-115. Sau khi nạp FPGA, máy tính gửi và nhận từng byte qua CP2102. Nhánh `main` dùng thiết kế TARGET-v1.0. Nhánh `main2` dùng thanh ghi và bộ chia baud của lõi PULP gốc.

**Báo cáo** trình bày sơ đồ luồng dữ liệu, ba yêu cầu của đề và kết quả đo. [Đọc báo cáo](docs/BAO_CAO.md)

| Yêu cầu | Kết quả trên `main` | Tài liệu |
|---|---|---|
| 1. Đặc tả hệ thống | 80 yêu cầu, bản đồ thanh ghi, giao thức APB, FIFO, ngắt và 65 chân FPGA | [Đặc tả TARGET-v1.0](docs/01_System_Specification.md) · [Thay đổi so với PULP](docs/04_RTL_Changes.md) |
| 2. Kiểm chứng | 15/15 lượt UVM, 3/3 mô phỏng bổ sung, phát hiện cả hai lỗi cố ý. Đã kích hoạt 833/833 bin chức năng trong mô hình | [Kế hoạch DV](docs/03_DV_Plan.md) · [Kết quả và độ phủ](docs/dv/RESULTS.md) |
| 3. Triển khai FPGA | RC1 đã qua Quartus Lite 25.1 trên Windows, fitter và STA ở ba góc. Có file nạp SRAM. 14 mục thử trên bo đang chờ thực hiện | [Project Quartus](fpga/de2_115/de2_115_apb_uart.qpf) · [Nạp và thử bo](docs/06_FPGA_Implementation.md) · [Phiếu thử](docs/07_FPGA_Board_Acceptance.csv) |

## Chạy thử với CP2102

Dùng USB-Blaster nạp `de2_115_apb_uart.sof` trong Release RC1. Kiểm tra jumper, mức logic và dây TX/RX/GND theo hướng dẫn nạp trước khi cấp nguồn. Để SW14=0, SW16=0, bật SW17 rồi nhấn và nhả KEY0. Khi LEDG0 sáng, mở menu ở 115200 baud, 8N1. [Tải SOF và báo cáo Quartus](https://github.com/hoafff/APB_UART_2026.1/releases/tag/v1.0.0-fpga-rc1)

**Windows** · Mở PowerShell tại thư mục gốc của nhánh.

```powershell
py -3 -m pip install pyserial==3.5
py -3 host/uart_menu.py --profile target
```

**Linux** · Cài pySerial cho Python của dự án một lần rồi chạy menu.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install pyserial==3.5
.venv/bin/python host/uart_linux.py --profile target
```

Chọn `c` để mở cổng CP2102, chọn `e` và nhập `55 AA 00 FF`. Khi FPGA trả về đúng bốn byte, menu báo `MATCH`. Để thử chiều FPGA → PC, đặt SW[7:0] = `41`, chọn `r` rồi nhấn KEY1. [Các phím và cách lưu log](host/README.md)

## Đối chiếu kết quả

Từ checkout trên Linux, chạy ba lệnh sau để kiểm đặc tả, kế hoạch DV và dữ liệu mô phỏng đã lưu.

```sh
python3 tools/check_spec.py
python3 tools/check_dv.py
python3 tools/check_published_evidence.py
```

Lệnh cuối đối chiếu các log, dữ liệu coverage và mã nguồn đi kèm. Để mô phỏng lại, dùng Verilator theo hướng dẫn DV. Bài kiểm tra menu trên Linux nối một cổng serial ảo với hai chân UART của top FPGA. [Chạy UVM](dv/README.md) · [Thử menu với RTL](integration/README.md)
