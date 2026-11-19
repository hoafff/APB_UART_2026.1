# Dùng bản nạp RC1 trên Windows

Tải `de2_115_apb_uart.sof` để nạp SRAM qua USB-Blaster. Gói `APB_UART_DE2_115_2026-11-13.zip` cùng release chứa project, manifest, báo cáo Quartus và bản sao của SOF. [Release RC1](https://github.com/hoafff/APB_UART_2026.1/releases/tag/v1.0.0-fpga-rc1)

Để kiểm gói, giải nén ZIP, mở PowerShell **trong thư mục vừa giải nén** rồi chạy lệnh sau với Python 3.11 trở lên.

```powershell
py -3 -X utf8 tools/build_fpga.py verify
```

Để dùng menu UART mới, mở PowerShell **trong checkout hiện tại của nhánh main**. Sau khi kiểm jumper, đấu dây và nạp SOF, mở cổng bằng hai lệnh dưới đây.

```powershell
py -3 -m pip install pyserial==3.5
py -3 host/uart_menu.py --profile target
```

Kết quả Windows của RC1 gồm fitter, timing ở 50 MHz, file nạp và ba mô phỏng Questa. Phiếu thử DE2-115 + CP2102 còn 14 mục chờ đo. [Hướng dẫn nạp và build lại](06_FPGA_Implementation.md) · [Hướng dẫn menu](../host/README.md) · [Phiếu thử](07_FPGA_Board_Acceptance.csv)
