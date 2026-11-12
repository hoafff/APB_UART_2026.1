# DV Plan v1.0 — TARGET APB UART / DE2-115

Ngày: 12/11/2026. Đầu vào chuẩn: [SPEC TARGET-v1.0](01_System_Specification.md). Đây là kế hoạch và hợp đồng kiểm chứng Yêu cầu 2. Kết quả thực thi được quản lý riêng trong [báo cáo regression](dv/RESULTS.md); tên testcase hoặc source đã viết không chứng minh PASS.

## 1. Mục tiêu và phạm vi

Kiểm chứng APB slave, register bank, clock-enable 16×, TX/RX 5–8 bit, none/odd/even parity, 1/2 stop, FIFO capacity 1/16, PE/FE/OE/BI, ngắt và reset/configuration của TARGET-v1.0. Bản PULP nguyên gốc được giữ trong `rtl/vendor/`; DUT dùng trong regression ở `rtl/modified/`. Không dùng kết quả baseline để đóng requirement target.

Phân định nghiệm thu:

- **DUT simulation:** directed, automatic regression, constrained-random, scoreboard, assertions và functional coverage của IP.
- **SYSTEM simulation:** reset/debounce/APB master/KEY/SW/HEX/LED/echo/hold và backpressure của wrapper. Kết quả phải gắn nhãn SIM; wrapper đã có trong rtl/fpga và được kiểm bằng tb_system/tb_controller.
- **DOC:** source provenance, filelist, register/requirement/pin consistency.
- **FPGA:** Quartus compile/fitter/STA, JP6/điện áp, đấu dây và dữ liệu trên DE2-115 thật; thuộc Yêu cầu 3. Kết quả simulation không đóng các mục này.

80 yêu cầu trong SPEC đều có dòng truy vết, kể cả mục phần cứng chưa chạy. Một requirement chỉ CLOSED khi **toàn bộ** nghĩa nghiệm thu, cấu hình và coverage bắt buộc của nó có bằng chứng. Một test PASS một seed không tự động đóng mọi requirement được liên kết với test đó.

## 2. Kiến trúc môi trường UVM

```text
uvm_test / sequences ──> APB sequencer ──> APB driver ──> DUT APB
                                                  ┌── APB monitor ──────────┐
UART RX BFM (independent real-time peer) ──> DUT RX │                         v
UART TX monitor <────────────────────────── DUT TX └──────────────> scoreboard
                                                                    │       │
SVA checker <── APB + reset + IRQ + FIFO bounds                 coverage   errors
                                                                    │
                                                      run manifest / logs / waveform
```

Tập tin sở hữu:

| Thành phần | Source | Vai trò |
|---|---|---|
| Interface | `dv/uvm/uart_apb_if.sv` | Port APB/UART và probe căn thời điểm stimulus |
| APB agent | `dv/uvm/include/apb_agent.svh` | Driver/monitor/sequencer; sample tại completion trước NBA |
| Types/coverage | `dv/uvm/include/uart_types.svh` | Transaction, frame config, covergroup 48 mode, ledger |
| UART agents | `dv/uvm/include/uart_agents.svh` | BFM serial bất đồng bộ; TX decoder kiểm từng clock của mỗi bit |
| Reference/scoreboard | `dv/uvm/include/uart_scoreboard.svh` | Register, FIFO, metadata, IRQ expected từ giao dịch/serial stimulus |
| Tests/sequences | `dv/uvm/include/uart_tests.svh` | Directed và constrained-random; explicit expected checks |
| Assertions | `dv/assertions/apb_uart_assertions.sv` | APB phase/stability/ready/idle/zero-extend, reset, FIFO bounds, IRQ encoding |
| Top | `dv/uvm/tb_top.sv` | 50 MHz, reset, DUT, SVA, watchdog, optional FST |
| Runner | `tools/run_dv.py` | Build/run/replay, provenance, giữ failures, machine-readable results |

APB driver phát tại cạnh xuống; monitor lấy dữ liệu tại cạnh lên hoàn tất trước read side effect. Có expected PSLVERR cho giao dịch âm, không coi error hợp lệ là lỗi test. RX BFM dùng độ trễ thời gian thực và cấu hình riêng; không sao chép RX state machine/counter. TX monitor giải mã dây serial, giữ cấu hình tại start, kiểm cả stop thứ hai và bit period; chỉ sample giữa bit là chưa đủ bắt thiếu stop hoặc lệch một clock.

Probe `rx_done_probe`/`tx_ready_probe` chỉ căn thời điểm tạo collision, không cấp expected data/flags vào oracle. Test collision vẫn kiểm giá trị APB, thứ tự byte, cờ lỗi và dữ liệu sau collision. Các test RX timing độc lập không dùng probe.

## 3. Mô hình chuẩn và chính sách so sánh

### 3.1. APB/register

Decode full address 0/4/8/C/14, kiểm DLAB, mask LCR=9F/IER=07, reset LSR=60/IIR=01, FIFO-on IIR có bits C0. Unsupported/misaligned/write-LSR phải trả error và dữ liệu 0. PRDATA byte thấp và zero-extension được kiểm cả trong scoreboard và SVA. Setup-only không đổi register; back-to-back bắt buộc có SETUP mới.

### 3.2. FIFO và dữ liệu

TX model nhận đúng THR write thành công. TX start chuyển head vào frame active; clear queue không xóa frame active. RX expected nhận từ serial stimulus; capacity off/on=1/16, full drop-new và OE. Data và PE/FE/BI đi cùng entry; đọc LSR ack head và OE, đọc RBR pop một entry. Queue rỗng đọc 0, không bypass byte vừa tới cùng cạnh.

Reference queue của RX là mô hình giao dịch: thông báo frame theo BFM, không tự nhận là mô hình từng clock của synchronizer. Các test đọc sớm/collision có explicit expected theo pre-edge và probe alignment, sau đó kiểm dữ liệu/cờ thực tế. Timing majority/baud được kiểm riêng bằng stimulus serial. Không lấy internal count làm expected count.

### 3.3. Lỗi và ngắt

PE odd/even, FE từng stop, BI một entry cho khoảng low kéo dài; kiểm recovery và byte sạch/lỗi xen kẽ. RLS > RDA > THRE, mask IER, thresholds 1/4/8/14, >= threshold; IIR read chỉ ack THRE nếu mã trả về là THRE. LSR clear đồng thời overflow mới: set mới thắng. Event hạ và bit0 IIR lên 1 khi không còn nguồn enabled.

### 3.4. Reset và config

Reset hủy giao dịch/frame và pending, không replay; kiểm reset ở APB SETUP/ACCESS và các vùng start/data/parity/stop, FIFO full và IRQ. Frame active giữ D/LCR đã chốt; queued byte lấy config ở start của nó. D=0 dừng frame mới, giữ queue, active frame hoàn tất; THR mới bị error. DLL/DLM không được giả định atomic.

## 4. Phương pháp kiểm thử

**Directed:** kích chính xác reset/side effect/error/FIFO/IRQ boundaries và đo bit time. Các pattern 00/FF/55/AA giúp phân biệt dữ liệu, parity và khoảng chuyển mức; one-hot/random bổ sung trong mở rộng closure.

**Automatic:** runner compile một DUT filelist, lần lượt chạy từng UVM test, kiểm cả return code và UVM summary/test completion/checker activation, lưu JSON/log/wave/coverage. Thất bại được lưu riêng, không ghi đè bằng lần chạy xanh.

**Constrained-random:** 300 APB transactions/seed, sau đó 64 frame pairs full-duplex/seed; random data width/parity/stop/divisor/payload/error injection. Seeds nghiệm thu ban đầu 17/29/101. Random testcase phải có scoreboard và lưu seed; số seed không thay thế bin closure.

**Assertion:** runtime SVA có enable thật (`--assert`), nonvacuity bằng access/reset counters và cover properties. Đây là simulation assertions, chưa phải formal proof.

**Negative controls:** làm sai observed TX data để scoreboard báo lỗi; tạo ACCESS không SETUP để assertion bắt lỗi. Kết quả mong muốn là DETECTED, không cộng vào số testcase chức năng PASS.

## 5. Testcase chi tiết

Danh mục máy đọc được nằm trong [testcases.json](dv/testcases.json); mỗi row ghi stimulus, observer/oracle, pass/fail và requirement liên quan. Nhóm AT01..AT08 giữ đúng SPEC; một môi trường UVM có nhiều testcase, không cần nhiều top-level testbench trùng nhau.

| ID / tên | Nhóm | Stimulus bắt buộc | Observer / oracle |
|---|---|---|---|
| TC01 `target_apb_test` | AT01 | Reset values, DLAB/readback/mask; quét toàn bộ 4096 địa chỉ; setup-only/back-to-back/PSLVERR | APB monitor + register scoreboard + APB SVA |
| TC02 `target_tx_modes_test` | AT02 | 24 mode × 00/FF/55/AA, các frame queued nối tiếp | Independent TX decoder kiểm từng clock và expected THR queue |
| TC03 `target_rx_modes_test` | AT03 | 24 mode × bốn payload, RBR order/zero-extension/LSR | RX peer độc lập + expected receive queue + LSR/RBR |
| TC04 `target_tolerance_test` | AT03 | 24 mode × 3 rate × 5 phase; additional D=1/27; back-to-back | Peer real-time, data/error count/order oracle |
| TC05 `target_errors_test` | AT04 | Odd/even error; stop1/stop2; break; clean/bad/clean metadata và ack | LSR/RBR expected flags theo từng frame; recovery |
| TC06 `target_fifo_test` | AT05 | Capacity1/16, drop-new, wrap, FCR clear/toggle, clear active, THR full | Data queue, OE sticky, PSLVERR, active frame preserved |
| TC07 `target_irq_test` | AT06 | 4 thresholds; 64 source×mask cases; RLS>RDA>THRE, ack/mask/no-stuck | Independent pending model, IIR/event and source-clear reads |
| TC08 `target_reset_test` | AT07 | Reset start/data/parity/stop, APB phases, full/IRQ; recovery | Post-reset register/data/line levels; no stale queues |
| TC09 `target_snapshot_test` | AT07 | Config mid-frame/same-edge TX/RX; D0 active/paused queue/rearm | Serial captured-mode oracle; pre-edge config and retained bytes |
| TC10 `target_baud_test` | AT02 | D=0/1/27/326/65535, full measured frame | Per-clock serial waveform and completion counts; no skipped extreme |
| TC11 `target_random_test` | AT01, AT02, AT03, AT04 | 300 constrained APB + 64 full-duplex frame pairs mỗi seed 17/29/101 | Scoreboard, serial decoder, explicit counts, pinned solver/seed |
| TC12 `target_false_start_test` | AT03 | False start, rearm, 1-sample noise at center of a data bit | No phantom RBR/error; majority retains data |
| TC13 `target_concurrency_test` | AT05, AT06 | Empty/full arrival+pop, OE+ack, new-head+LSR, flush+arrival, full TX+pop+write | Pre-edge APB read data + later queue/error checks; probe only aligns stimulus |
| TC14 `tb_system` | AT08 | Default 500000-cycle debounce; N/O/E send/receive/echo/hold/errors; burst32; reset sync | Top port serial/HEX/LED, init APB monitor and independent application expected values |
| TC15 `tb_controller` | AT08 | Stub APB errors, manual overflow/same-edge acceptance, echo reserve/fairness, hold polling | Accepted writes and request ordering; explicit injected-error labels |
| TC16 `tb_tx_onehot` | AT02 | 192 N×parity×stop×one-hot cases including bits above WLS | Known single-bit expected wire/parity, no DUT parity algorithm in oracle |
| TC17 `check_spec` | DOC | 80 IDs/36 legacy mappings/65 CSV pins/timing/contract arithmetic/vendor hashes | Python document checker, not simulation |
| TC18 `check_dv` | DOC | Traceability/classes/artifacts/native coverage/requirement and source references | Python static/evidence checker, not hardware |
| TC19 `board_acceptance` | AT08 | Quartus/fitter/STA, bank/JP6/CP2102, board TX/RX/echo/parity/error capture | Manual physical evidence; NOT_RUN under Requirement 3 |

## 6. Coverage model và tiêu chí closure

| Nhóm | Bin/cross bắt buộc | Cách quan sát | Điều kiện |
|---|---|---|---|
| UART format | 24 TX + 24 RX (N×parity×stop) | Frame monitor/BFM + scoreboard; native covergroup và JSON ledger | Tất cả 48 bin, data/format checks không lỗi |
| APB | direction×mapped offset×DLAB hợp lệ, invalid/error, setup-only, back-to-back | APB monitor + register oracle/SVA | Không alias, side effect đúng; invalid bins không gộp với valid |
| FIFO | count 0/1/C−1/C; capacity1/16; wrap; full/empty push-pop; flush | Observed APB/serial transactions + collision tests + bounds assertion | Đúng data/OE/PSLVERR, không chỉ đạt count coverage |
| RX errors | parity off/odd/even, stop1/stop2 fault, break, metadata/ack | Serial stimulus + LSR/RBR readback | Error gắn đúng byte; clear không xóa lỗi mới |
| IRQ | source×mask×priority/clear, T−1/T/T+1 tại T=1/4/8/14 | IIR/event/LSR/RBR | Không ngắt giả/stuck; nguồn thấp không mất |
| Reset/config | idle/SETUP/ACCESS/start/data/parity/stop/full/IRQ; config snapshot/D0 | Directed reset, serial monitor, post-reset register reads | Không stale byte, đúng config của frame |
| Baud/RX phase | D=0/1/27/326/65535; rate=.98/1/1.02; phase=0/5/10/15/19 ns | Independent serial peer and cycle decoder | Bit=16D clock, clean data không lỗi giả |
| System | init/parity N/O/E/send/receive/echo/hold/bounce/fault/fairness | Wrapper simulation và board protocol | SIM và BOARD ghi riêng |

Native simulator coverage (`coverage.dat`) phải được lưu và merge; functional ledger xuất các bin có tên để kiểm cross/requirement rõ ràng và tái lập. Hai số liệu có phạm vi khác nhau. Code line/toggle coverage là chẩn đoán bổ sung, không thay functional coverage hoặc tự chứng minh đúng chức năng.

Một bin có stimulus nhưng test FAIL không được dùng đóng coverage đạt. Chỉ merge bin từ run PASS đúng source hash. Negative-control coverage và baseline coverage bị loại khỏi target closure. Bin chưa có code/stimulus/evidence phải giữ OPEN; không tự đổi thành exclusion. Các tổ hợp bất khả thi phải ghi lý do và requirement chấp nhận, không chỉnh cross âm thầm cho đủ 100%.

## 7. Truy vết 80 yêu cầu

[traceability.json](dv/traceability.json) và [REQUIREMENT_MATRIX.md](dv/REQUIREMENT_MATRIX.md) giữ toàn bộ ID `TGT-*`, mục SPEC, RTL owner, testcase, observer và evidence status. `tools/check_dv.py` kiểm ID không thiếu/trùng, test class có thật, đường dẫn/coverage references hợp lệ và không dùng baseline PASS cho target.

Khi một test chỉ phủ một phần requirement, row phải ghi phần còn thiếu. Các yêu cầu PHY/Quartus/STA của Yêu cầu 3 được đánh dấu `HW_PENDING`, không phải PASS hoặc tự loại khỏi scope.

## 8. Chính sách PASS/FAIL và chống kết quả rỗng

Một run PASS phải đồng thời: build thành công; executable đúng input hash; không timeout/nonzero return; UVM_ERROR=0/UVM_FATAL=0; có TEST_COMPLETED đúng test; scoreboard có comparisons >0; không pending data ngoài traffic đã hủy bằng reset/clear; assertion hoạt động; kết quả expected/observed phù hợp testcase. Các ca serial còn kiểm số frame cụ thể.

Không cho EXPECTED_FAIL vào green target regression. Nếu RTL chưa đáp ứng, target run giữ FAIL và tạo bug entry. Negative control dùng verdict riêng DETECTED/NOT_DETECTED với yêu cầu đúng diagnostic; timeout/compiler failure không được xem là phát hiện lỗi có chủ đích.

## 9. Tool, build và reproducibility

Flow đã chọn: Verilator trong OSS CAD Suite đã có trên máy, `verilator/uvm` commit `656f20d087370a7c742e00188d20bbf30fa95339` (UVM 2020.3.1), `UVM_NO_DPI`. Runner ghi version thực tế; không tuyên bố đã chạy Questa chỉ vì có script.

Verilator là simulator chủ yếu hai trạng thái; các bằng chứng này không đóng X-propagation/metastability analog hoặc electrical behavior. CDC topology/STA phải review trong flow FPGA. Regression có timed SystemVerilog/UVM/SVA/coverage thực sự; không gọi Python model là RTL simulation.

```bash
python tools/check_spec.py
python tools/run_dv.py build
python tools/run_dv.py run --test target_apb_test --seed 17
python tools/run_dv.py regress
python tools/check_dv.py
```

Có thể đặt `UVM_HOME` vào checkout đúng commit, hoặc runner tải thư viện đã pin vào `.tools/uvm`. `OSS_CAD_SUITE`/PATH hay `~/.local/bin/ic-eda` chọn công cụ. Build `-j1`, output split/group và `-O0` giới hạn RAM trên máy 8 GB. Cần đủ dung lượng cho C++/PCH/object; không commit thư viện/toolchain hoặc binary build.

Watchdog mặc định 2 giây **thời gian mô phỏng**, hỗ trợ override. D=65535 với frame 12 bit cần khoảng 251,65 ms, nên không giữ watchdog 5 ms của bản cũ. Runner có timeout wall-clock riêng và ghi rõ timeout.

## 10. Evidence ledger và quản lý lỗi

Mỗi run ghi: testcase/seed, command, simulator/UVM revision, Git HEAD và dirty state, SHA-256 toàn bộ RTL/TB/checker inputs, return code, elapsed time, UVM counts, scoreboard counters, completion marker, functional bin counts, waveform/coverage path. Hash trước và sau build phải trùng; nguồn đổi thì phải build lại.

Log fail/timeout/compiler error lưu riêng. Khi fix: ghi symptom, nguyên nhân, file/requirement, test trước/sau, affected regression. [BUG_LOG.md](dv/BUG_LOG.md) phân biệt lỗi baseline đã biết, lỗi target và lỗi testbench/tool flow. Không sửa oracle để phù hợp lỗi DUT.

## 11. Kế hoạch SYSTEM và FPGA

Các ca wrapper phải cover init sáu write/≤32 clock, debounce đúng 500000 mẫu, một send mỗi nhấn/không lặp khi giữ, manual data capture, parity chốt tại init, live hold/echo, slot backpressure/fairness, APB fault, HEX/LED polarity và sticky errors. Fault injection tại phản hồi slave phải gắn nhãn simulation stub.

Các ca board yêu cầu log hai đầu, terminal 115200 N/O/E, ảnh/video hoặc capture logic analyzer, tên bitstream và revision, Quartus/fitter/STA, pin/voltage/JP6 checklist thực tế. Chưa có board là `NOT_RUN`, không suy từ simulation rằng mạch đã chạy.

## 12. Điều kiện bàn giao Yêu cầu 2

- DV Plan và traceability cho toàn bộ SPEC, testcases có stimulus/oracle/pass-fail rõ.
- UVM source build được; directed/automatic/random chạy thực tế với bằng chứng và negative controls.
- Báo cáo coverage nêu bin đạt, bin còn mở và phạm vi; không báo 100% từ số lượng test.
- README, runner, tool pins, defect log và results thống nhất để người khác tái lập.
- Kết quả SYSTEM/FPGA còn thiếu phải ghi rõ; chỉ tuyên bố toàn bộ thiết kế đạt SPEC khi các nghĩa vụ này cũng hoàn tất.
