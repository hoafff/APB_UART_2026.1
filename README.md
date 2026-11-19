# APB UART PULP trên DE2-115 · main2

Nhánh này xây dựng hệ thống DE2-115 quanh lõi `apb_uart_sv` của ETH Zürich và Đại học Bologna. Năm file RTL, file danh sách nguồn và giấy phép trong `rtl/vendor/pulp_apb_uart_sv/` khớp từng byte với [commit PULP dfad6e0, nhánh pulpinov1](https://github.com/pulp-platform/apb_uart_sv/tree/dfad6e04d19cc9481d3cd2750b45b970dc61271b). Wrapper FPGA và bộ kiểm thử thuộc dự án này.

| Nội dung đồ án | Tài liệu và mã nguồn |
|---|---|
| 1. Đặc tả hệ thống, thanh ghi, giao thức, FIFO, ngắt, baud | [Đặc tả PULP](docs/01_System_Specification.md) và [danh tính từng file gốc](docs/spec/baseline_hashes.json) |
| 2. Kế hoạch kiểm chứng, môi trường UVM, ca định hướng và ngẫu nhiên, coverage | [DV Plan](docs/03_DV_Plan.md), [mã kiểm thử](dv/) và [kết quả thực thi](docs/DV_RESULTS.md) |
| 3. Tích hợp, build, nạp và thử trên DE2-115 | [Project Quartus](fpga/de2_115/de2_115_pulp_uart.qpf), [hướng dẫn Windows và nghiệm thu bo](docs/05_FPGA_Windows.md), [menu COM](host/uart_menu.py) |

Bộ mô phỏng dùng đúng mã nguồn PULP phía trên. Mốc bàn giao cho Windows gồm project và các bài thử. File nạp, số liệu fitter/STA và kết quả bo của `main2` sẽ do lần build và thử riêng trên Windows xác định. Kiểm tổng hợp độc lập bằng Yosys đã phát hiện latch ở `fifo_tx_data` trong lõi gốc. [Chi tiết phép thử](docs/02_Synthesis_Review.md)

## Chạy trên Windows

1. Cài Python 3 và pySerial. Mở PowerShell ở thư mục gốc và chạy `py -3 tools/check_upstream.py` để kiểm bản nguồn.
2. Dùng Quartus Prime Lite có hỗ trợ **Cyclone IV E, EP4CE115F29C7**. Mở `fpga/de2_115/de2_115_pulp_uart.qpf`, biên dịch revision `de2_115_pulp_uart` theo hướng dẫn Windows. Xem báo cáo synthesis, fitter, timing 50 MHz và pin assignments của chính lần build trước khi nạp. [Kết quả kiểm tổng hợp bằng Yosys](docs/02_Synthesis_Review.md)
3. Kiểm jumper và mức logic theo hướng dẫn. Dùng USB-Blaster để nạp `de2_115_pulp_uart.sof` vừa build. CP2102 dùng cho dữ liệu UART sau khi nạp. File `.sof` ở Release `v1.0.0-fpga-rc1` chứa thiết kế TARGET trên nhánh khác.
4. Với chế độ mặc định, để SW14=0, SW16=0, nhấn rồi nhả KEY0. Chọn cổng COM của CP2102 trong chương trình sau.

```powershell
py -3 -m pip install pyserial==3.5
py -3 host/uart_menu.py --profile pulp
```

Đường truyền là UART byte thô, 115200 baud, không dùng flow control. SW14=1 trước reset chọn 8E1. SW15 dự phòng. KEY1 gửi SW[7:0] từ FPGA về PC. Khi nhận từ PC, HEX5:HEX4 hiển thị byte mới nhất. Bật SW17 và để SW16=0 để thử echo, ví dụ gửi chuỗi HEX `55 AA 00 FF` rồi kiểm đủ bốn byte phản hồi. [Hướng dẫn chương trình](host/README.md)

## Chạy lại bằng chứng

| Mục đích | Lệnh từ thư mục gốc |
|---|---|
| Kiểm tra nguồn PULP | `python tools/check_upstream.py` |
| Kiểm tra filelist, chip và các chân trong project | `python fpga/scripts/check_project.py` |
| Đối chiếu lại bộ log UVM đã bàn giao | `python dv/run.py verify` |
| Chạy hồi quy UVM mới trên Linux với Verilator, Z3 và UVM đã pin | `python dv/run.py regress` |
| Kiểm biên FIFO, reset giữa khung, bộ chia baud và cạnh lấy mẫu ở chân RX | `python dv/probes/run.py` |
| Mô phỏng top FPGA và master APB | `python fpga/sim/run.py` |
| Chạy các test của ứng dụng PC với pySerial | `python -m unittest discover -s host/tests` |
| Chạy menu thật qua cổng ảo nối tới chân UART của top RTL trên Linux | `python integration/test_host_rtl.py` · [Chi tiết cách nối](integration/README.md) |

## Nhận diện đúng bản thiết kế

- PULP giải mã `PADDR[2:0]`, LCR ở offset `0x03`, LSR ở `0x05`. Với clock 50 MHz, wrapper nạp DLM=`0x01`, DLL=`0xB1` (433), tương ứng 434 clock/bit khi truyền dữ liệu.
- Tại board, PULP hỗ trợ cấu hình 8N1 và 8E1. Hành vi cờ lỗi và ngắt của lõi gốc được ghi cụ thể trong SPEC. Bộ điều khiển đọc trạng thái LSR khi phục vụ UART.
- Có thể đối chiếu trực tiếp các byte nguồn với một clone upstream bằng `python tools/check_upstream.py --upstream <thu-muc-clone-pulp>`. [Ghi chú đối chiếu với hướng dẫn thực hành ban đầu](docs/00_RTL_Guide_Discrepancies.md)
