# Bằng chứng bổ sung cho audit closure

Gói core có thể kiểm lại bằng `python tools/check_published_evidence.py`; kết quả ở `../target_v2/`. Thư mục này giữ thêm các kiểm tra phục vụ lần sửa AUD-01…05 ngày 12/11/2026. Không merge artifact ở đây vào coverage core.

- `checks.json`: commands, return codes, input hashes, kiểm guard với substitution trên manifests thật, native recount và các kết quả bên dưới.
- `unit_tests.log`: 24 tests; chạy lại `python -m unittest discover -s tools/tests -v`.
- `spec.log`, `dv.log`, `archive_validation.log`: kết quả các checker cùng tên trong `tools/`.
- `rtl_lint.log`: lint top `de2_115_apb_uart_bringup`, không error; warning giữ nguyên. Command đầy đủ trong checks.json.
- `extra_uvm_runs.json`: random seeds 20261112 và 20261113, cùng build với regression core. Chạy lại `python tools/run_dv.py run --test target_random_test --seed <seed>` sau build.
- `debounce_negative.json`: mutant nhả tức thì, verdict DETECTED với diagnostic exact-release. Chạy lại `python tools/run_debounce_negative.py`.
- `standalone_runs.json`: RX/FIFO độc lập dùng stimulus/oracle của audit; source hashes đã đối chiếu với bản sửa. Đây là manifest audit riêng, không phải schema build-bound của core.
- `additional_artifacts.zip`: raw logs và native artifacts của extra seeds; log/mã mutant; mã TB/runner/log của probe độc lập. Khi tái lập probe, giữ layout hai thư mục ngang hàng `APB_UART_2026.1/` và `audit/`, chạy từ repo: `python ../audit/run_standalone.py rx` hoặc `fifo`.
- `artifact_sha256.json`: SHA-256 của các file trong snapshot này. Không phải chữ ký chống người có quyền sửa đồng thời manifest và artifact.

Các lệnh đã chạy trên Arch Linux/Verilator; Windows, Questa, Quartus/fitter/STA và board vẫn NOT_RUN. Không đưa executable hoặc thư viện UVM vào Git.
