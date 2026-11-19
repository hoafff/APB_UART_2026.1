# Run with quartus_sh -t fpga/scripts/check_project.tcl.
# Test resolved Quartus assignments against the independent Terasic CSV contract.
package require ::quartus::project

proc require_equal {actual expected label} {
    if {$actual ne $expected} { error "$label: expected '$expected', got '$actual'" }
}

set root [file normalize [file join [file dirname [info script]] ../..]]
set project_dir [file join $root fpga de2_115]
set revision de2_115_apb_uart
set project_path [file join $project_dir $revision]
if {![file exists "$project_path.qpf"]} {
    error "FPGA_PROJECT_MISSING: $project_path.qpf"
}
cd $project_dir
project_open $project_path -revision $revision
require_equal [get_global_assignment -name FAMILY] "Cyclone IV E" FAMILY
require_equal [get_global_assignment -name DEVICE] EP4CE115F29C7 DEVICE
require_equal [get_global_assignment -name TOP_LEVEL_ENTITY] de2_115_apb_uart_bringup TOP
require_equal [get_global_assignment -name RESERVE_ALL_UNUSED_PINS] "AS INPUT TRI-STATED" UNUSED_PINS
set unused_alias [get_global_assignment -name RESERVE_ALL_UNUSED_PINS_NO_OUTPUT_GND]
if {$unused_alias ne ""} { require_equal $unused_alias "AS INPUT TRI-STATED" UNUSED_PINS_ALIAS }

set expected_sources {}
foreach path {
    rtl/modified/pulp_apb_uart_sv/uart_fifo.sv
    rtl/modified/pulp_apb_uart_sv/uart_tx.sv
    rtl/modified/pulp_apb_uart_sv/uart_rx.sv
    rtl/modified/pulp_apb_uart_sv/apb_uart_sv.sv
    rtl/fpga/de2_uart_controller.sv
    rtl/fpga/de2_115_apb_uart_bringup.sv
} { lappend expected_sources [file normalize [file join $root $path]] }
set actual_sources {}
foreach_in_collection assignment [get_all_global_assignments -name SYSTEMVERILOG_FILE] {
    lappend actual_sources [file normalize [lindex $assignment 2]]
}
require_equal [lsort $actual_sources] [lsort $expected_sources] SOURCE_LIST

set csv [open [file join $root reference DE2_115_pin_assignments.csv] r]
array set board {}
while {[gets $csv line] >= 0} {
    set row [split $line ,]
    if {[llength $row] >= 6 && [string match PIN_* [lindex $row 2]]} {
        set board([lindex $row 0]) [list [lindex $row 2] [lindex $row 5]]
    }
}
close $csv
set ports {CLOCK_50 GPIO_UART_RX GPIO_UART_TX}
foreach {bus width} {KEY 2 SW 18 LEDR 5 LEDG 9 HEX0 7 HEX1 7 HEX4 7 HEX5 7} {
    for {set i 0} {$i < $width} {incr i} { lappend ports [format {%s[%d]} $bus $i] }
}
require_equal [llength $ports] 65 PORT_COUNT
require_equal [get_collection_size [get_all_assignments -type instance -name LOCATION]] 65 LOCATION_COUNT
require_equal [get_collection_size [get_all_assignments -type instance -name IO_STANDARD]] 65 IO_STANDARD_COUNT
array set used_locations {}
foreach port $ports {
    set board_name $port
    if {$port eq "GPIO_UART_TX"} { set board_name {GPIO[0]} }
    if {$port eq "GPIO_UART_RX"} { set board_name {GPIO[2]} }
    if {![info exists board($board_name)]} { error "Missing Terasic reference: $board_name" }
    lassign $board($board_name) pin io_standard
    require_equal [get_location_assignment -to $port] $pin "PIN $port"
    require_equal [get_instance_assignment -name IO_STANDARD -to $port] $io_standard "IO $port"
    if {[info exists used_locations($pin)]} { error "Duplicate pin $pin" }
    set used_locations($pin) $port
}
project_close
puts "FPGA_PROJECT_CONTRACT_PASS: exact device, top, six TARGET sources, 65 unique Terasic pin/I/O assignments, unused pins tri-stated"
