module de2_115_apb_uart_bringup #(
    parameter int DEBOUNCE_CYCLES=500000,
    parameter int POLL_CYCLES=5000
) (
    input logic CLOCK_50,
    input logic [1:0] KEY,
    input logic [17:0] SW,
    input logic GPIO_UART_RX,
    output logic GPIO_UART_TX,
    output logic [4:0] LEDR,
    output logic [8:0] LEDG,
    output logic [6:0] HEX0,HEX1,HEX4,HEX5
);
    (* async_reg="true" *) logic [1:0] reset_sync,rx_sync,key_sync;
    (* async_reg="true" *) logic [17:0] sw_meta,sw_sync;
    logic rst_n,stable_q,send_pulse;
    logic [31:0] debounce_q;
    logic [11:0] paddr;
    logic [31:0] pwdata,prdata;
    logic pwrite,psel,penable,pready,pslverr,irq,init_done,fault;
    logic [7:0] rx_byte;
    assign rst_n=reset_sync[1];
    always_ff @(posedge CLOCK_50 or negedge KEY[0])
        if(!KEY[0]) reset_sync<=0;
        else reset_sync<={reset_sync[0],1'b1};
    always_ff @(posedge CLOCK_50 or negedge rst_n) begin
        if(!rst_n) begin
            rx_sync<='1; key_sync<=0; sw_meta<=0; sw_sync<=0;
            debounce_q<=0; stable_q<=0; send_pulse<=0;
        end else begin
            rx_sync<={rx_sync[0],GPIO_UART_RX};
            key_sync<={key_sync[0],~KEY[1]};
            sw_meta<=SW; sw_sync<=sw_meta;
            send_pulse<=0;
            if(key_sync[1]==stable_q) debounce_q<=0;
            else if(debounce_q==DEBOUNCE_CYCLES-1) begin
                debounce_q<=0; stable_q<=key_sync[1]; send_pulse<=key_sync[1];
            end else debounce_q<=debounce_q+1'b1;
        end
    end
    de2_uart_controller #(.POLL_CYCLES(POLL_CYCLES)) master (
        .clk(CLOCK_50),.rst_n(rst_n),.send_i(send_pulse),.sw_i(sw_sync),
        .paddr(paddr),.pwdata(pwdata),.pwrite(pwrite),.psel(psel),.penable(penable),
        .prdata(prdata),.pready(pready),.pslverr(pslverr),.irq_i(irq),
        .init_done_o(init_done),.fault_o(fault),.rx_byte_o(rx_byte),.status_o(LEDR)
    );
    apb_uart_sv uart (
        .CLK(CLOCK_50),.RSTN(rst_n),.PADDR(paddr),.PWDATA(pwdata),.PWRITE(pwrite),
        .PSEL(psel),.PENABLE(penable),.PRDATA(prdata),.PREADY(pready),.PSLVERR(pslverr),
        .rx_i(rx_sync[1]),.tx_o(GPIO_UART_TX),.event_o(irq)
    );
    function automatic logic [6:0] hex(input logic [3:0] nibble);
        case(nibble)
            0:hex=7'b1000000; 1:hex=7'b1111001; 2:hex=7'b0100100; 3:hex=7'b0110000;
            4:hex=7'b0011001; 5:hex=7'b0010010; 6:hex=7'b0000010; 7:hex=7'b1111000;
            8:hex=7'b0000000; 9:hex=7'b0010000; 10:hex=7'b0001000; 11:hex=7'b0000011;
            12:hex=7'b1000110; 13:hex=7'b0100001; 14:hex=7'b0000110; default:hex=7'b0001110;
        endcase
    endfunction
    assign HEX0=hex(sw_sync[3:0]); assign HEX1=hex(sw_sync[7:4]);
    assign HEX4=hex(rx_byte[3:0]); assign HEX5=hex(rx_byte[7:4]);
    assign LEDG={irq,6'b0,fault,init_done};
endmodule
