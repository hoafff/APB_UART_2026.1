# Kiểm tra menu PC với top FPGA

Bài kiểm tra nối một cổng serial ảo của Linux với hai chân `GPIO_UART_RX` và `GPIO_UART_TX` của mô hình RTL. Cần Python 3 có pySerial, Verilator và bộ biên dịch C++. Chạy từ thư mục gốc của dự án.

```sh
.venv/bin/python integration/test_host_rtl.py
.venv/bin/python integration/test_host_rtl.py --entry uart_linux.py
```

Script chọn top theo project Quartus trong checkout. Bộ phát PC dùng tốc độ 115200 baud. Bộ thu độc lập lấy mẫu giữa bit, kiểm parity và stop, rồi giải mã ba gói nhị phân gồm cả một burst 16 byte. KEY1 được giữ đủ thời gian debounce để truyền giá trị trên SW[7:0].

Qua PTY, test gửi `55 AA 00 FF` khi SW17 tắt rồi bật lại. Nhật ký menu phải lần lượt ghi `NO_RX` và `MATCH`. Sau đó test đặt SW[7:0] = `41`, nhấn KEY1 và kiểm PC nhận đúng byte `41`. Bài PTY dùng 8N1. Phần thử trực tiếp trên chân RTL chạy thêm các chế độ parity mà từng thiết kế hỗ trợ. [Kết quả của nhánh này](result.json)
