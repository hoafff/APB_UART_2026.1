`timescale 1ns/1ps
interface uart_if(input logic clk);
    logic rst_n = 0;
    logic [11:0] addr = 0;
    logic [31:0] wdata = 0, rdata;
    logic wr = 0, sel = 0, enable = 0, ready, slverr;
    logic rx = 1, tx, irq;
endinterface
