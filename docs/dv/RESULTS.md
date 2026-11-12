# Kết quả kiểm chứng TARGET-v1.0 / audit closure v2

**15/15 run UVM chức năng PASS; 3/3 simulation bổ sung PASS; 2/2 negative controls DETECTED.**
Functional coverage: **833/833 bin đã công khai** trong coverage_model.json. Đây là coverage của tập nghĩa vụ mô phỏng đã định nghĩa, không phải mọi chuỗi đầu vào hoặc bằng chứng formal/hardware.

Git HEAD tại lúc chạy UVM: `9edea82b6a969a0c9b63a03ecbf8ff6c30bade2e`; working_tree_dirty=`True`. Các sửa đổi nguồn chưa commit khi chạy, nên SHA HEAD này không đại diện riêng cho bản đã kiểm. Danh tính bản đã chạy là toàn bộ SHA-256 đầu vào và build ID trong [source_manifest](../../dv/results/target_v2/source_manifest.json) và từng run manifest. Runner xác minh source/UVM/binary trước và sau execution; metadata gốc được giữ nguyên sau commit.

## UVM runs

| Test | Seed | Kết quả | SB checks | TX / RX | Thời gian wall-clock |
|---|---:|---|---:|---|---:|
| `target_apb_test` | 17 | PASS | 8219 | 0 / 0 | 3.48 s |
| `target_tx_modes_test` | 17 | PASS | 432 | 96 / 0 | 4.63 s |
| `target_rx_modes_test` | 17 | PASS | 432 | 0 / 96 | 3.83 s |
| `target_tolerance_test` | 17 | PASS | 3870 | 0 / 780 | 29.95 s |
| `target_errors_test` | 17 | PASS | 105 | 0 / 20 | 2.28 s |
| `target_fifo_test` | 17 | PASS | 109 | 1 / 50 | 3.13 s |
| `target_irq_test` | 17 | PASS | 818 | 1 / 25 | 3.55 s |
| `target_reset_test` | 17 | PASS | 93 | 0 / 1 | 1.87 s |
| `target_snapshot_test` | 17 | PASS | 110 | 7 / 6 | 2.12 s |
| `target_baud_test` | 17 | PASS | 38 | 4 / 0 | 610.67 s |
| `target_false_start_test` | 17 | PASS | 38 | 0 / 7 | 1.63 s |
| `target_concurrency_test` | 17 | PASS | 234 | 20 / 47 | 11.48 s |
| `target_random_test` | 17 | PASS | 1187 | 64 / 64 | 27.81 s |
| `target_random_test` | 29 | PASS | 1193 | 64 / 64 | 21.95 s |
| `target_random_test` | 101 | PASS | 1191 | 64 / 64 | 15.64 s |

## Bổ sung và negative controls

- `tb_system`: profile 50 MHz/D27, default debounce 500000 cycles, reset sync, N/O/E, send/RX/echo/hold/errors, finite burst 32; chỉ simulation.
- `tb_controller`: injected slave faults (init/runtime), manual overflow, same-edge consume/new, echo reservation/fairness và poll interval khi hold IRQ.
- `tb_tx_onehot`: 192 N/parity/stop/one-hot cases; kiểm cả bit dữ liệu nằm ngoài WLS.
- Negative TX-data và ACCESS thiếu SETUP đều bị checker đúng phát hiện. Các run này không được cộng vào PASS/coverage target.

## Functional coverage theo nhóm

| Nhóm | Hit / bắt buộc |
|---|---|
| uart_modes | 48 / 48 |
| tx_onehot | 192 / 192 |
| apb_valid | 18 / 18 |
| apb_sequences | 3 / 3 |
| rx_occupancy | 17 / 17 |
| fifo | 8 / 8 |
| errors | 10 / 10 |
| irq_sources_masks | 64 / 64 |
| irq_thresholds | 4 / 4 |
| irq_misc | 11 / 11 |
| reset | 9 / 9 |
| config | 8 / 8 |
| baud | 5 / 5 |
| tolerance | 390 / 390 |
| rx_start_noise | 3 / 3 |
| concurrency | 7 / 7 |
| random | 2 / 2 |
| system | 11 / 11 |
| controller | 9 / 9 |
| rx_visibility | 12 / 12 |
| rx_rearm | 2 / 2 |

## Native RTL coverage

| Loại điểm instrument | Hit / tổng |
|---|---|
| branch | 149 / 156 |
| expr | 279 / 309 |
| line | 130 / 135 |
| toggle | 1975 / 3030 |

Còn **1097 điểm instrument chưa hit**; danh sách lưu trong native_unhit_points.json để review. Chưa tuyên bố code/toggle coverage closure. Không tự loại unreachable bins để nâng tỷ lệ.

## Bằng chứng và giới hạn

- [Evidence index](../../dv/results/target_v2/summary.json), [logs](../../dv/results/target_v2/logs), [functional ledger](../../dv/results/target_v2/functional_coverage.json), [native merge](../../dv/results/target_v2/coverage_merged.dat.gz), [waveforms](../../dv/results/target_v2/waveforms.zip).
- 80 requirement có testcase/observer mapping; các row MAPPED_SIM_TESTS_PASS xác nhận ca liên kết đã chạy đạt, không thay một review sign-off toàn bộ không gian trạng thái. 5 requirement FPGA vẫn HW_PENDING.
- Chưa chạy Quartus/fitter/STA, chưa có bitstream hay thử DE2-115 + CP2102 thật. Chưa chạy Questa, formal hoặc X-propagation/analog metastability.
- Thư viện/công cụ có sẵn được tái sử dụng; đã tải UVM pin vào .tools/uvm. Các failure ban đầu (syntax/task direction, hết disk, runtime thiếu PATH Z3) được giữ trong build history và issue ledger.
- Exporter đối chiếu trực tiếp 20 raw logs với JSON: đủ đúng test/seed, completion, scoreboard, assertion activity, diagnostic của negative controls và functional counts. Xem [evidence validation](../../dv/results/target_v2/evidence_validation.json).

## Chạy lại

```bash
bash dv/sim/run_smoke.sh
```

Hoặc chạy từng lệnh trong dv/README.md. Exporter từ chối log/JSON không khớp, thiếu/trùng test, source mismatch, run FAIL/timeout, thiếu assertion activity, negative control sai diagnostic hoặc thiếu mandatory functional bin.
