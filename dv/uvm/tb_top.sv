`timescale 1ns/1ps
module tb_top;
    import uvm_pkg::*;
    import apb_uart_uvm_pkg::*;
    logic clk=0;
    always #10 clk=~clk;
    uart_apb_if bus(clk);
    apb_uart_sv dut(
        .CLK(clk),.RSTN(bus.RSTN),.PADDR(bus.PADDR),.PWDATA(bus.PWDATA),
        .PWRITE(bus.PWRITE),.PSEL(bus.PSEL),.PENABLE(bus.PENABLE),
        .PRDATA(bus.PRDATA),.PREADY(bus.PREADY),.PSLVERR(bus.PSLVERR),
        .rx_i(bus.rx_i),.tx_o(bus.tx_o),.event_o(bus.event_o)
    );
    assign bus.rx_done_probe=dut.rx_done;
    assign bus.rx_start_probe=dut.rx.armed_q && dut.rx.prev_q && !dut.rx.sync_q[2];
    assign bus.tx_ready_probe=dut.tx_ready;
    apb_uart_assertions checks(
        .clk(clk),.rst_n(bus.RSTN),.psel(bus.PSEL),.penable(bus.PENABLE),.pwrite(bus.PWRITE),
        .pready(bus.PREADY),.pslverr(bus.PSLVERR),.paddr(bus.PADDR),.pwdata(bus.PWDATA),.prdata(bus.PRDATA),
        .tx(bus.tx_o),.irq(bus.event_o),.tx_count(dut.tx_count),.rx_count(dut.rx_count),.capacity(dut.capacity)
    );
    initial begin
        bus.RSTN=0; bus.PADDR=0; bus.PWDATA=0; bus.PWRITE=0; bus.PSEL=0; bus.PENABLE=0; bus.rx_i=1;
        repeat(8) @(negedge clk); bus.RSTN=1;
    end
    initial begin
        uvm_config_db#(virtual uart_apb_if)::set(null,"uvm_test_top*","vif",bus);
        run_test();
    end
    initial begin
        longint unsigned watchdog_ns;
        watchdog_ns=2_000_000_000;
        if($value$plusargs("WATCHDOG_NS=%d",watchdog_ns)) begin end
        #(watchdog_ns); $fatal(1,"TB_WATCHDOG");
    end
    initial if($test$plusargs("TRACE")) begin $dumpfile("wave.fst"); $dumpvars(0,tb_top); end
endmodule
