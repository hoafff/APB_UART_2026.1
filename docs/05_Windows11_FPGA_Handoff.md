# Bàn giao Yêu cầu 3 trên Windows 11

Cập nhật 12/11/2026: **SOFTWARE_READY / HARDWARE_PENDING**.

Quartus Prime Lite 25.1std.0 và Cyclone IV đã được cài tại `D:\uart\25.1std`.
Repo ở `D:\uart\APB_UART_2026.1` có project DE2-115, bitstream SRAM `.sof`,
fitter/STA ba corner, bộ kiểm tra SHA-256 và hướng dẫn nạp. RTL cùng bằng chứng
Yêu cầu 1–2 được giữ nguyên. Chưa nạp hoặc thử UART trên bo thật.

**Tài liệu tiếp tục:** [hướng dẫn triển khai/nạp/kiểm chứng đầy đủ](06_FPGA_Implementation.md)
và [phiếu thử bo](07_FPGA_Board_Acceptance.csv).

| Hạng mục | Trạng thái |
|---|---|
| Quartus Lite + Cyclone IV E, đúng EP4CE115F29C7 | PASS |
| Project, đúng sáu source, 65 chân | PASS |
| Full compile, fitter, assembler, STA | PASS; 20 warning đã phân loại |
| Bitstream và manifest SHA-256 | Có; chạy `tools/build_fpga.py verify` trước dùng |
| Mô phỏng system/controller/onehot bằng Questa hiện có | PASS |
| JTAG hiện tại | Không phát hiện hardware |
| Jumper/điện áp, nạp FPGA, thử CP2102 | NOT_RUN |

```powershell
Set-Location D:\uart\APB_UART_2026.1
python -X utf8 tools/build_fpga.py verify
```

Python 3.11+; project GUI tại `fpga/de2_115/de2_115_apb_uart.qpf`.
USB-Blaster là đường nạp, CP2102 là đường UART. Driver/device thật vẫn cần xác
minh khi cắm bo. Không lấy driver hay kết quả Linux làm bằng chứng Windows.

UVM đầy đủ tiếp tục dùng flow Linux đã có; unit test `test_report_dv` cũ phụ
thuộc `resource` nên không chạy native Windows. Hạn chế này không được ghi
thành PASS, cũng không ảnh hưởng bộ test phát hành FPGA độc lập.
