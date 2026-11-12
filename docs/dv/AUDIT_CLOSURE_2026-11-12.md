# Sửa và kiểm lại yêu cầu 1–2 — audit closure v2

Base: `9edea82b6a969a0c9b63a03ecbf8ff6c30bade2e`. **Đã đóng AUD-01…05 trong phạm vi SPEC và kiểm chứng mô phỏng của Yêu cầu 1–2.** Các nghĩa vụ phần cứng của Yêu cầu 3 vẫn NOT_RUN. Không còn finding đã xác nhận cản trở bàn giao Yêu cầu 1–2 trong phạm vi audit này.

| Finding | Thay đổi | Phép kiểm phân biệt |
|---|---|---|
| AUD-01 / P2 | RX passive observer lấy rx_i/clock/reset/APB config; công thức sample tuyệt đối; APB pre-edge, arrival post-edge; flush cùng cạnh bỏ completion | TC13: LSR/RBR trước/đúng/sau enqueue D1/D27; TC09 DLL/DLM cùng start; suite RX errors/phase/config |
| AUD-02 / P2 | Native coverage gắn run/build ID, hash/size/path/inode; loại negative/failure và file không có payload | Unit tests thay bằng negative/duplicate/missing/foreign-rehashed coverage; actual merge sau guard |
| AUD-03 / P2 | Build content ID gắn binary/dependencies/flags; kiểm source/binary/UVM trước/sau; supplemental dùng cùng schema | Unit tests sai binary/tool/UVM, rỗng/thiếu source, sửa build flags; runtime binding và archived replay |
| AUD-04 / P2 | Đo nhả N−1/N và bounce; kiểm lại một pulse sau stable release | RTL gốc PASS; mutant nhả tức thì bị SYSTEM_CHECK exact release bắt |
| AUD-05 / P3 | SPEC §13.1/handoff ghi JP7=2.5V short5–6, JP6=3.3V short7–8 | check_spec, 65 pin CSV giữ nguyên; trạng thái jumper thật NOT_RUN |

Các khoảng trống bổ sung đã thêm testcase: RX rearm31/32 clocks sau break tại D2; live hold/echo quanh SETUP; reset manual/echo pending; IRQ/manual wake≤8 clock; board poll5000; cả16 glyph HEX TX/RX. Functional model tăng 810→833 bins (23 nghĩa vụ thêm), không coi tỷ lệ này là chứng minh mọi trạng thái UART.

Không sửa RTL TARGET hoặc vendor trong bản này. Baseline/upstream được giữ nguyên. Expected không lấy từ DUT data/state/done; các probe nội bộ còn lại chỉ dùng căn stimulus collision. Không nới SPEC để làm test đạt.

Kết quả cuối nằm trong [RESULTS.md](RESULTS.md) và `dv/results/target_v2/`: 15/15 UVM thường PASS, 2/2 negative controls DETECTED, 3/3 simulation bổ sung PASS, **833/833 functional bins**. Hai seed 20261112/20261113 cũng PASS nhưng không cộng vào coverage closure. Bộ guard có 24/24 unit tests PASS. System thực hiện 4.027.274 checks/43 TX frames, controller 46 checks, one-hot 2.361 checks/192 frames. Mutant nhả debounce sai bị bắt bằng diagnostic exact-release.

Check SPEC/DV đạt: 80 requirements, 19 testcase definitions và 65 chân; đây là kiểm tài liệu/truy vết. Kiểm RX độc lập đạt 22.916 checks/2.893 frames; FIFO độc lập đạt 131.208 checks/32.802 bước. Lint top FPGA không có error, còn 10 warning đã ghi log. Evidence bổ sung, commands và source hashes lưu tại `dv/results/audit_closure_20261112/`.

Native coverage: line 130/135, branch 149/156, expr 279/309, toggle 1975/3030. **1.097 điểm chưa hit được giữ mở**, không tự loại để nâng tỷ lệ. Xem [phân tích khoảng trống](NATIVE_COVERAGE_REVIEW.md). Functional coverage là tập nghĩa vụ công khai; không phải chứng minh mọi trạng thái hoặc 100% native coverage.

Evidence cũ `target_v1/` và `review_20261112/` là snapshots lịch sử, không dùng để chứng minh source mới. Gói v2 giữ raw log, per-run native coverage, build/source/UVM/binary identities và checksum; `python tools/check_published_evidence.py` đã kiểm gói xuất thành công mà không gọi simulator. Các run chạy với HEAD base và working tree có bản sửa chưa commit; giữ nguyên provenance này, nhận diện bản đã chạy bằng toàn bộ source hashes và build IDs. Commit giao cuối phải chứa đúng các hash ấy.

Tái lập phần chính: `bash dv/sim/run_smoke.sh`. Chạy thêm seed bằng `python tools/run_dv.py run --test target_random_test --seed 20261112` và tương tự seed 20261113. Không cần Quartus cho các phép kiểm này; native Windows/Questa vẫn chưa được nghiệm thu.

Rà soát cuối do chính agent sửa thực hiện vì phiên làm việc không có native subagent tool. Đây không phải một lượt review độc lập thứ hai. Phần cứng/Windows11/Questa/Quartus/fitter/STA/X-propagation/formal chưa được chạy và không được đóng bằng simulation.
