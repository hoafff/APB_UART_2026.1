`timescale 1ns/1ps
module apb_uart_assertions (
    input logic clk,rst_n,psel,penable,pwrite,pready,pslverr,tx,irq,
    input logic [11:0] paddr,
    input logic [31:0] pwdata,prdata,
    input logic [4:0] tx_count,rx_count,capacity
);
    int access_count,reset_count;
    apb_ready: assert property (@(posedge clk) pready) else $fatal(1,"ASSERT_APB_READY");
    apb_setup: assert property (@(posedge clk) disable iff(!rst_n)
        (psel && penable) |-> ($past(psel && !penable) && $stable(paddr) && $stable(pwrite) && (!pwrite || $stable(pwdata))))
        else $fatal(1,"ASSERT_APB_SETUP_STABILITY");
    apb_idle: assert property (@(posedge clk) (!rst_n || !psel || !penable) |-> (prdata==0 && !pslverr))
        else $fatal(1,"ASSERT_APB_IDLE_OUTPUTS");
    apb_byte: assert property (@(posedge clk) prdata[31:8]==0) else $fatal(1,"ASSERT_APB_ZERO_EXTEND");
    fifo_bounds: assert property (@(posedge clk) disable iff(!rst_n) (tx_count<=capacity && rx_count<=capacity))
        else $fatal(1,"ASSERT_FIFO_BOUNDS");
    reset_outputs: assert property (@(posedge clk) !rst_n |-> (tx && !irq)) else $fatal(1,"ASSERT_RESET_OUTPUTS");
    irq_encoding: assert property (@(posedge clk) disable iff(!rst_n)
        (psel && penable && !pwrite && paddr==12'h008) |-> (irq==!prdata[0] && prdata[3:0]!=0))
        else $fatal(1,"ASSERT_IIR_IRQ");
    cover property (@(posedge clk) rst_n && psel && penable && pslverr);
    cover property (@(posedge clk) rst_n && rx_count==capacity);
    cover property (@(posedge clk) rst_n && irq);
    always @(posedge clk) begin
        if(!rst_n) reset_count++;
        else if(psel && penable && pready) access_count++;
    end
    final $display("ASSERTIONS_ACTIVE|apb=%0d|reset=%0d",access_count,reset_count);
endmodule
