# Chạy UVM trên IP APB UART PULP

Tại thư mục gốc checkout hoặc ZIP đã giải nén, dùng Python 3.9+ để kiểm bộ bằng chứng đi kèm. Lệnh mặc định yêu cầu đủ 7 ca directed, 3 seed random, một replay riêng và hai control trong `dv/evidence/`. Có thể chạy cả bộ kiểm tra công cụ bằng thư viện chuẩn Python.

```sh
python3 dv/run.py verify
python3 -m unittest discover -s dv/tests -v
```

Để chạy mô phỏng mới, cần Git, GNU make, G++, Z3 và Verilator có hỗ trợ UVM, timing, constrained random và covergroup. Chọn một thư mục kết quả mới cho mỗi lần chạy. Sau khi `regress` kết thúc, có thể kiểm lại chính thư mục đó bằng Python. [Phiên bản và kết quả đã đo](../docs/DV_RESULTS.md) · [DV Plan](../docs/03_DV_Plan.md)

```sh
python3 dv/run.py regress --jobs 2 --out dv/.work/my-regression
python3 dv/run.py verify --out dv/.work/my-regression
```

Cả Verilator, Questa và bộ đọc bằng chứng kiểm bảy file PULP theo cùng danh mục SHA-256 đã khóa và kiểm filelist thực sự dùng đúng năm RTL. Khi tách ZIP chỉ để chạy DV, giữ nguyên `rtl/vendor/pulp_apb_uart_sv/`, `dv/`, `docs/spec/baseline_hashes.json` và `tools/check_upstream.py`. [Danh mục nguồn gốc](../docs/spec/baseline_hashes.json)

Runner dùng `verilator` và `z3` trên `PATH` hoặc wrapper `~/.local/bin/ic-eda`. Có thể đặt `IC_EDA` thành đường dẫn tuyệt đối tới wrapper nhận lệnh EDA làm đối số thứ nhất. Lần đầu, runner lấy đúng commit UVM `656f20d087370a7c742e00188d20bbf30fa95339` vào cache. Để chạy offline, đặt `UVM_HOME` trỏ đến **gốc Git checkout UVM** có `src/uvm_pkg.sv` ở đúng commit này. Cây nguồn dự án có thể đến từ ZIP. [Nguồn UVM đã khóa](https://github.com/verilator/uvm/tree/656f20d087370a7c742e00188d20bbf30fa95339)

```sh
python3 dv/run.py run --case registers
python3 dv/run.py run --case random --seed 29
python3 dv/run.py run --case baud --inject tx
python3 dv/run.py run --case baud --inject rbr
```

Hai lệnh cuối cố ý đảo bit 0 của một giá trị kỳ vọng. Ca chạy riêng trả **1** khi bắt đúng sai lệch. Hồi quy yêu cầu đúng ID, cặp byte, một `UVM_ERROR`, không có `UVM_FATAL` và simulator trả **1**. Ca bình thường trả **0** khi đạt tiêu chí. Watchdog mô phỏng, timeout tiến trình, sai nguồn hay hỏng bằng chứng làm phép kiểm thất bại. Để đọc lại một ca riêng, dùng `verify --out` với thư mục riêng mà `run` đã in. Nếu hợp lệ, công cụ in `Verified single run`.

`--work PATH` chọn cache riêng, `--out EMPTY_DIR` chọn đường dẫn kết quả mới. Định danh build bao gồm mã biên dịch, phiên bản công cụ, cây UVM, cờ và mức song song. Runner kiểm SHA-256 của binary và log trước khi dùng lại cache. `regress` chạy tuần tự các tiến trình mô phỏng và giới hạn biên dịch theo `--jobs`, mặc định 2.

## Các probe bổ sung trên Linux

Chạy `python3 dv/probes/run.py` để lặp lại các phép thử phân giải theo cạnh FIFO/APB, reset giữa khung, hai đầu divisor và khung RX bất thường. Bộ probe có checker control và log riêng. [Kết quả probe](probes/main.log) · [Replay từ cây thiếu Git](probes/archive-replay.log)

## Questa

Trên môi trường có license và `vlib`, `vlog`, `vsim` trong `PATH`, dùng cùng cây UVM đã khóa. Có thể dùng `py -3` trên Windows thay cho `python3`. Driver tạo thư viện `work` mới theo từng lần chạy, compile filelist bằng `vlog -sv -mfcu`, truyền `-sv_seed`, và giữ `build.log`, `run.log` cùng `coverage.ucdb` của ca thành công.

```sh
python3 dv/questa.py --case modes --seed 17
python3 dv/questa.py --case random --seed 29
python3 dv/questa.py --case baud --inject tx
```

Tcl trả mã kết thúc từ `tb_top.bench_exit`. Python kiểm tiếp DONE, số so sánh, coverage và tổng severity trong transcript. Quy ước exit cho control giống runner Verilator. **Chưa chạy mô phỏng Questa** trong hồ sơ này. [Driver Questa](questa.py)
