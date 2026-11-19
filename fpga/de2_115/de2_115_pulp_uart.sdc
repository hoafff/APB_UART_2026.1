create_clock -name CLOCK_50 -period 20.000 [get_ports {CLOCK_50}]
derive_clock_uncertainty

proc pulp_require_nodes {label nodes expected} {
    set count [get_collection_size $nodes]
    if {$count != $expected} { error "$label expected $expected nodes, found $count" }
    return $nodes
}

# Only the pad-to-first-stage paths lack a synchronous launch clock.
foreach {pad stage} {
    GPIO_UART_RX {rx_sync[0]}
    {KEY[1]}     {key_sync[0]}
} {
    set_false_path -from [pulp_require_nodes $pad [get_ports $pad] 1] \
                   -to [pulp_require_nodes $stage [get_registers $stage] 1]
}
foreach bit {0 1 2 3 4 5 6 7 14 16 17} {
    set pad [format {SW[%d]} $bit]
    set stage [format {sw_meta[%d]} $bit]
    set_false_path -from [pulp_require_nodes $pad [get_ports $pad] 1] \
                   -to [pulp_require_nodes $stage [get_registers $stage] 1]
}
# KEY0 asynchronously asserts both reset synchronizer flops. Release from
# reset_sync[1] to functional flops remains timed for recovery and removal.
set_false_path -from [pulp_require_nodes KEY0 [get_ports {KEY[0]}] 1] \
               -to [pulp_require_nodes RESET_STAGES [get_registers {reset_sync[*]}] 2]

# Asynchronous UART and human-readable indicators have no external capture
# clock. Budget the delay to every output pad against one board-clock period.
set pads [pulp_require_nodes OUTPUTS [get_ports {
    GPIO_UART_TX LEDR[*] LEDG[*] HEX0[*] HEX1[*] HEX4[*] HEX5[*]
}] 43]
set_max_delay 20.000 -to $pads
set_min_delay 0.000 -to $pads
