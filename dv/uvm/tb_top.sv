`timescale 1ns/1ps
module tb_top;
    import uvm_pkg::*;
    import apb_uart_uvm_pkg::*;

    logic clk = 1'b0;
    always #10 clk = ~clk; // 50 MHz, 20 ns period

    uart_apb_if bus(clk);

    apb_uart_sv dut (
        .CLK      (clk),
        .RSTN     (bus.RSTN),
        .PADDR    (bus.PADDR),
        .PWDATA   (bus.PWDATA),
        .PWRITE   (bus.PWRITE),
        .PSEL     (bus.PSEL),
        .PENABLE  (bus.PENABLE),
        .PRDATA   (bus.PRDATA),
        .PREADY   (bus.PREADY),
        .PSLVERR  (bus.PSLVERR),
        .rx_i     (bus.rx_i),
        .tx_o     (bus.tx_o),
        .event_o  (bus.event_o)
    );

    initial begin
        bus.RSTN = 0;
        bus.PADDR = '0;
        bus.PWDATA = '0;
        bus.PWRITE = 0;
        bus.PSEL = 0;
        bus.PENABLE = 0;
        bus.rx_i = 1; // UART idle
        repeat (8) @(negedge clk);
        bus.RSTN = 1;
    end

    initial begin
        uvm_config_db#(virtual uart_apb_if)::set(null, "uvm_test_top*", "vif", bus);
        run_test("apb_reg_smoke_test");
    end

    // Emergency hang guard; real regression timing/latency handled by each test.
    initial begin
        #5_000_000;
        `fatal(1, "TB watchdog timeout (5 ms)");
    end
endmodule
