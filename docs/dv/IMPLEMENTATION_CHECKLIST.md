# Checklist yêu cầu 1–2 — audit closure v2

| Task | Kết quả cần đạt | Kiểm chứng | Trạng thái |
|---|---|---|---|
| SPEC / pin / baseline | 80 yêu cầu,65 chân; JP7/JP6 rõ; vendor nguyên vẹn | check_spec, diff RTL/vendor | PASS_DOCUMENT_CHECK |
| RX observer | serial oracle, enqueue đúng cạnh, không dựa BFM completion | TC03/04/05/09/12/13 + early-read boundaries | PASS_SIMULATION |
| Wrapper temporal | debounce release, mode SETUP, reset pending, wake/poll/HEX | system/controller + release mutant | PASS; mutant DETECTED |
| Guard evidence | build→binary→run→coverage, dependency identity và source stability | 24 positive/negative unit tests + actual merge | PASS_EVIDENCE_CHECK |
| Regression | 15 normal UVM,2 negative controls,3 supplemental; extra random seeds | raw logs,source hashes,expected/observed | 15+3 PASS; 2 DETECTED; 2 extra seeds PASS |
| Coverage | 833 mandatory bins; native riêng và review unhit | exporter từ chối bin thiếu hoặc evidence sai | 833/833; native 1097 unhit còn mở |
| Package | source/run/artifact hashes,archived replay | check_published_evidence | PASS_EVIDENCE_CHECK |
| Git | commit nguồn/evidence và remote HEAD khớp | git status + ls-remote | Kết quả transport ghi trong báo cáo bàn giao sau push; không phải simulation gate |
| Windows/Quartus/board | QPF/QSF/SDC,compile/fitter/STA,CP2102/bo thật | thực thi trên Windows/FPGA | NOT_RUN / yêu cầu3 |

Evidence v1 và review cũ được giữ nguyên làm lịch sử. Verdict source mới chỉ nằm trong target_v2; không dùng PASS cũ để đóng bản sửa.
