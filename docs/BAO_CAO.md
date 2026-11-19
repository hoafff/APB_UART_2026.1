# Báo cáo thực hành APB–UART trên DE2-115 — TARGET RC1

## 1. Đặc tả và thiết kế

Bộ điều khiển làm chủ bus APB 32 bit ở 50 MHz. Khi nhận xung từ KEY1 sau khử dội, nó ghi `SW[7:0]` vào THR. Byte đi qua FIFO phát và UART tới PC qua CP2102. Ở chiều nhận, bộ điều khiển đọc byte đầu FIFO qua RBR và hiển thị trên HEX5–HEX4. SW16 tạm dừng đọc RBR. SW17 cho phép phát lại byte vừa đọc (echo).

| Offset theo byte | `0x000` | `0x004` | `0x008` | `0x00C` | `0x014` |
|---|---|---|---|---|---|
| Đọc khi DLAB = 0 | RBR | IER | IIR | LCR | LSR |
| Ghi khi DLAB = 0 | THR | IER | FCR | LCR | Báo lỗi APB |

Đặt DLAB (bit 7 của LCR) để ghi DLL và DLM tại hai offset đầu. Với DLL = 27 và DLM = 0, mỗi bit dài `16 × 27 = 432` chu kỳ, tức 8,64 µs theo thiết kế. PC mặc định 115200 baud, 8N1, tắt điều khiển luồng. LCR chọn 5–8 bit dữ liệu, parity tắt/lẻ/chẵn và 1–2 bit stop. Mỗi FIFO chứa 16 byte khi bật. LSR báo lỗi tràn, sai parity, sai stop và break. [Đặc tả TARGET-v1.0](01_System_Specification.md)

## 2. Kế hoạch và kết quả kiểm chứng

UVM phát giao dịch APB và dùng nguồn nối tiếp độc lập để kích `rx_i`. Scoreboard so byte ghi THR với khung giải mã ở `tx_o` và dùng khung quan sát trên `rx_i` làm chuẩn cho byte đọc RBR. Trong hai ca đối chứng, đảo một bit TX sau giải mã làm scoreboard báo sai byte, còn phát ACCESS thiếu SETUP kích hoạt assertion APB.

Trên Linux, **15/15 lượt UVM đạt** với Verilator, gồm 12 ca định hướng và một ca ngẫu nhiên có ràng buộc với ba seed 17, 29, 101. Cả ba testbench bổ sung cho hệ thống, bộ điều khiển và mẫu TX one-hot đều đạt. Bộ kiểm thử phủ **833/833 bin chức năng** đã định nghĩa. Độ phủ mã RTL còn 1.097 điểm chưa được kích hoạt. [Kế hoạch DV](03_DV_Plan.md) · [Kết quả và độ phủ](dv/RESULTS.md)

## 3. Triển khai FPGA và nghiệm thu

Nhánh `main` chứa RTL và dự án Quartus của bản bàn giao `f6f3eb2`. Bản phát hành RC1 kèm tệp nạp SRAM `de2_115_apb_uart.sof` và báo cáo biên dịch từ `cbce1e5`. Trên Windows, ba testbench bổ sung đạt với Questa. Quartus Prime Lite 25.1 hoàn tất với 0 lỗi, 20 cảnh báo. Thiết kế dùng 1.422 phần tử logic và 65 chân của EP4CE115F29C7. Ở 50 MHz, slack nhỏ nhất qua ba góc phân tích là **+5,016 ns cho setup** và **+0,181 ns cho hold**. [Dự án Quartus](../fpga/de2_115/de2_115_apb_uart.qpf) · [Bản phát hành v1.0.0-fpga-rc1](https://github.com/hoafff/APB_UART_2026.1/releases/tag/v1.0.0-fpga-rc1)

Phần còn lại trên bo gồm kiểm jumper và mức logic 3,3 V, đấu chéo TX/RX với GND chung, nạp SOF qua USB-Blaster rồi thử truyền nhận. Sau khi nạp, `host/uart_menu.py --profile target` chạy trên PC, mở cổng CP2102 (COM trên Windows, thường là `/dev/ttyUSB0` trên Linux) và ghi nhật ký TX/RX. Dùng menu gửi byte `0x41` ở chế độ HEX để kiểm HEX5–HEX4, thu byte do KEY1 phát và so gói echo `55 AA 00 FF` ở 8N1, 8O1 và 8E1. [Menu Python](../host/README.md) · [Phiếu thử bo](07_FPGA_Board_Acceptance.csv)
