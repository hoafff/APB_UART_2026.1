#!/usr/bin/env bash
# Usage: export UVM_HOME=/path/to/uvm-1.2
#        bash dv/sim/run_questa.sh apb_reg_smoke_test 1
set -euo pipefail

TEST_NAME="${1:-apb_reg_smoke_test}"
SEED="${2:-1}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BUILD="${ROOT}/dv/sim/build"
RTL="${ROOT}/rtl/vendor/pulp_apb_uart_sv"

if ! command -v vlog >/dev/null || ! command -v vsim >/dev/null || ! command -v vlib >/dev/null; then
  echo "ERROR: Questa/ModelSim simulator commands vlog, vsim, vlib not found." >&2
  exit 2
fi
if [[ -z "${UVM_HOME:-}" || ! -f "${UVM_HOME}/src/uvm_pkg.sv" ]]; then
  echo "ERROR: set UVM_HOME to an installed UVM library with src/uvm_pkg.sv." >&2
  exit 2
fi

mkdir -p "${BUILD}"
cd "${BUILD}"
if [[ ! -d work ]]; then vlib work; fi

vlog -sv -mfcu -work work \
    "+incdir+${UVM_HOME}/src" \
    "${UVM_HOME}/src/uvm_pkg.sv" \
    "${RTL}/io_generic_fifo.sv" \
    "${RTL}/uart_tx.sv" \
    "${RTL}/uart_rx.sv" \
    "${RTL}/uart_interrupt.sv" \
    "${RTL}/apb_uart_sv.sv" \
    "${ROOT}/dv/uvm/uart_apb_if.sv" \
    "${ROOT}/dv/uvm/apb_uart_uvm_pkg.sv" \
    "${ROOT}/dv/uvm/tb_top.sv"

echo "Running ${TEST_NAME} seed=${SEED}"
vsim -c -L work work.tb_top \
    "+UVM_TESTNAME=${TEST_NAME}" \
    "-sv_seed" "${SEED}" \
    -do "run -all; quit -f"

# NOTE: A zero simulator process exit code does not guarantee zero UVM_ERRORs.
# Review the UVM Report Summary, and parse it in a future regression runner.
