# Thay đổi RTL theo TARGET-v1.0

Baseline PULP commit `dfad6e04d19cc9481d3cd2750b45b970dc61271b` được giữ bất biến trong `rtl/vendor/pulp_apb_uart_sv`; bản target và filelist riêng nằm trong `rtl/modified/pulp_apb_uart_sv`. Giữ LICENSE và attribution ETH Zurich/University of Bologna. Đây là bản triển khai sửa theo hợp đồng dự án, không tuyên bố tương thích đầy đủ 16550 hoặc là project đã chạy của giảng viên.

| Khối | Thay đổi | Yêu cầu chính | Kiểm chứng |
|---|---|---|---|
| apb_uart_sv | Decode word/full address, error responses, DLAB/masks/reset; IRQ integrated pending/priority/clear | APB/REG/IRQ | UVM APB/IRQ/concurrency |
| uart_tx | Bit=16D, start không thừa clock; none/odd/even, 5–8/1–2; per-frame config, next frame không idle bắt buộc | TX/BAUD | 24 modes, 192 one-hot cases, D extremes, snapshot |
| uart_rx | 3FF, phase riêng, majority7/8/9, frame-complete atomic data/errors, FE từng stop, break/rearm, config snapshot | RX/BAUD | Clean/error/phase/noise/config/reset tests |
| uart_fifo | Capacity1/16, không empty bypass, full+pop nhận push; per-entry metadata/ack; clear priority | FIFO/REG | Full/drop/wrap/clear/concurrency |
| de2_uart_controller | Sáu init, polling, independent manual/echo slots, fairness, hold, sticky LED/error handling | SYS | System simulation + injected slave-fault unit test |
| de2_115_apb_uart_bringup | Reset sync, input synchronizers, 500000-cycle debounce, HEX/LED; 65 port bits | RST/SYS | Actual-port checker, system simulation default parameters |

Controller có các trạng thái chức năng trong guide, thêm pha quyết định/arbiter nội bộ để chốt snapshot và tránh ghi đè pending. Profile ngoài vẫn là sáu giao dịch init, init trong 32 clock, poll 5000 clock, các mode SW/KEY trong SPEC. Không dựa vào số file hay số encoding state để đánh giá đúng chức năng.

Thay đổi compatibility có chủ đích: địa chỉ 0/4/8/C/14; divisor 27 cho board thay direct divisor433; FIFO off reset IIR=01; FCR enable thật; LCR EPS thật; PSLVERR cho access sai/full/D0; clear/error semantics theo SPEC. Test baseline phải migrate trước khi chạy target.

Xem [RESULTS.md](dv/RESULTS.md) để biết revision/run thực sự đã kiểm. Chưa có Quartus/resource/STA hoặc hardware sign-off.
