# UVM và regression TARGET-v1.0

DUT chính: `rtl/modified/pulp_apb_uart_sv/files.f`. [DV Plan](../docs/03_DV_Plan.md), [kết quả](../docs/dv/RESULTS.md), [traceability](../docs/dv/REQUIREMENT_MATRIX.md).

## Công cụ và cài đặt

Máy thực hiện có OSS CAD Suite 2026-11-08, Verilator 5.055 devel và Z3 4.15.5. `~/.local/bin/ic-eda` nạp môi trường suite. Có thể dùng tool trên PATH hoặc đặt `OSS_CAD_SUITE=/path/to/oss-cad-suite`. Runner tự tải `verilator/uvm` commit `656f20d087370a7c742e00188d20bbf30fa95339` vào `.tools/uvm`; có thể đặt UVM_HOME vào checkout đúng commit để dùng offline. Không cần cài UVM vào thư mục hệ thống.

Z3 phải có trong môi trường **chạy executable**, không chỉ lúc build. Runner sử dụng wrapper suite hoặc thêm suite/bin vào PATH và ghi version solver. Lỗi randomization/solver là FAIL, không chuyển sang random khác hoặc bỏ constrained-random.

Cần khoảng 2 GB dung lượng build và đủ RAM; mặc định `-j1`, C++ output split/group và `-O0` phù hợp máy 8 GB. Qua lần kiểm tra đã giải phóng generated object/PCH của audit cũ khi /home đầy. Không xóa source/log để làm regression xanh.

## Chạy

```bash
python tools/check_spec.py
python tools/check_dv.py
python tools/run_dv.py build
python tools/run_dv.py run --test target_apb_test --seed 17
python tools/run_dv.py regress
python tools/run_system.py
python tools/run_controller.py
python tools/run_onehot.py
python tools/report_dv.py
```

Hoặc `bash dv/sim/run_smoke.sh` chạy toàn bộ flow. Các source/testbench đã build bị đổi thì runner từ chối executable cũ. Test riêng có thể thêm `--trace` để tạo `wave.fst`; full regression tự trace nhóm errors/snapshot.

Core regression có 12 directed classes và constrained-random class chạy ba seed (17,29,101): 15 run chức năng. Hai negative controls riêng kiểm scoreboard và APB assertion, phải DETECTED. Supplementary simulation: wrapper trên profile board, controller với slave stub để inject fault/fairness, và 192 mode/one-hot cases.

`target_baud_test` thực sự phát/giải mã frame với divisor 65535; trên build C++ -O0 ca này có thể mất vài phút. Watchdog mô phỏng 2 giây và timeout wall-clock 900 giây phân biệt rõ; không dùng giới hạn 5 ms cũ để bỏ extreme divisor.

## Kết quả và coverage

`build/target/runs/<test>_seed<seed>/` chứa log, result.json, coverage.dat, waveform nếu yêu cầu. Các lần chạy lại dùng thư mục mới. Exporter chỉ nhận run PASS đúng input hashes hiện tại, có source ổn định; không merge negative/baseline/failure vào closure.

833 bin bắt buộc được định nghĩa trong `docs/dv/coverage_model.json`: format, APB, FIFO, error/IRQ, reset/config, baud/phase, concurrency, random và wrapper. Con số này chỉ là model coverage đã công khai, không phải “100% mọi tình huống UART”. Native Verilator coverage cũng được merge và lưu; code line/toggle coverage khác functional bin ledger. Kết quả native theo RTL được báo riêng, không gộp UVM library thành coverage DUT.

`dv/results/target_v2/` là bản evidence gọn đã xuất lên Git: logs/results, source manifest, coverage merge nén và chỉ mục waveform. Build binaries, thư viện UVM và PCH không commit. Exporter xác minh source hiện tại trùng nguồn đã chạy.

Exporter cũng đối chiếu trực tiếp log với JSON: đúng danh sách testcase/seed/control, mã thoát,
completion, scoreboard, UVM errors/fatals, assertion activity và functional bin counts.
Các ca kiểm tra lỗi của exporter chạy bằng `python -m unittest discover -s tools/tests -v`;
chúng là kiểm tra công cụ Python, không được cộng vào số testcase UART hoặc coverage DUT.

## Baseline và simulator khác

`dv/baseline/uvm/` giữ các testcase cũ đã sửa 15 `$sformatf` và một `$fatal`; contract vẫn là byte map/direct divider. Chúng không được chạy với TARGET. RTL vendor giữ nguyên SHA-256. Bằng chứng baseline nằm trong [review lịch sử](../docs/history/APB_UART_2026.1_REVIEW.md).

`dv/sim/run_questa.sh` đã chuyển filelist/địa chỉ môi trường sang TARGET và kiểm UVM summary, nhưng **chưa thực thi trên Questa** vì máy chưa có simulator/license đó. Không tính khả năng parse script là bằng chứng Questa. Verilator là simulator chủ yếu hai trạng thái: chưa kiểm X-propagation/metastability analog hay timing vật lý.

## Phạm vi FPGA

Wrapper đã có source và testcase simulation. Kết quả SIM của `tb_system`/`tb_controller` không thay Quartus synthesis/fitter/STA, nạp bitstream, kiểm JP6/JP7/điện áp/pin planner hoặc thử CP2102 trên board thật. Những phần này vẫn thuộc Yêu cầu 3.

Chủ dự án chọn thực hiện Yêu cầu 3 trên **Windows 11 ở cùng máy dual boot với Arch Linux**.
Xem [ghi chú bàn giao Windows](../docs/05_Windows11_FPGA_Handoff.md). Runner UVM ở đây
được kiểm trên Linux; `run_smoke.sh`/`run_questa.sh` là script Bash, `run_dv.py` dùng
module Unix `resource`. Chưa nghiệm thu chạy các runner này trực tiếp bằng PowerShell.

Audit closure v2 adds the passive RX timing observer and 23 temporal coverage bins. Run `python -m unittest discover -s tools/tests -v` for evidence mutation controls and `python tools/run_debounce_negative.py` to prove the release checker rejects an intentionally faulty scratch wrapper. The latter is excluded from native/functional coverage. After checkout, `python tools/check_published_evidence.py` verifies stored artifacts without requiring simulator binaries; this is not a new simulation.
