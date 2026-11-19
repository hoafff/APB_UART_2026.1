# Tổng hợp RTL PULP nguyên bản trên main2

**Ba phép kiểm Yosys trực tiếp đều dừng với exit 1, cả ở lõi UART lẫn top DE2-115.** Nguyên nhân chung là byte `fifo_tx_data` được giữ giá trị trong `always_comb`. Một frontend khác đã tạo được netlist cổng generic và giữ đủ tám bit latch. Backend Cyclone IV E của Yosys vẫn dừng khi gặp các latch này. **Quartus, fitter, TimeQuest, SOF và bo vật lý của main2 đang ở trạng thái `NOT_RUN`.**

Lần rà soát dùng Linux, Yosys `0.70+360 (5e740962d)`, checkout nền `5d96a7f`. Cả bảy file PULP khớp SHA-256 và Git blob tại `dfad6e04d19cc9481d3cd2750b45b970dc61271b`. Lõi dùng năm file SV, top bo dùng đúng bảy file theo thứ tự QSF. Gói bằng chứng có `manifest.json` ghi argv, exit code của từng tiến trình, hash đầu vào/netlist và log stdout/stderr đầy đủ. [Filelist bo](../fpga/de2_115/rtl.f) · [Log và manifest của 21 lệnh](../fpga/evidence/synthesis-review.zip)

## Kết quả từng luồng

| Đầu vào và phép kiểm | Lõi `apb_uart_sv` | Bo `de2_115_pulp_uart` |
|---|---|---|
| SV gốc, `read_verilog -sv; hierarchy; proc; opt; check -assert` | **1**, `proc` báo `Latch inferred … fifo_tx_data … from always_comb process`, dòng 195 | **1**, cùng latch trong module PULP |
| SV gốc, `read_slang; hierarchy; proc; opt; check -assert` | **1**, 24 đường hồi tiếp qua tám bit dữ liệu | **1**, 24 đường qua `uart.fifo_tx_data` |
| SV gốc, `read_slang; synth_intel -family cycloneive; check -assert` | **1**, `Combinational cycle through \fifo_tx_data [7]` | **1**, vòng qua `\uart.fifo_tx_data [7]` |
| `sv2v` → Verilog → Yosys generic, `synth -flatten; scc -expect 0; check -assert` | **0**, 0 SCC tổ hợp, 8 cell `$_DLATCH_N_` | **0**, 0 SCC tổ hợp, 8 cell `$_DLATCH_N_` |
| Cùng Verilog do `sv2v` sinh → `synth_intel -family cycloneive` | **1** tại `dfflegalize`, `D latches are not supported` | **1**, cùng chẩn đoán |

Slang còn báo thiếu giá trị nạp bất đồng bộ cho `regs_q[7:0]` ở dòng 314. Dòng `Build succeeded` của frontend chỉ đánh dấu bước đọc thiết kế. Với Verilator 5.055, lint mặc định của lõi cũng trả 1 với `%Warning-LATCH`. Các transcript giữ cả cảnh báo lẫn mã thoát cuối.

**Tái lập ba lỗi trực tiếp** từ thư mục gốc trên Linux, chạy riêng từng lệnh và đọc `$?` ngay sau lệnh. Khi chạy qua bộ công cụ đã dùng trong lần kiểm này, thay `yosys` bằng `"$HOME/.local/bin/ic-eda" yosys`.

```sh
yosys -p 'read_verilog -sv rtl/vendor/pulp_apb_uart_sv/*.sv; hierarchy -check -top apb_uart_sv; proc; opt; check -assert'
yosys -p 'read_slang --top apb_uart_sv rtl/vendor/pulp_apb_uart_sv/*.sv; hierarchy -check -top apb_uart_sv; proc; opt; check -assert'
yosys -p 'read_slang --top apb_uart_sv rtl/vendor/pulp_apb_uart_sv/*.sv; synth_intel -family cycloneive -top apb_uart_sv; check -assert'
```

## Byte giữ lại có vào FIFO không?

Với điều khiển 0/1 ổn định tại cạnh clock, `fifo_tx_valid` bằng 1 đúng khi `PSEL && PENABLE && PWRITE`, `PADDR[2:0] == 0` và `DLAB == 0`. Chính nhánh này gán `fifo_tx_data = PWDATA[7:0]`. Khi điều kiện sai, latch giữ byte trước và `fifo_tx_valid` bằng 0. Trong netlist sau `proc; opt`, D của latch rộng 8 bit nối thẳng đến `PWDATA[7:0]`, Q là `fifo_tx_data` và tải dữ liệu duy nhất là `uart_tx_fifo_i.data_i`. [Giải mã ghi THR](../rtl/vendor/pulp_apb_uart_sv/apb_uart_sv.sv#L195-L229) · [Kết nối FIFO](../rtl/vendor/pulp_apb_uart_sv/apb_uart_sv.sv#L140-L162)

Tại cạnh lên ngoài reset, mảng FIFO chỉ ghi khi `valid_i && !full`. Do đó **mọi lần thực sự ghi một ô đều lấy byte hiện tại trên APB**. Khi FIFO đầy, APB vẫn hoàn tất với `PREADY=1`, `PSLVERR=0`, kể cả nếu FIFO pop ngay cạnh đó. Khi `clr_i` có hiệu lực, số phần tử và con trỏ về 0. Nhánh ghi mảng vẫn có điều kiện riêng như trên. Tính chất này áp dụng cho mô hình số đã ổn định quanh cạnh lấy mẫu. Timing vật lý cần bằng chứng sau fit. [Điều kiện full, ghi ô, clear và cập nhật con trỏ](../rtl/vendor/pulp_apb_uart_sv/io_generic_fifo.sv#L46-L113)

**Mô phỏng đối chiếu.** Icarus chạy song song SV gốc và netlist cổng generic của lõi. Trong 41.984 chu kỳ, 83.968 lần lấy mẫu toàn bộ `PRDATA, PREADY, PSLVERR, tx_o, event_o` trước và sau cạnh lên đều khớp. Oracle riêng kiểm con trỏ, số phần tử và cả 16 ô nhớ sau mỗi cạnh. Có 273 lần ghi với đủ 256 giá trị byte, 7 lần bị từ chối khi đầy, 2 lần ghi divisor qua DLAB, một lần clear FIFO và reset giữa lúc TX bận. Có 41.532 mẫu không phát valid dù byte trên bus khác byte giữ. Peer RX gửi `A6` và RBR trả đúng `A6`. Đảo một bit byte kỳ vọng làm oracle dừng ở chu kỳ 13, ô 0, exit 1. Đây là so sánh hữu hạn ở lõi. Top bo đã qua kiểm cấu trúc generic trong bảng. [Testbench và oracle](../fpga/sim/tb_tx_synthesis.sv)

## Tái lập netlist generic

Dùng `sv2v v0.0.13` với tùy chọn mặc định để chuyển ngôn ngữ trong thư mục tạm. Verilog trung gian giữ nhánh gán có điều kiện. Yosys suy ra một `$dlatch` rộng 8 bit trước tối ưu và tám latch một bit sau ánh xạ generic. Giữ project Quartus dùng trực tiếp các file SV đã ghim. [Bản phát hành sv2v v0.0.13](https://github.com/zachjs/sv2v/releases/tag/v0.0.13)

```sh
# Bắt đầu từ gốc repo, với sv2v, yosys, iverilog và vvp trên PATH.
repo=$PWD
run_dir=$(mktemp -d)
cd "$run_dir" || exit 1
ln -s "$repo/rtl" rtl
ln -s "$repo/fpga" fpga
sv2v -w core.v rtl/vendor/pulp_apb_uart_sv/*.sv
yosys -p 'read_verilog core.v; hierarchy -check -top apb_uart_sv; proc; opt; check -assert; write_json core-proc.json; synth -flatten -top apb_uart_sv; scc -expect 0; check -assert; stat; rename apb_uart_sv apb_uart_sv_mapped; write_json core-generic.json; write_verilog -noattr core-generic.v'
iverilog -g2012 -s tb_tx_synthesis -o compare.vvp fpga/sim/tb_tx_synthesis.sv rtl/vendor/pulp_apb_uart_sv/*.sv core-generic.v
vvp compare.vvp
vvp compare.vvp +negative-store  # oracle sai có chủ ý, exit 1
yosys -p 'read_verilog core.v; synth_intel -family cycloneive -top apb_uart_sv; check -assert'
```

## Kiểm tra trên DE2-115

Trên Windows, biên dịch revision `de2_115_pulp_uart`, kiểm thông báo latch và vòng tổ hợp trong Analysis & Synthesis rồi đối chiếu fitter và TimeQuest ở cả ba góc. Ghi SHA-256 của SOF trước khi nạp và điền phiếu thử trên bo. [Hướng dẫn build và bằng chứng cần giữ](05_FPGA_Windows.md)
