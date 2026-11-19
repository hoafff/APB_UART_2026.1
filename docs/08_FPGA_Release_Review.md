# Kết quả biên dịch FPGA của RC1

Quartus Prime Lite 25.1std.0 Build 1129 đã biên dịch top `de2_115_apb_uart_bringup` cho EP4CE115F29C7. Manifest ghi commit lúc build là `cbce1e55915306b07a8ebae0ee4592a6bdd75424`. Tag phát hành `v1.0.0-fpga-rc1` trỏ tới `f6f3eb2`. [Gói RC1, manifest và báo cáo gốc](https://github.com/hoafff/APB_UART_2026.1/releases/tag/v1.0.0-fpga-rc1)

| Mục | Kết quả |
|---|---|
| Fitter | 1.422 logic elements, 667 thanh ghi, 65 chân |
| Timing 50 MHz, ba góc | Worst setup +5,016 ns, worst hold +0,181 ns |
| Kiểm ràng buộc | 0 đường chưa ràng buộc, 0 SDC bị bỏ qua |
| Cảnh báo | 20 warning đã phân loại, 0 critical warning |
| Questa | System, controller và TX one-hot đều đạt |
| Nạp SRAM, UART và đo trên bo | Chưa thực hiện |

Thiết kế dùng `CLOCK_50` ở Y2, TX ở AB22 và RX ở AB21. SOF dài 3.541.833 byte, SHA-256 `8dbd4d2a4f4b0d15c4db123d2bde29536da6059bfa89f9b1b3914456640da4a1`. [Chi tiết từng góc timing và các cảnh báo](06_FPGA_Implementation.md) · [Phiếu đo trên bo](07_FPGA_Board_Acceptance.csv)

Mã RTL, project Quartus, ràng buộc và testbench trong `main` khớp các hash dùng để tạo SOF. Script đóng gói trên `main` chỉ lấy nguồn được Git theo dõi và các kết quả build đã niêm phong. Khi đối chiếu RC1, chạy `verify` trong chính gói tải về.
