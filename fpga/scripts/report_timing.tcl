# Run quartus_sta -t ../scripts/report_timing.tcl from the compiled project directory.
package require ::quartus::project
package require ::quartus::sta
package require ::quartus::report
source [file join [file dirname [info script]] timing_checks.tcl]

set revision de2_115_pulp_uart
set reports [file normalize [file join .. build timing]]
file mkdir $reports
project_open $revision -revision $revision
load_report
create_timing_netlist
read_sdc
update_timing_netlist
set issues {}
proc one_reg {name} {
    set nodes [get_registers $name]
    if {[get_collection_size $nodes] != 1} { error "Expected one fitted register for $name" }
    return $nodes
}
proc metric {corner kind result} {
    global issues
    lassign $result count slack
    puts "METRIC $corner $kind paths=$count slack_ns=$slack"
    if {![pulp_valid_metric $count $slack]} {
        lappend issues "$corner $kind $result"
    }
}
set clk [get_clocks CLOCK_50]
if {[get_collection_size [get_clocks *]] != 1 || [get_collection_size $clk] != 1 ||
    abs([get_clock_info -period $clk] - 20.0) > 0.0001} { error "Expected one 20 ns CLOCK_50" }
set chains [list {{reset_sync[0]} {reset_sync[1]}} {{key_sync[0]} {key_sync[1]}} \
    {{rx_sync[0]} {rx_sync[1]} {apb_uart_sv:uart|uart_rx:uart_rx_i|reg_rx_sync[0]}
     {apb_uart_sv:uart|uart_rx:uart_rx_i|reg_rx_sync[1]} {apb_uart_sv:uart|uart_rx:uart_rx_i|reg_rx_sync[2]}}]
foreach bit {0 1 2 3 4 5 6 7 14 16 17} {
    lappend chains [list [format {sw_meta[%d]} $bit] [format {sw_sync[%d]} $bit]]
}
set corners [get_available_operating_conditions]
set names {}
foreach_in_collection op $corners { lappend names [get_operating_conditions_info -name $op] }
pulp_require_corners $names
puts "OPERATING_CONDITIONS $names"
foreach_in_collection op $corners {
    set_operating_conditions $op
    update_timing_netlist
    set tag [get_operating_conditions_info -name $op]
    foreach kind {setup hold recovery removal} {
        metric $tag $kind [report_timing -$kind -npaths 20 -detail full_path -file [file join $reports ${tag}_${kind}.rpt]]
    }
    foreach kind {recovery removal} {
        metric $tag reset_$kind [report_timing -$kind -from [one_reg {reset_sync[1]}] -npaths 10 \
            -detail full_path -file [file join $reports ${tag}_reset_${kind}.rpt]]
    }
    metric $tag pulse_width [report_min_pulse_width -nworst 20 -file [file join $reports ${tag}_pulse.rpt]]
    foreach chain $chains {
        foreach src [lrange $chain 0 end-1] dst [lrange $chain 1 end] {
            foreach kind {setup hold} {
                set paths [get_timing_paths -$kind -from [one_reg $src] -to [one_reg $dst] -npaths 1]
                if {[get_collection_size $paths] != 1} { error "Missing $kind path $src -> $dst" }
                foreach_in_collection path $paths {
                    metric $tag "$kind $src -> $dst" [list 1 [get_path_info -slack $path]]
                }
            }
        }
    }
    report_metastability -nchains 100 -file [file join $reports ${tag}_metastability.rpt]
}
report_clocks -file [file join $reports clocks.rpt]
report_exceptions -file [file join $reports exceptions.rpt]
report_sdc -ignored -file [file join $reports ignored_sdc.rpt]
report_ucp -file [file join $reports unconstrained.rpt] -panel_name {PULP UCP}
check_timing -include {no_clock multiple_clock generated_clock loops latches no_input_delay no_output_delay
    partial_input_delay partial_output_delay io_min_max_delay_consistency} -file [file join $reports check_timing.rpt]

set panel {}
foreach name [get_report_panel_names] {
    if {[string match {*||PULP UCP||Unconstrained Paths Summary} $name]} { lappend panel $name }
}
if {[llength $panel] != 1} { error "Missing unconstrained-path summary, inspect $reports" }
set name [lindex $panel 0]
set rows [get_number_of_rows -name $name]
if {$rows < 2} { error "Empty unconstrained-path summary" }
for {set i 1} {$i < $rows} {incr i} {
    lassign [get_report_panel_row -name $name -row $i] category setup hold
    if {$setup ne "0" || $hold ne "0"} { lappend issues "Unconstrained $category $setup $hold" }
}
set f [open [file join $reports ignored_sdc.rpt] r]
set ignored [read $f]
close $f
if {[string first {No constraints were ignored.} $ignored] < 0} { lappend issues "Review ignored_sdc.rpt" }
project_close
if {[llength $issues]} { error [join $issues "\n"] }
puts "PULP_POSTFIT_CHECKS_COMPLETE - review check_timing, latch/loop and fitter messages"
