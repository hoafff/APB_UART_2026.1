# Post-fit release audit. No -post_map: fitted netlist and assembled SOF required.
package require ::quartus::project
package require ::quartus::sta
package require ::quartus::report

set root [file normalize [file join [file dirname [info script]] ../..]]
set project_dir [file join $root fpga de2_115]
set reports [file join $root build fpga reports]
file mkdir $reports
set table_path [file join $reports timing.tsv]
if {[file exists $table_path]} { file delete $table_path }
foreach ext {sof fit.rpt} {
    if {![file exists [file join $root build fpga output_files de2_115_apb_uart.$ext]]} {
        error "Missing fitted artifact .$ext; perform a full compile first"
    }
}
set table [open $table_path w]
proc emit {args} { global table; puts $table [join $args "\t"]; flush $table }
proc eq {actual expected label} {
    if {$actual ne $expected} { error "$label: expected '$expected', got '$actual'" }
}
proc one_reg {name} {
    set regs [get_registers $name]
    eq [get_collection_size $regs] 1 "Register $name"
    return $regs
}
proc fanout_names {nodes} {
    set names {}
    foreach_in_collection node [get_fanouts -no_logic $nodes] {
        lappend names [get_node_info -name $node]
    }
    return [lsort -unique $names]
}
proc panel {suffix} {
    set matches {}
    foreach name [get_report_panel_names] {
        if {[string match "*||$suffix" $name]} { lappend matches $name }
    }
    eq [llength $matches] 1 "Report panel $suffix"
    return [lindex $matches 0]
}
proc table_rows {suffix} {
    set name [panel $suffix]
    set rows {}
    for {set i 1} {$i < [get_number_of_rows -name $name]} {incr i} {
        lappend rows [get_report_panel_row -name $name -row $i]
    }
    return $rows
}
proc pass_metric {corner kind result} {
    lassign $result count slack
    emit METRIC $corner $kind $count $slack
    if {$count < 1 || ![string is double -strict $slack] || $slack < 0} {
        error "Timing failure or missing data: $corner $kind = $result"
    }
}

cd $project_dir
project_open de2_115_apb_uart
load_report
create_timing_netlist
read_sdc
update_timing_netlist
eq [get_collection_size [get_clocks *]] 1 CLOCK_COUNT
set clk [get_clocks CLOCK_50]
eq [get_collection_size $clk] 1 CLOCK_NAME
set period [get_clock_info -period $clk]
if {abs($period-20.0) > 0.0001} { error "Wrong clock period $period" }
emit CLOCK CLOCK_50 $period

set used_sw {0 1 2 3 4 5 6 7 14 15 16 17}
set edges [list [list {reset_sync[0]} {reset_sync[1]}] [list {key_sync[0]} {key_sync[1]}] \
    [list {rx_sync[0]} {rx_sync[1]}] \
    [list {rx_sync[1]} {apb_uart_sv:uart|uart_rx:rx|sync_q[0]}] \
    [list {apb_uart_sv:uart|uart_rx:rx|sync_q[0]} {apb_uart_sv:uart|uart_rx:rx|sync_q[1]}] \
    [list {apb_uart_sv:uart|uart_rx:rx|sync_q[1]} {apb_uart_sv:uart|uart_rx:rx|sync_q[2]}]]
foreach bit $used_sw { lappend edges [list [format {sw_meta[%d]} $bit] [format {sw_sync[%d]} $bit]] }
eq [llength $edges] 18 CHAIN_EDGE_COUNT
set chain_regs {}
foreach edge $edges {
    lassign $edge src dst
    one_reg $src
    one_reg $dst
    eq [fanout_names [one_reg $src]] [list $dst] "Chain fanout $src"
    lappend chain_regs $src $dst
    emit CHAIN_EDGE $src $dst
}
eq [llength [lsort -unique $chain_regs]] 33 CHAIN_REGISTER_COUNT
emit COUNT chain_registers 33
emit COUNT chain_edges 18
eq [fanout_names [get_ports GPIO_UART_RX]] [list {rx_sync[0]}] RX_FIRST_HOP
eq [fanout_names [get_ports {KEY[1]}]] [list {key_sync[0]}] KEY_FIRST_HOP
eq [fanout_names [get_ports {KEY[0]}]] [lsort [list {reset_sync[0]} {reset_sync[1]}]] EXTERNAL_RESET_FANOUT
foreach bit $used_sw {
    eq [fanout_names [get_ports [format {SW[%d]} $bit]]] [list [format {sw_meta[%d]} $bit]] "SW_FIRST_HOP $bit"
}

set corners [get_available_operating_conditions]
eq [get_collection_size $corners] 3 CORNER_COUNT
emit COUNT corners 3
foreach_in_collection op $corners {
    set_operating_conditions $op
    update_timing_netlist
    set tag [get_operating_conditions_info -name $op]
    foreach typ {setup hold recovery removal} {
        pass_metric $tag $typ [report_timing -$typ -npaths 20 -detail full_path -file [file join $reports ${tag}_${typ}.rpt]]
    }
    pass_metric $tag min_pulse_width [report_min_pulse_width -nworst 20 -file [file join $reports ${tag}_min_pulse_width.rpt]]
    foreach typ {recovery removal} {
        pass_metric $tag reset_$typ [report_timing -$typ -from [one_reg {reset_sync[1]}] -npaths 20 -detail full_path -file [file join $reports ${tag}_reset_${typ}.rpt]]
    }
    foreach edge $edges {
        lassign $edge src dst
        foreach typ {setup hold} {
            set paths [get_timing_paths -$typ -from [one_reg $src] -to [one_reg $dst] -npaths 1]
            eq [get_collection_size $paths] 1 "Timed chain $tag $typ $src -> $dst"
            foreach_in_collection path $paths {
                set slack [get_path_info -slack $path]
                if {![string is double -strict $slack] || $slack < 0} { error "Chain timing $tag $src -> $dst: $slack" }
                emit CHAIN_TIMING $tag $typ $src $dst $slack
            }
        }
    }
    report_clock_fmax_summary -file [file join $reports ${tag}_fmax.rpt]
    report_metastability -nchains 100 -file [file join $reports ${tag}_metastability.rpt]
}

# Missing I/O clock delays are expected only on these asynchronous ports.
# Explicit first-stage cuts and implementation output budgets must still make UCP zero.
check_timing -include {no_clock multiple_clock generated_clock loops latches no_input_delay no_output_delay partial_input_delay partial_output_delay io_min_max_delay_consistency} -file [file join $reports check_timing.rpt] -panel_name {FPGA Check}
report_ucp -file [file join $reports unconstrained.rpt] -panel_name {FPGA UCP}
report_sdc -ignored -file [file join $reports ignored_sdc.rpt]
report_exceptions -file [file join $reports exceptions.rpt] -panel_name {FPGA Exceptions}
report_clocks -file [file join $reports clocks.rpt]
foreach row [table_rows {FPGA Check||Summary}] {
    lassign $row check count
    emit CHECK $check $count
    if {$check eq "no_input_delay"} { eq $count 15 INPUT_DELAY_COUNT } elseif {$check eq "no_output_delay"} {
        eq $count 43 OUTPUT_DELAY_COUNT
    } else { eq $count 0 "check_timing $check" }
}
set expected_inputs [list GPIO_UART_RX {KEY[0]} {KEY[1]}]
foreach bit $used_sw { lappend expected_inputs [format {SW[%d]} $bit] }
set expected_outputs {GPIO_UART_TX}
foreach {bus width} {LEDR 5 LEDG 9 HEX0 7 HEX1 7 HEX4 7 HEX5 7} {
    for {set i 0} {$i < $width} {incr i} { lappend expected_outputs [format {%s[%d]} $bus $i] }
}
foreach {suffix expected kind} [list {No Input Delay} $expected_inputs INPUT_WAIVER {No Output Delay} $expected_outputs OUTPUT_WAIVER] {
    set actual {}
    foreach row [table_rows "FPGA Check||$suffix"] { lappend actual [lindex $row 0]; emit $kind [lindex $row 0] }
    eq [lsort $actual] [lsort $expected] "Exact port waiver $suffix"
}
foreach row [table_rows {FPGA UCP||Unconstrained Paths Summary}] {
    lassign $row property setup hold
    eq $setup 0 "Unconstrained setup $property"
    eq $hold 0 "Unconstrained hold $property"
    emit UCP $property $setup $hold
}
set f [open [file join $reports ignored_sdc.rpt] r]
set ignored [read $f]
close $f
if {[string first {No constraints were ignored.} $ignored] < 0} { error "Ignored SDC constraints; inspect report" }
emit COUNT ignored_sdc 0
emit STATUS POST_FIT_AUDIT_PASS
close $table
project_close
puts "POST_FIT_AUDIT_PASS: all corners, reset release, exact chains/waivers, no ignored SDC or unconstrained paths; BOARD_NOT_TESTED"
