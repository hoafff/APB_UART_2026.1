# Run by tools/build_fpga.py from build/fpga/questa (existing non-UVM benches).
onerror {quit -code 1 -force}
if {![file isdirectory work]} {vlib work}
vmap work work
vlog -sv -work work ../../../rtl/modified/pulp_apb_uart_sv/uart_fifo.sv ../../../rtl/modified/pulp_apb_uart_sv/uart_tx.sv ../../../rtl/modified/pulp_apb_uart_sv/uart_rx.sv ../../../rtl/modified/pulp_apb_uart_sv/apb_uart_sv.sv ../../../rtl/fpga/de2_uart_controller.sv ../../../rtl/fpga/de2_115_apb_uart_bringup.sv ../../../dv/system/tb_system.sv ../../../dv/system/tb_controller.sv ../../../dv/system/tb_tx_onehot.sv
vsim -onfinish stop work.tb_system
run -all
quit -sim
vsim -onfinish stop work.tb_controller
run -all
quit -sim
vsim -onfinish stop work.tb_tx_onehot
run -all
quit -code 0 -force
