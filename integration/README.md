# Kiểm menu Python với tín hiệu UART của mô hình RTL

Trên Linux, dùng Python 3 với pySerial, Verilator và trình biên dịch C++. Từ thư mục gốc:

```sh
python integration/test_host_rtl.py
```

Lệnh biên dịch top DE2-115 cùng năm file PULP gốc. Bộ thu bên PC lấy mẫu giữa bit theo 115200 baud, kiểm cả parity và stop. Tín hiệu `GPIO_UART_RX` nhận ba chuỗi nhị phân, trong đó có burst 16 byte liên tiếp. Test bấm/nhả KEY1 trên mô hình với thời gian debounce mặc định và giải mã byte phát qua `GPIO_UART_TX`.

Sau đó script chạy chương trình `host/uart_menu.py` qua cổng PTY. Các byte PC gửi qua pySerial được phát thành bit ở chân RX của top. Chỉ các byte giải mã lại ở chân TX mới quay về host. Script tắt SW17 cho lượt đầu, bật lại rồi gửi cùng gói. Nó kiểm trong nhật ký menu hai kết quả `NO_RX` và `MATCH`, sau đó kiểm thêm byte `41` do KEY1 gửi. Phần PTY dùng 8N1. Các ca kiểm chân RTL chạy cả 8N1 và 8E1 trên PULP. Có thể dùng `--profile target --root <checkout-main>` để chạy với phiên bản RC1 và thêm ca 8O1 ở chân RTL.

Lần chạy ngày 19/11/2026 cho kết quả `NO_RX → MATCH` và nhận `41` với cả hai thiết kế. Phiên bản công cụ, các hash đầu vào và stdout của mỗi profile nằm trong [hồ sơ kiểm tra](result.json). Đây là kiểm tra phần mềm PC cùng RTL trước khi nạp. Ghi kết quả nạp, đo điện áp và thử UART trên CP2102/DE2-115 thật vào phiếu của lần nghiệm thu Windows.
