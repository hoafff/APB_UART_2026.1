# Tổng hợp RTL PULP nguyên bản

Lõi trong `rtl/vendor/pulp_apb_uart_sv/` khớp commit `dfad6e04d19cc9481d3cd2750b45b970dc61271b`. Ba phép thử sau chạy trên Arch với Yosys `0.70+360 (5e740962d)`, cùng năm file SystemVerilog và top `apb_uart_sv`. Chạy từng lệnh ở thư mục gốc.

```sh
yosys -p 'read_verilog -sv rtl/vendor/pulp_apb_uart_sv/*.sv; hierarchy -check -top apb_uart_sv; proc; opt; check -assert'
yosys -p 'read_slang --top apb_uart_sv rtl/vendor/pulp_apb_uart_sv/*.sv; hierarchy -check -top apb_uart_sv; proc; opt; check -assert'
yosys -p 'read_slang --top apb_uart_sv rtl/vendor/pulp_apb_uart_sv/*.sv; synth_intel -family cycloneive -top apb_uart_sv; check -assert'
```

| Phép thử | Kết quả thực thi |
|---|---|
| Frontend Verilog của Yosys | Exit 1. Pass `proc` báo `Latch inferred for signal ... fifo_tx_data ... from always_comb process` tại `apb_uart_sv.sv:195`. |
| Frontend slang, kiểm cấu trúc | Exit 1. `check -assert` báo 24 đường hồi tiếp đi qua các bit của `fifo_tx_data`. |
| Frontend slang, ánh xạ Cyclone IV E | Exit 1. Luồng ánh xạ báo `Combinational cycle through ... fifo_tx_data [7]`. |

Trong logic ghi APB, `fifo_tx_valid` có giá trị mặc định 0. `fifo_tx_data` chỉ nhận dữ liệu khi ghi THR với DLAB bằng 0. FIFO chỉ chốt dữ liệu hợp lệ khi còn chỗ. Vì vậy test giao dịch có thể quan sát đúng byte trong khi công cụ tổng hợp vẫn phát hiện phép giữ giá trị trên đường dữ liệu. Có thể kiểm trực tiếp ở [mạch ghi THR](../rtl/vendor/pulp_apb_uart_sv/apb_uart_sv.sv#L195-L229) và [mạch ghi bộ nhớ FIFO](../rtl/vendor/pulp_apb_uart_sv/io_generic_fifo.sv#L72-L86).

Khi build `main2` trên Windows, lưu thông báo Analysis & Synthesis, báo cáo latch/loop, fitter và TimeQuest của chính lần build này. Nếu Quartus dừng, giữ nguyên log lỗi và phiên bản tool. Kết quả trên là của Yosys. Verdict Quartus và kết quả nạp bo phải đến từ lần chạy trên Windows. [Hướng dẫn FPGA](05_FPGA_Windows.md)
