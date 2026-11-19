# UART DE2-115 qua CP2102

Chọn `target` cho bitstream RC1, `pulp` cho bitstream main2. Cả hai dùng 115200 baud, mặc định 8N1, tắt điều khiển luồng XON/XOFF, RTS/CTS và DSR/DTR.

## Arch Linux

Mở menu từ thư mục gốc của dự án.

```sh
python host/uart_linux.py
```

Chọn profile, sau đó chọn số cổng. Menu ưu tiên tên ổn định trong `/dev/serial/by-id/` và hiện thiết bị mà tên đó trỏ tới. Khi thiếu tên ổn định, dùng cổng do pySerial phát hiện hoặc `/dev/ttyUSB*`, `/dev/ttyACM*`. Có thể nhập trực tiếp đường dẫn khác, kể cả PTY như `/dev/pts/4`.

```sh
python host/uart_linux.py --list
python host/uart_linux.py --profile target --port /dev/ttyUSB0 --log uart-target.log
```

Thay `/dev/ttyUSB0` bằng cổng đã xác định. Nếu Python đang dùng thiếu pySerial, lệnh trên tự dùng `.venv` ở gốc dự án. Tạo môi trường này một lần bằng hai lệnh sau.

```sh
python -m venv .venv
.venv/bin/python -m pip install pyserial==3.5
```

Nếu thiếu quyền, xem `ls -lL /dev/ttyUSB0` và `id` để đối chiếu quyền đọc/ghi và nhóm của tài khoản (thường là `uucp` trên Arch). Nếu cổng bận, đóng terminal đang dùng cổng. Nếu rút cáp, cắm lại rồi dùng `c` để quét lại.

## Windows 11

Dùng Python 3.8 trở lên. Đối chiếu CP2102 trong **Device Manager → Ports (COM & LPT)** rồi thay `COM10` bằng cổng thực tế.

```powershell
py -3 -m pip install pyserial==3.5
py -3 -X utf8 host\uart_menu.py --list
py -3 -X utf8 host\uart_menu.py --profile target --port COM10
```

Có thể tải riêng `uart_menu.py` và chạy `py -3 -X utf8 .\uart_menu.py`. Chọn profile rồi nhấn `c` để nhập tên COM hoặc chọn số thứ tự.

## Phím menu

| Phím | Thao tác |
|---|---|
| `c`, `d`, `q` | Chọn cổng, ngắt cổng, thoát. Enter tại ô chọn cổng để hủy. |
| `t`, `x` | Gửi chữ UTF-8 hoặc byte HEX (tối đa 1024 byte). Muốn gửi cả CR/LF, nhập `0D 0A` bằng `x`. |
| `r` | Hiện RX đã chờ và nghe thêm 3 giây, kể cả byte từ KEY1. |
| `e` | Thử echo. Enter gửi `55 AA 00 FF`, hoặc nhập HEX khác. `:q` hủy trước khi gửi. Sau lượt chưa khớp, `r` gửi lại, Enter về menu. |
| `f`, `h` | Đổi khung phía PC và mở lại cổng, hoặc xem hướng dẫn thử bo theo profile. |

Ctrl+C trong khi nhận hoặc thử echo sẽ đưa về menu. Lệnh `--log` chọn file JSON Lines UTF-8 để ghi nối tiếp. Mặc định file `uart-*.log` nằm trong thư mục chạy. Các dòng `TX` và `RX` ghi thời điểm phía PC, số byte và toàn bộ dữ liệu HEX. RX vẫn được ghi trong khi chờ nhập lệnh.

## Đấu dây và thử bo

Tắt nguồn trước khi đấu. Kiểm tra JP6 nối 7–8 (3,3 V), JP7 nối 5–6 (2,5 V) và mức logic UART của CP2102 là 3,3 V. Đối chiếu vị trí chân 1 trên JP5.

| CP2102 | JP5 trên DE2-115 |
|---|---|
| TXD → | Chân 3, GPIO[2] / AB21, FPGA RX |
| RXD ← | Chân 1, GPIO[0] / AB22, FPGA TX |
| GND | Chân 12 hoặc 30 |
| 3V3, 5V | Để hở. Bo dùng nguồn riêng. |

Nạp bitstream bằng USB-Blaster. Đặt SW14=SW16=SW17=0, giữ switch ổn định ít nhất 1 ms rồi nhấn/nhả KEY0. Chờ LEDG0 sáng, LEDG1 tắt rồi mở cổng ở 8N1.

1. **PC → bo.** Chọn `x`, nhập `41`. Kiểm tra HEX5:HEX4 hiện `41`.
2. **Bo → PC.** Đặt SW[7:0]=0x41 và giữ ổn định ít nhất 1 ms. Chọn `r`, nhấn KEY1 ít nhất 20 ms rồi nhả ít nhất 20 ms. PC phải nhận đúng một byte `41`.
3. **Echo.** Giữ SW16=0, bật SW17=1, để KEY1 yên. Chọn `e` rồi Enter. Kết quả mong đợi là `MATCH` với bốn byte `55 AA 00 FF`. Hạ SW17 và lặp lại khi đường truyền yên để kiểm tra `NO_RX`.
4. **Đổi parity.** Với RC1, SW14=1 chọn 8O1 khi SW15=0 và 8E1 khi SW15=1. Với PULP, SW14=1 chọn 8E1, SW15 dự phòng. Nhấn/nhả KEY0, chọn cùng khung bằng `f` rồi lặp lại bước 1–3. Phím `h` có thêm bài giữ RX bằng SW16.

Echo đợi RX yên 120 ms trước khi gửi. Nếu sau 700 ms RX vẫn bận, kết quả là `BUSY` và gói thử chưa được gửi. Trong 1 giây sau TX, `MATCH` yêu cầu đúng dữ liệu, độ dài và thứ tự. `SHORT`, `MISMATCH`, `EXTRA` lần lượt chỉ gói thiếu, sai và thừa.

## Kiểm thử host trên Linux

```sh
.venv/bin/python -B -m unittest discover -v -s host/tests
```

Các ca PTY chạy chương trình thật và dùng đầu serial đối diện để phát, thu và kiểm tra byte. Đối chiếu HEX, LED và tín hiệu điện trên bo bằng quy trình ở trên.
