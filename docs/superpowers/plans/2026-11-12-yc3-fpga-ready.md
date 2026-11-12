# Yêu cầu 3 FPGA Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement task-by-task, with an independent whole-branch review.

**Goal:** Build a verified, reproducible DE2-115 SRAM programming package; keep hardware acceptance pending.

**Architecture:** Preserve validated RTL, add a standalone Quartus project with explicit pin/timing/reset contracts. Use real Quartus project and post-fit reports to gate release, then bind the `.sof` to source/config hashes.

**Tech Stack:** Quartus Prime Lite 25.1, Tcl/SDC, Python 3.11, existing SystemVerilog benches/Questa where available.

**Spec:** `docs/superpowers/specs/2026-11-12-yc3-fpga-design.md`; `docs/01_System_Specification.md` §11–14.

## Global Constraints

- `Cyclone IV E / EP4CE115F29C7`; 50 MHz / 20 ns; top `de2_115_apb_uart_bringup`.
- Six TARGET/wrapper files only; no baseline vendor or DV source in synthesis.
- Exactly 65 bit ports; pin/I/O profile from JSON, independently checked against CSV/RTL.
- JP7 5–6 = 2.5 V; JP6 7–8 = 3.3 V. Physical verification remains pending.
- No push/deploy; no fabricated board results; keep existing RTL/evidence unchanged unless a measured defect requires correction.

## Review Focus

- Swapped TX/RX or wrong bus index: compare resolved and fitted assignments, including AB22 TX / AB21 RX and KEY0.
- False-path accidentally masking chain or reset release: inspect actual post-fit paths and ensure synchronous/recovery/removal path sets exist.
- A corner or timing category with missing data: fail closed rather than treating an empty/NA result as zero slack.
- Stale `.sof` or changed source after build: verify every sealed hash and test tampering rejection.
- Borrowed board with wrong jumper/logic level or unexpected JTAG chain: explicit physical preflight and device match before programming.

## Tasks

### 1. Project and pin contract

- [x] Write a real Quartus Tcl preflight test that fails while the project is missing and checks device/top/source list/pin assignments from independently derived expected data.
- [x] Run the test and capture the expected missing-project failure.
- [x] Add `.qpf/.qsf`, per-bit pins, synchronizer preservation and portable paths.
- [x] Re-run preflight; require exact assignments and no duplicate or missing pins.

### 2. Timing constraints and full compile

- [x] Add explicit async-input/reset exceptions and output budgets; guard empty/incorrect collection matches.
- [x] Execute full Quartus compile through fitter, assembler and STA.
- [x] Export all available operating corners; check setup/hold/recovery/removal/minimum pulse width, clocks, synchronizers and exceptions/unconstrained paths.
- [x] Correct measured issues and repeat affected checks; record any ruling and its reason.

### 3. Reproducible build and sealed release

- [x] Write negative tests for absent timing, negative slack, missing categories/corners, and tampered source/bitstream.
- [x] Implement the build/report/manifest helper and make the tests green.
- [x] Run applicable existing checks plus project/STA checks and existing wrapper simulation if the installed simulator can execute it.
- [x] Seal actual source/config/bitstream hashes and tool version; export software readiness with hardware fields still `NOT_RUN`.

### 4. Documentation, review and handoff

- [x] Update README/handoff status and provide exact build, GUI/programmer, CP2102 and physical-preflight instructions.
- [x] Have independent reviewer examine final diff and actual reports; fix substantive findings with verification.
- [ ] Reconcile checklist, commit locally, bind final artifacts to commit and unchanged inputs.
- [ ] Deliver source/reports/bitstream package under chat `outputs/`, plus final status and limitations.

## Baseline and rulings

- Starting commit: `7173ec73cf7a0ecb90808515168ca69780a4e318`; isolated checkout `D:\uart\APB_UART_2026.1`, branch `codex/yc3-fpga-ready`.
- Baseline `tools/check_spec.py` and `tools/check_dv.py`: PASS on Windows.
- Baseline existing `unittest discover -s tools/tests`: blocked during import because Linux-only `run_dv.py` imports `resource`. Record separately; do not claim it passed or alter unrelated Linux runners solely to hide the platform limitation.
- Ruling: use a separate checkout/branch on D because C has less than 1 GiB free and Quartus creates databases. This is covered by the user's request and standing instruction to continue without per-step confirmation.

## Execution evidence

- Task 1 complete: missing-project RED captured in `build/fpga/work/preflight-red.log`; resolved-project GREEN in `preflight-green.log` (0 errors, 0 warnings).
- Native Questa 10.7c ran existing system/controller/onehot benches: completion counts 4,027,274 / 46 / 2,361 (192 onehot frames), each simulator run 0 errors, 0 warnings; log `build/fpga/questa/questa-system.log`.
- Independent pin audit matched all 65 pins against current Terasic manual; no profile conflict. Timing audit experimentally validated first-stage exceptions and output budgets on post-map scratch. Full post-fit closure remains in Task 2.

## Resume evidence (12/11/2026)

- Task 2 complete: fresh `quartus_sh -t fpga/scripts/check_project.tcl` and
  `quartus_sta -t fpga/scripts/audit_timing.tcl` both exit 0, zero errors/warnings.
  All three fitted corners have positive setup/hold/recovery/removal/min-pulse
  slack; 33 chain registers, 18 timed edges, exact I/O waivers, UCP=0, ignored SDC=0.
- Task 3 complete: 13 release tests first failed (validator missing), then all
  passed. Full `tools/build_fpga.py build --questa-bin E:\Apps\QuestaSim-10.7c\win64`
  exited 0, with compile 0 errors/20 reviewed warnings and 72 sealed file hashes.
  Questa reran the existing three benches with completion counts
  4,027,274 / 46 / 2,361 (192 frames), zero errors.
- Existing `check_spec.py` and `check_dv.py` passed again. Full Python unittest
  discovery still cannot import `test_report_dv` because Windows lacks `resource`;
  this is reported in the handoff and is not counted as a pass.
- Read-only hardware observation: `jtagconfig` exit 4, `No JTAG hardware available`;
  no COM ports listed. Programming/electrical/board tests remain NOT_RUN.
- Ruling: continue the established D-drive checkout on its existing feature
  branch; creating another checkout would discard the interrupted work context.
- Ruling: keep the documented 20 warning profile, including default output drive
  settings and AN447 requirements, instead of changing validated RTL or asserting
  unmeasured board properties. Cost: electrical acceptance still needs the board.
- Ruling: actual unused-pin fit is tri-state with weak pull-up; document that
  measured result. The setting does not drive unused peripherals to ground.
- Ruling: tool identity is the recorded Quartus edition/build/version; source,
  configuration, reports and bitstream use SHA-256. This is an integrity seal,
  not cryptographic attestation of the installed vendor toolchain.
- Final review: independent reviewer confirmed actual 65-pin mapping, all three
  timing corners, reset release paths and 20-warning inventory. One Important
  finding concerned simulation provenance; no Critical findings.
- Final fix: bind all three simulation benches and the fixture in INPUTS;
  require a sealed log for PASS and compare every completion count to that log.
  Two new unit tests failed before the fix; the release suite now passes 15/15.
  Five real extracted-package cases pass: changed bench rejected, missing sealed
  simulation log rejected, altered count rejected, explicit NOT_RUN accepted,
  stale PASS counts in NOT_RUN rejected. Probe logs live under `D:/uart/work/`.
- Ruling: include the one-line Git-checkout clarification in the already-scoped
  handoff documentation; no additional package-from-ZIP functionality is added.
- Reviewer-declined physical voltage, overshoot, oscillator, jumper orientation,
  JTAG/UART and empirical MTBF judgments remain explicitly NOT_RUN. Windows UVM
  runner stays unsupported as already recorded; no hardware acceptance inferred.
