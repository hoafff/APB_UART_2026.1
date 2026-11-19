# SPEC TARGET-v1.0: one 50 MHz clock; no PLL or fabric/gated clocks.
create_clock -name CLOCK_50 -period 20.000 [get_ports {CLOCK_50}]
derive_clock_uncertainty

# Fail if synthesis renamed/pruned a required synchronizer endpoint. Never let
# an empty collection silently turn a CDC exception into a no-op.
proc fpga_require_count {label collection expected} {
    set actual [get_collection_size $collection]
    if {$actual != $expected} { error "$label: expected $expected nodes, got $actual" }
    return $collection
}
set fpga_rx_first [fpga_require_count RX_FIRST [get_registers {rx_sync[0]}] 1]
set fpga_key_first [fpga_require_count KEY_FIRST [get_registers {key_sync[0]}] 1]
set fpga_sw_first [fpga_require_count SW_FIRST [get_registers {sw_meta[*]}] 12]
set fpga_reset_chain [fpga_require_count RESET_CHAIN [get_registers {reset_sync[*]}] 2]

# These external sources have no phase relationship to CLOCK_50. Only their
# first sampling stage is exempt; all later stage-to-stage paths remain timed.
# SW[13:8] have no functional loads; the 12 used bits are 0..7 and 14..17.
set_false_path -from [get_ports {GPIO_UART_RX}] -to $fpga_rx_first
set_false_path -from [get_ports {KEY[1]}] -to $fpga_key_first
set_false_path -from [get_ports {SW[*]}] -to $fpga_sw_first

# KEY0 directly asserts the asynchronous reset of both reset-sync flops.
# Crucially, there is NO cut from reset_sync[1] / rst_n to functional logic:
# recovery/removal of synchronized internal reset release must pass STA.
set_false_path -from [get_ports {KEY[0]}] -to $fpga_reset_chain

set fpga_outputs [fpga_require_count OUTPUTS [get_ports {
    GPIO_UART_TX LEDR[*] LEDG[*] HEX0[*] HEX1[*] HEX4[*] HEX5[*]
}] 43]
# UART is asynchronous and the indicators have no external capture clock.
# Bound implementation delay to 0..20 ns including launch clock-network
# latency. These are engineering budgets, not CP2102 setup/hold specifications.
# Quartus 25.1 Standard/Lite does not support Vivado's -datapath_only option.
set_max_delay 20.000 -to $fpga_outputs
set_min_delay 0.000 -to $fpga_outputs
