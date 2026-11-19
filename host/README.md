# Terminal UART cho DE2-115 và CP2102

`uart_menu.py` là entry point duy nhất. Cùng một file dùng cho bitstream TARGET RC1 (`target`) và wrapper main2 với DUT PULP nguyên bản (`pulp`). Chọn profile theo bitstream đã nạp. Cả hai khởi đầu ở **115200 baud, 8N1**, tắt XON/XOFF, RTS/CTS và DSR/DTR flow control.

## Mở trên Windows 11

Nếu tải riêng file Python, mở PowerShell trong thư mục chứa file và dùng `py -3 -X utf8 .\uart_menu.py` thay cho đường dẫn `host\uart_menu.py` ở các lệnh bên dưới.

Tắt nguồn khi đấu dây. Kiểm tra CP2102 dùng mức logic UART 3,3 V. Nối **TXD → GPIO[2]/AB21** (FPGA RX), **RXD ← GPIO[0]/AB22** (FPGA TX) và **GND chung**. Bo dùng nguồn riêng, để hở chân nguồn của CP2102. Đối chiếu tên tín hiệu trên sơ đồ header. Trong gói RC1, mục 5–7 của `docs/06_FPGA_Implementation.md` mô tả vị trí jumper, cách nạp SRAM và quy trình thử bo.

Trong PowerShell, tại thư mục gốc checkout, dùng Python 3.8 trở lên. Cài pyserial một lần. Dùng `--list` và đối chiếu với **Device Manager → Ports (COM & LPT)** khi cắm/rút CP2102.

```powershell
py -3 -m pip install pyserial==3.5
py -3 -X utf8 host\uart_menu.py --list
py -3 -X utf8 host\uart_menu.py --profile target --port COM10 --log "$env:TEMP\uart-target.log"
```

Thay `COM10` bằng tên cổng của bạn. Với main2, chọn profile `pulp`.

```powershell
py -3 -X utf8 host\uart_menu.py --profile pulp --port COM10 --log "$env:TEMP\uart-pulp.log"
```

Chạy `py -3 -X utf8 host\uart_menu.py` để chọn profile trên màn hình, rồi nhấn `c`. Có thể chọn số thứ tự hoặc gõ thẳng `COM3`, `COM10`, `COM101` kể cả khi danh sách trống. Khi cổng bận, đóng terminal đang giữ cổng rồi dùng `c` để thử lại. Nếu Windows chưa liệt kê CP2102, kiểm tra cáp USB dữ liệu và driver CP210x VCP trong Device Manager.

## Dùng menu

| Phím | Thao tác |
|---|---|
| `c`, `d`, `q` | Liệt kê/chọn cổng, ngắt kết nối, thoát. Enter tại ô chọn cổng hủy lựa chọn. |
| `f` | Chọn khung phía PC. Đổi khung sẽ mở lại cổng đang dùng. Chọn switch trên bo và reset bằng KEY0 để hai đầu khớp nhau. |
| `t` | Gửi nguyên dòng dưới dạng UTF-8. Ký tự ASCII chiếm một byte. Giữ nguyên khoảng trắng và chỉ gửi nội dung trước Enter. |
| `x` | Gửi byte HEX, ví dụ `00 FF 11 13` hoặc `00FF1113`. Muốn gửi CR/LF thì nhập `0D 0A`. Mỗi lần gửi tối đa 1024 byte. |
| `r` | Hiện RX đang chờ rồi nghe thêm 3 giây. RX từ KEY1 cũng được ghi trong lúc chờ nhập lệnh. |
| `e` | So echo raw. Enter dùng `55 AA 00 FF`, hoặc gõ gói HEX riêng. `:q` hủy trước TX. Sau kết quả chưa khớp, `r` gửi lại đúng gói, Enter về menu. |
| `h` | Hiện các bước thử và mapping switch của profile đang chạy. |

Ctrl+C trong thao tác nhận/so echo đưa về menu. Byte đã gửi trước khi hủy vẫn có thể tới bo. Khi rút cáp hoặc driver báo lỗi, xem thông báo cổng và mở lại bằng `c`. Dòng TX thể hiện byte driver đã nhận để phát. Chương trình chỉ lấy RX từ cổng nối tiếp.

## Các bài thử trên bo

Trước khi thử, nạp đúng bitstream, đặt **SW14=0, SW16=0, SW17=0**. Giữ switch ổn định ít nhất 1 ms, nhấn/nhả KEY0 (RC1 yêu cầu nhấn ít nhất 1 µs). Chờ LEDG0 sáng, LEDG1 tắt. Mở CP2102 ở 8N1. Mỗi bước dưới đây ghi **kết quả mong đợi** để so với quan sát thật.

1. **PC → HEX.** Chọn `x`, nhập `41`, nhấn Enter. Kiểm tra log có TX đúng một byte `41` và **HEX5:HEX4 hiện 41**. Có thể dùng `t` rồi nhập chữ hoa `A` để gửi đúng byte đó. Đặt SW17=0 cho bài thử một chiều này.
2. **KEY1 → PC.** Đặt SW[7:0] = `0100 0001` (bật SW6 và SW0). Kiểm tra HEX1:HEX0 hiện `41`. Giữ switch ổn định ít nhất 1 ms, chọn `r`, nhấn rồi nhả KEY1, mỗi trạng thái kéo dài ít nhất 10 ms. PC phải ghi đúng **một RX `41`** cho một lần nhấn. Giữ phím chỉ phát một lần. Nếu nhấn trước khi chọn `r`, byte đã đọc nằm trong hàng chờ của phiên mở cổng.
3. **Echo nhị phân.** Đặt SW16=0, SW17=1, để KEY1 yên. Chọn `e` rồi Enter. Đối chiếu TX `55 AA 00 FF` với RX đúng bốn byte cùng thứ tự và kết quả `MATCH`. Có thể nhập `00 FF 0D 0A` để thử thêm byte điều khiển. Hạ SW17 sau bài thử.
4. **Giữ RX và nhả.** Với SW17=0, gửi `41` để có mốc trên HEX5:HEX4. Bật SW16=1, chọn `x`, gửi `A5`. Quan sát HEX vẫn là `41`. Hạ SW16, chờ wrapper đọc FIFO và kiểm tra HEX chuyển sang `A5`. **Riêng RC1**, để thử overflow, bật lại SW16, gửi một lần `00 01 02 03 04 05 06 07 08 09 0A 0B 0C 0D 0E 0F 10` (17 byte), chờ poll rồi hạ SW16. Kiểm tra OE sticky tại LEDR1 và xóa bằng KEY0. Với **main2**, dùng bài giữ/nhả một byte để quan sát hành vi đọc.
5. **Parity.** Chọn mode trong bảng, giữ switch ổn định rồi nhấn/nhả KEY0. Trong menu dùng `f` để chọn cùng khung, đợi bo init rồi lặp bước 1–3. Với RC1 thử lần lượt odd/even. Với main2 thử even. Để thử **PE riêng trên RC1**, đặt bo 8O1, PC 8E1, gửi `41` rồi quan sát LEDR2 (PE sticky). Khôi phục cùng khung và nhấn KEY0 để xóa cờ. Với PULP, kết luận về cờ lỗi cần phép quan sát DUT riêng.
6. **Reset và phục hồi.** Nhấn/nhả KEY0 khi idle, chờ init và lặp lại bước 1–3. Nếu thử reset giữa traffic, ghi lại các byte thực nhận của lượt đang chạy, chờ init rồi gửi một gói mới. Ghi riêng từng lượt để phân biệt dữ liệu trước và sau reset.

| Profile | 8N1 | 8O1 | 8E1 |
|---|---|---|---|
| `target` (RC1) | SW14=0 | SW14=1, SW15=0 | SW14=1, SW15=1 |
| `pulp` (main2) | SW14=0 | Không hỗ trợ | SW14=1 |

Main2 chốt SW14 khi reset bằng KEY0. SW15 dự phòng. Cả hai wrapper dùng SW16 để giữ đọc RX, SW17 để bật echo và KEY1 để phát SW[7:0].

## Đọc log và kết quả echo

Mỗi dòng log là một bản ghi JSON UTF-8. File mặc định có tên `uart-<ngày-giờ>.log` trong thư mục chạy. `--log` ghi nối tiếp vào file đã chọn. `OPEN` ghi cổng, baud, profile và khung. Mỗi `TX`/`RX` có thời điểm **phía host** kèm múi giờ, số byte `size`, toàn bộ byte ở trường `hex` và thao tác ở `phase`. Ghép các trường `hex` của cùng chiều theo thứ tự để phục hồi dữ liệu, kể cả NUL và FF. RX có thể chia thành nhiều dòng tùy thời điểm driver giao byte. Màn hình xem nhanh giữ 256 khối RX gần nhất, còn file ghi mọi khối đã đọc.

Trước khi gửi gói echo, chương trình ghi nhận dữ liệu cũ và đợi RX yên 120 ms, tối đa 700 ms. Sau TX, chương trình thu **trọn 1 giây** để phát hiện cả byte thừa đến sau một tiền tố đúng. Đọc cổng ở chế độ không chặn, timeout ghi là 0,5 giây. Bản ghi `ECHO` chứa `status`, số byte trước TX (`before_tx`) và số byte thực nhận sau TX (`rx_size`).

| Kết quả | Ý nghĩa trong lượt thử |
|---|---|
| `MATCH` | Byte nhận trong cửa sổ khớp toàn bộ gói gửi, đúng độ dài và thứ tự. |
| `NO_RX`, `SHORT` | Hết cửa sổ mà chưa nhận byte nào, hoặc chỉ nhận đúng một phần đầu gói. |
| `MISMATCH`, `EXTRA` | Sai nội dung/thứ tự, hoặc nhận đủ gói đúng rồi còn byte thừa. |
| `BUSY` | RX liên tục trước TX. Chương trình bỏ lượt gửi. |

Nếu driver lỗi giữa một lần ghi và số byte đã phát chưa xác định được, `TX_UNCERTAIN` lưu gói yêu cầu. Người vận hành quyết định có gửi lại. Để nghiệm thu phần cứng, lưu log cùng mã bo, CP2102/COM, định danh `.sof`, vị trí SW và ảnh HEX/LED. `MATCH` chỉ xác nhận luồng byte quan sát được ở cổng đã mở. Với raw UART, nguồn khác phát đúng gói trong cùng cửa sổ cũng có thể tạo kết quả này.

## Chạy kiểm thử host

```bash
python -B -m unittest discover -v -s host/tests
```

Các test PTY chạy trên POSIX, mở script bằng tiến trình riêng, truyền phím vào menu và điều khiển đầu serial đối diện. Bộ test thử hai chiều, đủ 256 giá trị byte, gói cũ trước TX, thiếu/sai/thừa byte, timeout, thử lại, hủy, rút cổng và kết thúc bằng EOF. Trên Windows, các ca cần PTY POSIX được đánh dấu skip. Người chạy mô phỏng đã đối chiếu riêng menu với board RC1 Verilator qua PTY cho echo `55 AA 00 FF` và KEY1 → `41`. Việc đo trên Windows 11 với CP2102 và DE2-115 thật cần thực hiện trên bộ thiết bị đó.
