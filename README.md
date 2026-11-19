# APB UART PULP trên DE2-115

Nhánh `main2` dùng lõi APB UART của ETH Zürich và Đại học Bologna ở commit `dfad6e0`. Năm file SystemVerilog, danh sách nguồn và giấy phép khớp từng byte với upstream. Bộ điều khiển APB, khối giao tiếp DE2-115, môi trường kiểm chứng và chương trình PC nằm ngoài thư mục RTL gốc. [Mã nguồn PULP](https://github.com/pulp-platform/apb_uart_sv/tree/dfad6e04d19cc9481d3cd2750b45b970dc61271b)

**Báo cáo** giải thích cách đặt baud, địa chỉ thanh ghi, các đặc điểm của FIFO và ngắt, và kết quả từng yêu cầu. [Đọc báo cáo](docs/BAO_CAO.md)

| Yêu cầu | Kết quả trên `main2` | Tài liệu |
|---|---|---|
| 1. Đặc tả hệ thống | 31 yêu cầu dựa trên hành vi của RTL PULP. LCR ở `0x03`, LSR ở `0x05`. Ở 50 MHz, bộ chia 433 cho 434 clock mỗi bit dữ liệu | [Đặc tả](docs/01_System_Specification.md) · [Đối chiếu hướng dẫn môn học](docs/00_RTL_Guide_Discrepancies.md) |
| 2. Kiểm chứng | 10/10 lượt UVM chức năng đạt, một lần chạy lại cùng seed, hai lỗi cố ý đều bị phát hiện. Đã kích hoạt 117/117 bin chức năng | [Kế hoạch DV](docs/03_DV_Plan.md) · [Kết quả](docs/DV_RESULTS.md) |
| 3. Triển khai FPGA | Có project cho EP4CE115F29C7, kiểm 65 chân, mô phỏng top và chương trình PC. Chờ build Quartus trên Windows, timing và thử trên bo | [Project](fpga/de2_115/de2_115_pulp_uart.qpf) · [Quy trình Windows và phiếu thử](docs/05_FPGA_Windows.md) |

## Build và chạy với CP2102

Mở project `de2_115_pulp_uart` trong Quartus Prime Lite có hỗ trợ Cyclone IV E. Kiểm tra báo cáo tổng hợp, fitter và timing 50 MHz của lần build. Yosys phát hiện latch trên đường dữ liệu TX của IP khi kiểm trực tiếp mã gốc. [Hướng dẫn build](docs/05_FPGA_Windows.md) · [Kết quả kiểm tra tổng hợp](docs/02_Synthesis_Review.md)

Nạp đúng file `de2_115_pulp_uart.sof` của nhánh này qua USB-Blaster. SOF ở Release RC1 thuộc thiết kế TARGET trên `main`. Sau khi kiểm jumper và đấu dây CP2102, để SW14=0, SW16=0, bật SW17 rồi nhấn và nhả KEY0. Khi LEDG0 sáng, mở cổng ở 115200 baud, 8N1.

**Windows** · Mở PowerShell tại thư mục gốc của nhánh.

```powershell
py -3 -m pip install pyserial==3.5
py -3 -X utf8 host/uart_gui.py --profile pulp
```

**Linux** · Cài pySerial cho Python của dự án một lần rồi mở cửa sổ.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install pyserial==3.5
.venv/bin/python host/uart_gui.py --profile pulp
```

Trong **Phiếu thử bo**, chọn một trong 8 ca để xem thao tác và giá trị mong đợi. Dùng **Gửi / nhận UART** để gửi byte, đọc TX/RX và thử echo. Khi đã đối chiếu với bo, ghi quan sát và xuất CSV. [Hướng dẫn giao diện](host/README.md) · [Phiếu nghiệm thu](docs/07_FPGA_Board_Acceptance.csv)

## Đối chiếu kết quả

```sh
python3 tools/check_upstream.py
python3 fpga/scripts/build_windows.py --check-only
python3 dv/run.py verify
```

Để chạy mô phỏng mới, dùng `python3 dv/run.py regress` cho UVM, `python3 dv/probes/run.py` cho các ca biên và `python3 fpga/sim/run.py` cho top cùng master APB. Kiểm tra menu qua cổng serial ảo nối trực tiếp với chân RX/TX của mô hình bằng `python3 integration/test_host_rtl.py`. [Hướng dẫn DV](dv/README.md) · [Thử menu với RTL](integration/README.md)
