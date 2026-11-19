// Pass through the stock APB/serial pins. These two read-only timing witnesses
// locate stimulus edges; neither exposes a byte, queue count or clear result.
module probe_uart (
    input logic CLK, RSTN,
    input logic [11:0] PADDR,
    input logic [31:0] PWDATA,
    input logic PWRITE, PSEL, PENABLE, rx_i,
    output logic [31:0] PRDATA,
    output logic PREADY, PSLVERR, tx_o, event_o,
    output logic align_rx_offer, align_tx_load
);
    apb_uart_sv uart (.CLK, .RSTN, .PADDR, .PWDATA, .PWRITE, .PSEL, .PENABLE,
                      .PRDATA, .PREADY, .PSLVERR, .rx_i, .tx_o, .event_o);
    assign align_rx_offer = uart.rx_valid;
    assign align_tx_load = uart.tx_valid && uart.tx_ready;
endmodule
