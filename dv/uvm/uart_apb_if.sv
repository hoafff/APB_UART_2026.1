`timescale 1ns/1ps
interface uart_apb_if(input logic CLK);
    logic RSTN;
    logic [11:0] PADDR;
    logic [31:0] PWDATA;
    logic        PWRITE;
    logic        PSEL;
    logic        PENABLE;
    logic [31:0] PRDATA;
    logic        PREADY;
    logic        PSLVERR;
    logic        rx_i;
    logic        tx_o;
    logic        event_o;
endinterface
