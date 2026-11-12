# Yêu cầu 3: phần triển khai có thể hoàn tất trước khi mượn bo

## Mục tiêu và phạm vi

Tạo project Quartus Prime Lite 25.1 cho DE2-115 (`EP4CE115F29C7`), compile/fitter/STA thực tế, bitstream SRAM `.sof`, bằng chứng build gắn với source và hướng dẫn nạp/thử. Trạng thái đích là `SOFTWARE_READY / HARDWARE_PENDING`: người dùng chưa có bo. Không giả lập kết quả JTAG, đo điện áp, UART hoặc thử bo; không push/publish.

SPEC TARGET-v1.0 §11–14, `docs/spec/pins.json` và CSV Terasic trong repo là hợp đồng. Tất cả logic dùng clock 50 MHz, top `de2_115_apb_uart_bringup`, đúng sáu file TARGET và wrapper. Giữ nguyên RTL nếu các phép đo không chỉ ra lỗi chức năng cần sửa; mọi sửa RTL phát sinh phải có kiểm thử và cập nhật nguồn bằng chứng.

## Phương án đã cân nhắc

1. Thêm cấu hình Quartus riêng, giữ RTL đã kiểm chứng, đánh dấu synchronizer/preserve bằng QSF, đánh giá mọi cảnh báo có nguồn gốc rõ. Chọn phương án này vì không thay hành vi hoặc làm lỗi thời bằng chứng DV trước đó chỉ để thay cú pháp thuộc tính.
2. Thêm thuộc tính riêng của Altera vào RTL. Chỉ dùng nếu QSF không giữ/nhận đúng chuỗi trong netlist thực tế; cách này thay hash RTL và cần kiểm chứng lại phần bị ảnh hưởng.
3. Chỉ tạo `.sof` với clock sơ lược. Loại vì không đáp ứng review CDC/reset, pin và timing của SPEC.

Các lựa chọn triển khai trên là quyết định của người thực hiện trong phạm vi người dùng đã giao; không cần hỏi xác nhận từng bước theo AGENTS.md.

## Tổ chức và hợp đồng kiểm chứng

- `fpga/de2_115/`: project mở được bằng GUI, pin assignments và SDC có chú thích từng nhóm giao tiếp.
- `fpga/scripts/`: kiểm tra project thực qua Quartus Tcl và xuất kiểm tra sau fitter/STA.
- `tools/build_fpga.py` và các helper/test cần thiết: chạy build, kiểm tra bằng chứng/độ mới của source, tạo manifest và gói nạp. Không báo PASS nếu báo cáo thiếu, có slack âm hoặc artifact không khớp nguồn.
- `build/fpga/`: sản phẩm sinh ra; source/config lưu trong Git, tách khỏi DB của Quartus.
- `docs/06_FPGA_Implementation.md`: kết quả, ngoại lệ được đánh giá, hướng dẫn nạp và phiếu thử bo để trống kết quả thực tế.

Pin checks phải đối chiếu 65 port RTL, JSON/CSV, assignment thực được Quartus load và kết quả fitter; không chỉ kiểm số lượng. Tất cả unused physical pins được cấu hình input tri-state. Đánh giá rõ profile JP7 2.5 V và JP6 3.3 V trước nạp.

SDC phải giữ timing giữa các tầng đồng bộ. Chỉ loại quan hệ pha từ input bất đồng bộ tới tầng đầu; KEY0 chỉ loại tới chân reset của reset_sync. Giữ recovery/removal từ reset_sync[1] tới logic nội bộ. Đầu ra UART/LED/HEX có budget clock-to-output 0..20 ns, không tạo clock nhận giả cho CP2102. Dùng `derive_clock_uncertainty`, kiểm mọi corner do Quartus cung cấp, không chỉ slow setup.

Kiểm chứng phải gồm setup, hold, recovery, removal, minimum pulse width, clock, matched/ignored exceptions, synchronizer chain và review đường chưa ràng buộc. Các endpoint không dùng/constant và thuộc tính `async_reg` không được Quartus hiểu phải được ghi rõ, không che cảnh báo bằng wildcard.

## Bàn giao

Bản repo trên ổ D, `.sof` cùng SHA-256/manifest source, báo cáo nguyên bản, archive có source cấu hình để tái tạo, và hướng dẫn GUI Programmer. Chỉ nạp SRAM qua JTAG; không tạo luồng ghi flash vĩnh viễn. Các mục physical/electrical/board acceptance giữ `NOT_RUN` tới khi có bo thực.
