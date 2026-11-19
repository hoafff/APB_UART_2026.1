# Chạy UVM trên IP APB UART PULP

Từ thư mục gốc của checkout hoặc của ZIP đã giải nén, chạy lệnh sau để biên dịch một lần và chạy bộ hồi quy. Dùng Python 3.9+, Git, GNU make, G++, Z3 và Verilator hỗ trợ UVM, timing, constrained random và covergroup. Phiên bản đã chạy và số liệu chi tiết nằm trong [kết quả](../docs/DV_RESULTS.md).

```sh
python3 dv/run.py regress --jobs 2
python3 dv/run.py verify
```

`regress` ghi vào thư mục mới dưới `dv/.work/runs/` và in đường dẫn. `verify` mặc định kiểm chứng hồ sơ bàn giao trong `dv/evidence/`. Để kiểm lại lần chạy của mình, dùng `python3 dv/run.py verify --out PATH_TO_RUN`. Lệnh này chỉ cần Python và cây nguồn đi kèm. Kế hoạch giải thích các ca, điểm lấy mẫu và quy tắc đếm. [DV Plan](../docs/03_DV_Plan.md)

Runner dùng `verilator` và `z3` trên `PATH` hoặc wrapper `~/.local/bin/ic-eda`. Có thể đặt `IC_EDA` thành đường dẫn tuyệt đối tới wrapper nhận lệnh EDA làm đối số thứ nhất. Lần đầu, runner lấy đúng commit UVM `656f20d087370a7c742e00188d20bbf30fa95339` vào cache. Để chạy offline, đặt `UVM_HOME` trỏ đến **gốc Git checkout UVM** có `src/uvm_pkg.sv` ở đúng commit này. Cây nguồn dự án có thể đến từ ZIP. [Nguồn UVM đã khóa](https://github.com/verilator/uvm/tree/656f20d087370a7c742e00188d20bbf30fa95339)

```sh
python3 dv/run.py run --case registers
python3 dv/run.py run --case random --seed 29
python3 dv/run.py run --case baud --inject tx
python3 dv/run.py run --case baud --inject rbr
```

Hai lệnh cuối cố ý đảo bit 0 của một giá trị kỳ vọng. Ca chạy riêng trả **1** khi bắt đúng sai lệch. Hồi quy yêu cầu cả hai control bắt đúng ID, cặp byte, đúng một `UVM_ERROR`, không có `UVM_FATAL` và simulator thoát lỗi. Ca bình thường trả **0** khi hoàn tất và đúng các điều kiện của ca. Lỗi hạ tầng, sai bằng chứng hoặc ca có lỗi ngoài dự kiến trả khác 0. Mỗi tiến trình có watchdog ở thời gian mô phỏng và timeout ngoài simulator.

`--work PATH` chọn cache riêng, `--out EMPTY_DIR` chọn đường dẫn kết quả mới. Định danh build bao gồm mã biên dịch, phiên bản công cụ, cây UVM, cờ và mức song song. Runner kiểm SHA-256 của binary và log trước khi dùng lại cache. `regress` chạy tuần tự các tiến trình mô phỏng và giới hạn biên dịch theo `--jobs`, mặc định 2.

## Các probe bổ sung trên Linux

Chạy `python3 dv/probes/run.py` để lặp lại các phép thử phân giải theo cạnh FIFO/APB, reset giữa khung, hai đầu divisor và khung RX bất thường. Bộ probe có checker control và log riêng. [Kết quả probe](probes/main.log) · [Replay từ cây thiếu Git](evidence/supplement-archive-replay.log)

## Questa

Trên môi trường có license và `vlib`, `vlog`, `vsim` trong `PATH`, dùng cùng cây UVM đã khóa. Có thể dùng `py -3` trên Windows thay cho `python3`. Driver tạo thư viện `work` mới theo từng lần chạy, compile filelist bằng `vlog -sv -mfcu`, truyền `-sv_seed`, và giữ `build.log`, `run.log` cùng `coverage.ucdb` của ca thành công.

```sh
python3 dv/questa.py --case modes --seed 17
python3 dv/questa.py --case random --seed 29
python3 dv/questa.py --case baud --inject tx
```

Tcl trả mã kết thúc từ `tb_top.bench_exit`. Python kiểm tiếp DONE, số so sánh, coverage và tổng severity trong transcript. Quy ước exit cho control giống runner Verilator. **Chưa chạy mô phỏng Questa** trong hồ sơ này. [Driver Questa](questa.py)
