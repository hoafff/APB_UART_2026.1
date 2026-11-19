# Báo cáo thực hành APB–UART trên DE2-115 — PULP nguyên bản

## 1. Đặc tả và tích hợp

Nhánh `main2` dùng nguyên năm tệp SystemVerilog của PULP tại `dfad6e0`. Hai mô-đun tích hợp nối lõi với DE2-115. Khi nhấn KEY1 đã khử dội, bộ điều khiển APB ghi `SW[7:0]` vào THR để phát qua FIFO TX và CP2102 tới PC. Chiều nhận đi từ CP2102 qua FIFO RX và RBR tới HEX5–HEX4. SW16 tạm dừng đọc RBR, còn SW17 cho phép phát lại byte đã đọc.

| Offset theo byte | `0x0` | `0x1` | `0x2` | `0x3` | `0x5` |
|---|---|---|---|---|---|
| Đọc khi DLAB = 0 | RBR | IER | IIR | LCR | LSR |
| Ghi khi DLAB = 0 | THR | IER | FCR | LCR | Bỏ qua |

Lõi chỉ giải mã `PADDR[2:0]` nên các offset lặp lại sau 8 byte. Khi DLAB (bit 7 của LCR) bằng 1, hai offset đầu chọn DLL và DLM. Với DLL = `0xB1`, DLM = `0x01` (hệ số chia 433) và clock 50 MHz, phép đo trên chân TX mô phỏng khi phát `0x55` cho **435 chu kỳ ở bit start** (8,70 µs) và **434 chu kỳ mỗi bit dữ liệu** (8,68 µs). PC mặc định 115200 baud, 8N1, tắt điều khiển luồng. SW14 chọn 8N1 hoặc 8E1 khi reset vì lõi chỉ tạo được parity chẵn. Hai FIFO 16 byte luôn hoạt động, bất kể giá trị `FCR[0]`. [Đặc tả main2](01_System_Specification.md) · [Log đo cạnh TX](../dv/evidence/baud-17.log)

## 2. Kế hoạch và kết quả kiểm chứng

UVM phát giao dịch APB và khung nối tiếp từ ngoài lõi. Scoreboard so byte ghi THR với khung giải mã trên TX và so byte quan sát độc lập ở chân RX với byte đọc RBR. Đổi một bit của byte kỳ vọng ở từng chiều làm hai ca đối chứng báo đúng lỗi `TX_DATA` và `RBR_DATA`. Verilator trên Linux chạy đạt **10/10 lượt UVM** gồm 7 ca định hướng và 3 lượt ngẫu nhiên có ràng buộc, với 2.485 phép so và **117/117 bin chức năng** đã định nghĩa. [Kế hoạch DV](03_DV_Plan.md) · [Kết quả từng ca](DV_RESULTS.md)

RX vẫn nhận byte sai parity hoặc có stop thấp với PE và FE bằng 0. Trong phép thử break, giữ RX ở mức thấp kéo dài vẫn cho BI = 0. Khi gửi 18 khung cách nhau một bit nghỉ rồi mới đọc, RBR trả 17 byte (16 trong FIFO, một chờ ở bộ thu), OE bằng 0. Ngắt có thể bật khi RX rỗng và giữ mức cao sau khi che nguồn ngắt. Vì vậy bộ điều khiển thăm dò `LSR[0]` để đọc RBR và `LSR[5]` để ghi THR.

## 3. Dự án FPGA và phần thực hành còn lại

Trên Linux, 9 ca mô phỏng tại chân FPGA và 5 ca của bộ điều khiển đều đạt. Các gói 4, 16 và 64 byte được echo đúng thứ tự ở cả 8N1 và 8E1. Kiểm tra tĩnh khớp 65 chân với bảng chân DE2-115. Với frontend `read_verilog -sv` của Yosys, bước `proc` dừng vì suy ra latch ở `fifo_tx_data`. Khối `always_comb` chỉ gán tín hiệu này khi ghi THR. [Log mô phỏng hệ thống](../fpga/evidence/board.log) · [Kết quả tổng hợp](02_Synthesis_Review.md)

Dự án EP4CE115F29C7 còn chờ biên dịch bằng Quartus trên Windows để có báo cáo fitter, kết quả TimeQuest ở 50 MHz và tệp SOF. Tại bàn thử cần kiểm jumper, mức logic 3,3 V, đấu chéo TX/RX với GND chung và nạp SOF qua USB-Blaster. Sau khi nạp, `host/uart_menu.py --profile pulp` chạy trên PC, mở cổng CP2102, ghi nhật ký TX/RX và so echo. Dùng menu gửi byte `0x55` để kiểm HEX5–HEX4, thu byte do KEY1 phát và thử echo ở 8N1, 8E1. [Hướng dẫn và phiếu thử bo](05_FPGA_Windows.md) · [Menu Python](../host/README.md)
