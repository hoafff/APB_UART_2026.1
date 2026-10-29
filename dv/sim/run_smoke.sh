#!/usr/bin/env bash
# Normal suite only; known-gap XFAIL tests are deliberately excluded.
# Usage: bash dv/sim/run_smoke.sh [seed]
set -euo pipefail
SEED="${1:-1}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
for TEST in \
  apb_reg_smoke_test \
  apb_reg_alias_test \
  uart_tx_8n1_test \
  uart_rx_8n1_test \
  uart_rx_fifo_order_test \
  uart_rx_fifo_clear_test \
  uart_tx_mode_matrix_test \
  apb_random_regs_test
do
  echo "=== RUN ${TEST} seed=${SEED} ==="
  bash "${ROOT}/dv/sim/run_questa.sh" "${TEST}" "${SEED}"
done
echo "Normal smoke/regression complete (known-gap XFAILs excluded)"
