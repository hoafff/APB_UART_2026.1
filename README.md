# APB_UART_2026.1 — Yêu cầu 1: Specifications (Draft v0.1)

Repo đích: https://github.com/hoafff/APB_UART_2026.1

## Đọc tài liệu theo thứ tự

1. [`docs/01_System_Specification.md`](docs/01_System_Specification.md): bản SPEC hệ thống và DUT, có mã `REQ_...` làm cơ sở cho DV Plan.
2. [`docs/00_RTL_Guide_Discrepancies.md`](docs/00_RTL_Guide_Discrepancies.md): bảng đối chiếu giữa hướng dẫn của thầy và hành vi RTL nguồn, bao gồm bằng chứng và hướng xử lý.
3. [`reference/Huongdan_UART.md`](reference/Huongdan_UART.md): bản hướng dẫn gốc được giữ nguyên để đối chiếu.

## Nguồn RTL cố định

`pulp-platform/apb_uart_sv`, branch `pulpinov1`, commit:

`dfad6e04d19cc9481d3cd2750b45b970dc61271b`

https://github.com/pulp-platform/apb_uart_sv/tree/dfad6e04d19cc9481d3cd2750b45b970dc61271b

*Chưa sao chép RTL vào bộ tài liệu này; khi triển khai dự án, lấy đúng 5 file trong `src_files.yml` theo commit cố định. Tránh add đồng thời `apb_uart.sv` và `apb_uart_sv.sv` vì trùng định nghĩa module.*

## Trạng thái

- SPEC v0.1: hoàn thành bản thảo bằng đối chiếu tĩnh với RTL; **chưa sign-off**.
- DV Plan / UVM: chưa bắt đầu (yêu cầu 2).
- FPGA / Quartus: chưa bắt đầu (yêu cầu 3).
- Các điểm cần mô phỏng hoặc kiểm tra board được liệt kê trong phần OPEN của SPEC.

> Quy tắc: lấy hướng dẫn của thầy làm khung tích hợp và phạm vi, còn các giá trị/đặc tính kỹ thuật của DUT dựa trên RTL thực tế. Khi có khác biệt, ghi rõ thay vì âm thầm sửa hoặc bỏ qua.