`timescale 1ns/1ps
module tb_top;
    import uvm_pkg::*;
    import pulp_uart_pkg::*;
    bit clk;
    always #10ns clk = !clk;
    uart_if bus(clk);
    int bench_exit=2; // Read by the batch Questa driver after "run -all".
    apb_uart_sv dut (
        .CLK(clk), .RSTN(bus.rst_n), .PADDR(bus.addr), .PWDATA(bus.wdata),
        .PWRITE(bus.wr), .PSEL(bus.sel), .PENABLE(bus.enable), .PRDATA(bus.rdata),
        .PREADY(bus.ready), .PSLVERR(bus.slverr), .rx_i(bus.rx), .tx_o(bus.tx),
        .event_o(bus.irq)
    );

    initial begin
        uvm_root root;
        uvm_report_server reports;
        root=uvm_root::get();
        $timeformat(-9,0,"",0);
        root.set_finish_on_completion(0);
        uvm_config_db#(virtual uart_if)::set(null, "*", "vif", bus);
        run_test("pulp_uart_test");
        reports = uvm_report_server::get_server();
        if (reports.get_severity_count(UVM_ERROR)!=0 || reports.get_severity_count(UVM_FATAL)!=0) begin
            bench_exit=1;
            $fatal(1, "DV_CHECKS_FAILED");
        end
        bench_exit=0;
        $display("DV_EXIT|PASS");
        $finish;
    end
    initial #25ms $fatal(1, "DV_SIM_WATCHDOG");
endmodule
