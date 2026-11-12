# Review và kiểm chứng gói FPGA

Ngày 12/11/2026. Phạm vi: hoàn tất phần chuẩn bị phần mềm của Yêu cầu 3;
phần cứng chưa có. Không push, publish, nạp bo hay ghi flash.

## Checklist

- [x] Xác định đúng checkout/nhánh và giữ nguyên RTL/DV đã có.
- [x] Quartus preflight: đúng chip/top/sáu source, 65 assignment duy nhất.
- [x] Full compile có `.sof`; 20 warning được phân loại, không Error/Critical Warning.
- [x] Audit post-fit ở ba corner: setup/hold/recovery/removal/pulse width,
  reset release và chuỗi đồng bộ; UCP=0, ignored SDC=0.
- [x] Build/verify/package CLI có kiểm tra hash và từ chối dữ liệu thiếu/hỏng.
- [x] Review độc lập, sửa lỗi provenance mô phỏng bằng kiểm thử trước/sau.
- [x] Hướng dẫn nạp, điện áp/jumper, UART và phiếu thử bo để NOT_RUN.
- [ ] Nghiệm thu trên DE2-115 + CP2102 thật: chưa có hardware.

Log và manifest trong `build/fpga/` của gói bàn giao là bằng chứng cho chính
bản build đó. Ngày/commit/hash không được suy ra chỉ từ văn bản này.

## Review độc lập

Reviewer đã đọc cấu hình, code, báo cáo nguyên bản và chạy `verify` cùng các
unit test. Kết luận: không có lỗi Critical, không tìm thấy lỗi pin/timing/reset.
TX AB22, RX AB21, KEY0 M23, CLOCK_50 Y2 khớp. Worst setup 5.016 ns, hold
0.181 ns; các phép đo recovery/removal/pulse width cũng dương ở ba corner.

Một lỗi Important đã sửa: trước đây manifest chưa niêm phong ba testbench
mô phỏng; verify cũng chưa đối chiếu trạng thái/số đếm với log. Probe thực tế
trên gói giải nén tái hiện cả ba trường hợp chấp nhận sai trước sửa. Bản sửa
hash testbench trước/sau chạy, yêu cầu log đã niêm phong khi PASS, và kiểm lại
kết quả từ nội dung log. NOT_RUN phải có lý do, không được giữ số đếm PASS cũ.

Reviewer còn nêu một điểm tài liệu nhỏ: `package` cần Git checkout, không chỉ
Git executable. Đã ghi rõ; `verify` và `build` vẫn chạy từ ZIP giải nén.

## Kiểm thử

- 13 ca release gate ban đầu: RED khi chưa có validator → GREEN.
- Hai ca bổ sung cho mô phỏng: RED → GREEN; tổng **15 unit test PASS**.
- Probe gói giải nén: sửa nguồn/SOF bị từ chối; chạy preflight Quartus tại
  đường dẫn mới có dấu cách thành công; hash/CRC archive khớp.
- Probe sửa review: thay testbench, thiếu hash log mô phỏng, sửa số đếm đều
  bị từ chối; NOT_RUN không có mô phỏng được chấp nhận; NOT_RUN mang số đếm cũ
  bị từ chối.
- `check_spec.py` và `check_dv.py` PASS. Ba bench Questa có số completion
  4.027.274 / 46 / 2.361, 192 frame onehot, không lỗi.
- Full unittest discovery Windows: test FPGA đạt; `test_report_dv` cũ không
  import được vì thiếu module Unix `resource`. Không coi toàn bộ suite là PASS.

## Các quyết định và giới hạn

1. Tiếp tục checkout D trên nhánh riêng, tránh tạo lại/copy công việc đã có.
2. Giữ nguyên RTL và runner DV Unix; không làm lỗi thời bằng chứng Yêu cầu 1–2.
3. Chấp nhận có điều kiện 20 warning đã review; điện áp, drive/slew và AN447
   cần kiểm trên bo. Không sửa RTL hoặc dòng ngõ ra chỉ để làm biến mất warning.
4. Ghi đúng kết quả fitter: unused pins là tri-state **có weak pull-up**.
5. Tool identity dùng edition/build/version từ Quartus; SHA-256 ràng buộc
   nguồn/cấu hình/testbench/bitstream/báo cáo. Không phải attestation của toàn
   bộ toolchain và không đảm bảo SOF tái tạo bit-for-bit qua mọi máy/phiên bản.
6. Chỉ chuẩn bị nạp SRAM. Driver thiết bị, điện áp/overshoot, oscillator,
   vị trí jumper/header, JTAG/UART và MTBF thực nghiệm chưa được nghiệm thu.
7. Giữ nhánh/checkout cục bộ. Không merge/push/deploy trong lần bàn giao này.
