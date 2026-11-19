# Yêu cầu 2 · Kết quả mô phỏng IP PULP nguyên bản

**10/10 lần chạy UVM chính đạt tiêu chí**, gồm 7 ca directed và 3 seed constrained random. Scoreboard thực hiện **2.485 phép so**, monitor ghi nhận **1.315 ACCESS**, giải mã **138 khung TX**, **209 khung ở chân RX** và kiểm **202 lần đọc RBR có dữ liệu**. Replay seed 17 khớp. Cả hai negative control tạo đúng sai lệch và simulator trả 1. Tổng coverage chính là **117/117 bin chức năng đã khai báo**. Các khiếm khuyết PE/FE/OE và IRQ dưới đây được tái hiện trên IP nguyên bản. [Báo cáo từng lần chạy và từng bin](../dv/evidence/regression.json) · [Kế hoạch và oracle](03_DV_Plan.md)

## Tái lập và nhận dạng nguồn

```sh
python3 dv/run.py regress --jobs 2
python3 dv/run.py verify
```

Hồ sơ chính lấy từ clone mới của `main2`, HEAD `407b29c08f1a724980ac183081eac01e45bcdd5a`, cây sạch trước khi chép phần DV đang bàn giao. Năm file RTL đã có sẵn trong clone và khớp SHA-256 của cây làm việc. Lần chạy đó bỏ đặt `UVM_HOME`/`IC_EDA`, tự tìm wrapper cục bộ và tự lấy UVM pin `656f20d087370a7c742e00188d20bbf30fa95339`. Compile cache ban đầu rỗng. Build bằng Verilator `5.055 devel rev v5.054-129-g14bd81f66 (mod)`, G++ 16.2.1, GNU Make 4.4.1, Z3 4.15.5, 2 build jobs. Build mất 145,6 s. 13 tiến trình mô phỏng chạy tuần tự mất tổng 6,8 s trên máy này. [Transcript checkout mới](../dv/evidence/fresh-checkout.log) · [Lệnh build và tool version](../dv/evidence/build.json)

| Danh tính | Giá trị |
|---|---|
| Revision PULP | `dfad6e04d19cc9481d3cd2750b45b970dc61271b` |
| SHA-256 tập nguồn RTL, TB, filelist và runner | `da1b21f7de958606c4f0f8df03ffe223633963541a88466bc32ddeabe4fc04fb` |
| Git tree `src` của UVM | `204b3b844d57b630364a5d9774a022bf033f232a` |
| SHA-256 binary dùng ở clone mới | `319bc395fec955b0e758b9b061de3617043b3b26d92078dc782715bb929d0d0a` |

Mỗi transcript có source key, build ID và run ID. `verify` kiểm lại SHA-256, đối chiếu nguồn đang có, giải mã lại transcript, kiểm số khung từng ca, đối chiếu từng bin native với counter và tái tính tổng. Bản build có cảnh báo latch `fifo_tx_data` ở `apb_uart_sv.sv` dòng 195, cùng các cảnh báo chuyển độ rộng/kiểu. Mỗi log có hai cảnh báo thư viện UVM khi dùng `UVM_NO_DPI` (`NO_DPI_USED`, `NO_VISIT_CHECK`). Ca chính và replay đều có UVM_ERROR=0 và UVM_FATAL=0. [Manifest nguồn](../dv/evidence/manifest.json) · [SHA-256 bằng chứng](../dv/evidence/SHA256SUMS) · [Log compiler gốc nén gzip](../dv/evidence/build.log.gz) · [Đánh giá tổng hợp](02_Synthesis_Review.md)

Đã chạy lại đủ **13 tiến trình** từ ZIP chỉ gồm nguồn cần thiết cho DV, giải nén vào thư mục mới thiếu `.git`, dùng checkout UVM offline đã khóa và một cache build rỗng khác. Build thứ hai mất 142,3 s. Cả 13 verdict, chẩn đoán control, hash stimulus và mọi bin trùng với clone mới. Cây `main2` đang làm việc cũng chạy lại đủ 13 tiến trình với cache đã xác minh. Các lần lặp này tách khỏi số đếm chính. [Transcript ZIP không có Git](../dv/evidence/source-zip.log) · [Bằng chứng đầy đủ lần chạy ZIP](../dv/evidence/source-zip-evidence.zip) · [Bằng chứng lần chạy tại main2](../dv/evidence/active-main2-evidence.zip) · [Đối chiếu ba lần chạy](../dv/evidence/reproducibility.json)

Đã thử độc lập bốn bản sao bị sửa. Runner trả **2** ở cả bốn ca với chẩn đoán tương ứng cho binary trong cache, log biên dịch trong cache, transcript UVM và nguồn TB khi kiểm bằng chứng. Bộ bàn giao chính có **35 file được niêm SHA-256**. Hai ZIP bằng chứng kèm theo có manifest riêng và đã được giải nén, chạy `verify` lại. [Log các phép thử hỏng có chủ đích](../dv/evidence/usability.log)

## Sổ chạy UVM

| Ca | Seed | ACCESS | Phép so | TX đã decode | RX trên dây | RBR đã so | Kết quả |
|---|---:|---:|---:|---:|---:|---:|---|
| [registers](../dv/evidence/registers-17.log) | 17 | 98 | 193 | 17 | 1 | 1 | PASS |
| [baud](../dv/evidence/baud-17.log) | 17 | 24 | 85 | 3 | 3 | 3 | PASS |
| [modes](../dv/evidence/modes-17.log) | 17 | 128 | 295 | 32 | 32 | 32 | PASS |
| [fifo](../dv/evidence/fifo-17.log) | 17 | 100 | 335 | 22 | 30 | 23 | PASS, đặc tính đầy/clear đã tái hiện |
| [errors](../dv/evidence/errors-17.log) | 17 | 18 | 60 | 0 | 4 | 4 | PASS theo oracle PULP, sai khác hướng dẫn PE/FE |
| [irq](../dv/evidence/irq-17.log) | 17 | 42 | 109 | 0 | 2 | 2 | PASS theo oracle PULP, sai khác IRQ đã tái hiện |
| [thresholds](../dv/evidence/thresholds-17.log) | 17 | 225 | 650 | 24 | 81 | 81 | PASS, so bằng T tại 12 điểm |
| [random](../dv/evidence/random-17.log) | 17 | 228 | 266 | 12 | 20 | 20 | PASS |
| [random](../dv/evidence/random-29.log) | 29 | 222 | 222 | 18 | 14 | 14 | PASS |
| [random](../dv/evidence/random-101.log) | 101 | 230 | 270 | 10 | 22 | 22 | PASS |
| **Tổng chính** | | **1.315** | **2.485** | **138** | **209** | **202** | **10 PASS** |
| [Replay seed 17](../dv/evidence/random-17-replay.log) | 17 | 228 | 266 | 12 | 20 | 20 | PASS, tách khỏi tổng |

Ba seed tạo ba chuỗi stimulus khác nhau. Hash SHA-256 của 80 dòng `STIM` theo thứ tự có prefix `2e3a106ce769`, `f0f9a64d494e` và `82e8201ee66c`. Lặp seed 17 cho cùng hash đủ 64 chữ số, cùng scoreboard, số SETUP/ACCESS và từng bin. Trong 7 khung RX chênh giữa 209 quan sát dây và 202 RBR, 6 byte nằm trong các lần clear chủ đích và 1 khung đến sau khi hết sức chứa của thí nghiệm đầy. [Log FIFO](../dv/evidence/fifo-17.log) · [Hash đầy đủ và số đếm](../dv/evidence/regression.json)

### Negative control

| Lần chạy | Byte thực thấy | Kỳ vọng đã đảo | Chẩn đoán độc lập | Kết quả tiến trình |
|---|---:|---:|---|---|
| [THR → TX](../dv/evidence/baud-17-tx.log) | `55` trên `tx_o` | `54` | `TX_DATA` tại 82.970 ns | 1 UVM_ERROR, 0 UVM_FATAL, simulator exit 1 |
| [RX → RBR](../dv/evidence/baud-17-rbr.log) | `96` ở RBR và trên `rx_i` | `97` | `RBR_DATA` tại 96.050 ns | 1 UVM_ERROR, 0 UVM_FATAL, simulator exit 1 |

Ca `baud` cùng stimulus và seed trả 0 khi không đảo bit. Hai control đều hoàn tất ca và chạy 85 phép so trước khi top trả lỗi. Runner chỉ ghi `DETECTED` khi ID, byte, severity, dấu kết thúc lỗi và exit cùng khớp. Khi gọi riêng `run --inject tx` hoặc `run --inject rbr`, chính runner cũng trả 1. Hồi quy kiểm hai lần từ chối có chủ đích này và trả 0 khi cả bộ đạt tiêu chí. [Control không tiêm](../dv/evidence/baud-17.log) · [Kiểm mã thoát CLI](../dv/evidence/usability.log)

## Coverage thực đo

| Nhóm | Bin trúng / đã khai báo | Số mẫu từ 10 run chính |
|---|---:|---:|
| APB R/W × offset [0:7] × DLAB | 32/32 | 1.315 ACCESS |
| Canonical/alias × R/W | 4/4 | 1.315 ACCESS |
| `LCR[6:4]`, cùng cặp byte parity 0/1 | 8/8 | 8 cặp |
| Hướng TX/RX × 5…8 bit × N/E × 1/2 stop | 32/32 | 337 frame đã so payload và sạch |
| DR 0/1, TEMT/THRE `00/01/11` | 5/5 | 284 mẫu bit/nhóm bit từ 142 lần đọc LSR |
| FIFO/FCR, clear tách/cả hai và giới hạn 17/18 | 8/8 | 8 điểm kết thúc ca con |
| Sai parity × stop thấp của byte RX | 4/4 | 4 khung có đối chiếu đầu FIFO |
| IIR/event cùng nguồn hoặc thao tác acknowledge đã chọn | 12/12 | 18 điểm |
| Ngưỡng FIFO 1/4/8/14 × dưới/bằng/trên | 12/12 | 12 điểm |
| **Tổng bin đã chọn** | **117/117** | Các nhóm có thể lấy mẫu cùng giao dịch |

Trong file coverage gốc, hai cross SystemVerilog đạt **32/32 + 32/32**. Bảy coverpoint thành phần của hai covergroup đạt **22/22**. `verify` so mỗi cross cell ở mỗi run với counter trước khi hợp nhất. 337 frame sạch gồm 138 TX và 199 RBR sạch. Ba RBR còn lại có fault đã xác nhận ở chân RX và được tính ở nhóm lỗi. Mẫu số 117 mô tả đúng các nhóm ở bảng trên. [Coverage native của mode matrix](../dv/evidence/modes-17.coverage.dat.gz) · [Tất cả bin, gồm số lần trúng](../dv/evidence/regression.json)

## Quan sát theo yêu cầu

| ID | Bằng chứng thực thi ở mức IP |
|---|---|
| APB-01, APB-02, APB-03 | 1.317 SETUP, 1.315 ACCESS. Hai SETUP-only ở ca gating có chủ đích. Cặp liên tiếp với PSEL giữ cao, alias LCR, hai DLAB, vùng bỏ trống, upper write bytes, PRDATA ngoài READ ACCESS và ready/error khi ghi đầy đều qua checker. Bài giữ ACCESS sai giao thức qua hai cạnh được đo bằng probe ở phần sau. [Register](../dv/evidence/registers-17.log) · [FIFO](../dv/evidence/fifo-17.log) |
| REG-01, REG-03 | Truy cập cả 8 offset ở hai bank, byte RX `62` còn sau khi đọc DLL, IER còn nguyên sau khi đóng DLAB. Đủ tám mã `LCR[6:4]` cùng cặp `41,01` đều phát even parity như nhau, đọc lại được các bit đã ghi. [Register](../dv/evidence/registers-17.log) |
| REG-02, REG-04, REG-05 | UVM kiểm reset quiescent, DR trước/sau cụm đọc, THRE=1/TEMT=0 khi shift còn phát, acknowledge IIR/LSR/RBR và các lần đọc hai bank giữ mã. RBR rỗng có thể acknowledge C8 thành C0. Dữ liệu ô nhớ khi RBR rỗng chỉ được ghi log. Thời điểm từng cạnh quanh reset động và FIFO được tách ở phần probe. [Register](../dv/evidence/registers-17.log) · [FIFO](../dv/evidence/fifo-17.log) · [IRQ](../dv/evidence/irq-17.log) |
| BAUD-01, BAUD-02, BAUD-03 | D=433, `55`, 50 MHz. Cạnh start ở 510 ns, bit 0 ở 9.210 ns, cạnh stop ở 78.650 ns. Start **435 clock (8.700 ns)**, tám khoảng sau **434 clock (8.680 ns)**. Suy ra 115.207,37 baud, lệch +0,0064% so 115200. D=27 cho start 29 và data 28 clock. Peer độc lập 115200 truyền đúng ở N và E. UVM chưa đo aperture lấy mẫu của RX hay hai biên divisor. [Cạnh thực đo và hai chiều](../dv/evidence/baud-17.log) |
| TX-01, TX-02, TX-03, RX-01 | Mỗi format nhận được đúng cặp TX từ `41,A6` và hai RBR theo byte ở `rx_i`. Có dữ liệu cả hai hướng đồng thời. Đo đủ 16 khoảng start→start trên cặp đã xếp sẵn. Ở D=433, 8N1 là **4.342 clock**, 8N2 là **4.776 clock**. UVM kiểm byte thu bên ngoài. Probe rx-phase bên dưới kiểm thời điểm RBR đã đọc được trước parity. [Mode matrix](../dv/evidence/modes-17.log) |
| RX-02, RX-03 | Decode chân RX xác nhận bốn mẫu PE/stop độc lập. Với cả bốn byte `31,32,33,34`, LSR đầu FIFO đều `61`, IIR `C1`, event=0, dữ liệu RBR đúng. **PE/FE không báo loại lỗi đã chèn.** Khung bị méo vẫn được nhận. Quan sát OE khi tràn nằm ở FIFO-04. Glitch start và break thuộc phạm vi probe. [Lỗi từng byte](../dv/evidence/errors-17.log) |
| FIFO-01, FIFO-02, FIFO-03, FIFO-04 | Burst RX `40…51` chỉ rút được `40…50`, đúng thứ tự, OE=0, cuối cùng DR=0. Đây là 16 vị trí và một byte chờ. Burst TX `80…91` chỉ phát `80…90`. Đã xác minh FCR bit 0 không ngăn lưu hai byte, clear RX/TX độc lập và cùng lúc qua `06/07`. Khi clear TX, chỉ khung đang phát còn lại. Coincident push/pop đúng cạnh và wrap được tính riêng ở probe. [FIFO và LSR](../dv/evidence/fifo-17.log) |
| IRQ-01, IRQ-03, IRQ-04 | **Ngắt RDA giả khi RX rỗng** với `LSR=60, IER=01, IIR=C8, event=1`. THRE riêng trả C4. Khi cả hai bật, C8 thắng. Sau C4, ghi IER=0 rồi đọc IIR hai lần thấy **C4 rồi C0, event vẫn 1**. Reset đưa về C1/0. So parity sai với IER=4 vẫn C1/0. Nhánh CTI buộc 0 và mã lỗi CC còn ở mức phân tích kết nối. [IRQ và acknowledge](../dv/evidence/irq-17.log) · [Kiểm cờ lỗi](../dv/evidence/errors-17.log) |
| IRQ-02 | Với TX FIFO còn dữ liệu và IER chỉ bật sau khi RX ổn định, cả bốn ngưỡng đều cho C8/1 đúng tại T, còn T−1 và T+1 cho C1/0. Mỗi occupancy được dựng sau reset riêng rồi được kiểm bằng cách rút từng byte. [12 điểm threshold](../dv/evidence/thresholds-17.log) |

## Kết quả directed bổ sung

Worker probe chạy **10/10 tình huống** và bắt **2/2 control**. Primitive FIFO được mô phỏng bằng Icarus 14.0. Chín ca top IP dùng Verilator 5.055, một build job và một simulation thread. Đã đối chiếu 12 SHA-256 nguồn của cả hai log chính thức (wrapper và PATH) với cây bàn giao. Lần replay độc lập thiếu `.git` dùng cùng 11 đầu vào RTL/test, với phiên bản runner trước lần cập nhật cách tìm tool. Toàn bộ dòng CHECK, PASS và DETECTED của ba lần đều khớp. Các điểm này có bộ đếm riêng, tách khỏi 117 bin UVM. [Log nguồn và số đo](../dv/probes/main.log) · [Log chạy qua PATH](../dv/probes/path.log) · [Replay độc lập từ cây không có Git](../dv/evidence/supplement-archive-replay.log) · [Runner](../dv/probes/run.py)

| ID | Số đo trong log probe |
|---|---|
| FIFO-01, FIFO-02 | Primitive 8/9 bit đi qua toàn bộ pre-count 0…16. 78 lần offer, 75 nhận và 75 pop được kiểm trong 103 bước. Push/pop đồng thời trúng lần lượt 1/36/2 lần ở count 0/8/16. Control lật bit 8 bị bắt ở bước wrap 71, exit 1. |
| FIFO-02 | RBR ACCESS lệch −1/0/+1 clock so với byte `A6` đến. Ở −1 và 0, lần đọc sau mới lấy `A6`. Ở +1, lần đọc trùng cửa sổ đã lấy `A6`. THR đầy ghi `D7` ngay cạnh dequeue cho 17 khung với ready=1/error=0. Trễ một clock cho 18 khung, `D7` ở cuối. |
| FIFO-03, REG-04 | RX offer ở cạnh ghi FCR k hoặc k+1 để lại FIFO rỗng. Ở k+2, byte mới `A6` còn. Cả ba lần đọc `LSR` ở k+2 vẫn thấy `61`. Với TX, khi cạnh dequeue dự kiến là k/k+1, dây còn `55,39`. Khi là k+2, dây chỉ còn `55`. Byte refill RX/TX lần lượt `71/93`. Bỏ bit clear RX bị bắt với `LSR=61` thay vì `60`, exit 1. |
| REG-02 | Reset sau 687 clock từ start TX khi LSR=01, IRQ đang bật, còn byte TX và RX. Ngay lúc reset, TX=1, IRQ=0. Khi đọc lại LSR/IIR là 60/C1, LCR/IER/DLL/DLM đều 0. Cấu hình lại rồi giải mã đúng TX `A9` và RBR `B6`. |
| BAUD-01 | D=0 cho start/data lần lượt 2/1 clock và start→start 12 clock. D=65535 cho 65.537/65.536 clock và start→start 655.362 clock. Cả hai ca decode đủ `55,A6`. |
| RX-02, RX-03 | Xung thấp 4 clock tạo `FF`. Giữ thấp 10.422 clock tạo `00`. Cả hai lần LSR đầu FIFO bằng `61`, FE/BI đều 0, sau đó nhận lại `69`. Lần lượt có 5.644 và 5.642 lần poll LSR. |
| BAUD-03, RX-01, REG-04 | 48 khung 8E1 độc lập ở D=432/433, đủ 8 bit × 3 độ dịch cạnh. Tính từ cạnh lên đầu tiên thấy start thấp (t=1), ranh giới bit 0 là clock 650/651. Cạnh dữ liệu ở −1/0 được nhận mức mới, ở +1 nhận mức cũ. READ ACCESS ở clock lấy mẫu chân cuối +5/+6 thấy LSR=60/61. Có 16 lần RBR trả đúng payload trước bit parity bên ngoài. |
| APB-01 | Giữ ACCESS qua hai cạnh tạo hai lần pop `6D,B2`, hoặc hai khung TX `A7,A7` từ một lần giữ ghi THR. Đây là kích thích vi phạm giao thức có chủ đích. |

**Còn mở tại IP.** Quét lệch baud cực đại và thay đổi cấu hình giữa khung chưa thực hiện. REG-02 đã quan sát reset và recovery qua cổng IP. Giá trị nội bộ từng tầng synchronizer, default trigger/clear tại chính cạnh reset và các nguồn CTI/mã line-status CC được đối chiếu tĩnh. [Phạm vi ID trong hợp đồng](spec/requirements.json)

## Phạm vi bên ngoài hồi quy UVM

| ID bên ngoài IP | Nguồn kết quả và điều kiện nghiệm thu |
|---|---|
| SYS-01, SYS-02, SYS-03 | Hồ sơ wrapper ghi **9/9 ca mô hình board và 5/5 ca master**, gồm reset/init, polling, KEY/SW/HEX, giữ đọc, echo, wait và lỗi APB. Dùng profile `pulp` trong kết quả GPIO/PTY để đối chiếu dữ liệu từ menu đến chân mô hình và quay về. [Log mô phỏng board và master](../fpga/evidence/board.log) · [Phương pháp tích hợp](../integration/README.md) · [Số liệu tích hợp](../integration/result.json) |
| BOARD-01, BOARD-02 | Đối chiếu pin, jumper, thiết bị, fitter, STA và hash SOF trong hồ sơ FPGA. Kết quả mô phỏng IP không xác nhận điện áp hay timing vật lý. [Kiểm tra tĩnh FPGA](../fpga/evidence/static.log) · [Đánh giá tổng hợp](02_Synthesis_Review.md) · [Hướng dẫn và phiếu nghiệm thu](05_FPGA_Windows.md) |
| BOARD-03 | **Chưa thử trên DE2-115 và CP2102 vật lý của main2.** Peer GPIO mô phỏng và PTY đã có hồ sơ tích hợp riêng. [Hồ sơ tích hợp](../integration/result.json) · [Phiếu nghiệm thu bo thật](05_FPGA_Windows.md) |

Questa chưa chạy vì máy thực thi thiếu `vlib`, `vlog`, `vsim`. Verilator dùng mô phỏng hai trạng thái. Sign-off X/Z bốn trạng thái, metastability, lệch baud tối đa, mọi tổ hợp thay cấu hình giữa khung và coverage cấu trúc RTL nằm ngoài kết quả này. [Driver Questa](../dv/questa.py) · [Điều kiện kiểm chứng và cách chạy](../dv/README.md)
