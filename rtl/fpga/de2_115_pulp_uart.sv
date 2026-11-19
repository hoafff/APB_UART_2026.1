module de2_115_pulp_uart (
    input  logic        CLOCK_50,
    input  logic [1:0]  KEY,
    input  logic [17:0] SW,
    input  logic        GPIO_UART_RX,
    output logic        GPIO_UART_TX,
    output logic [4:0]  LEDR,
    output logic [8:0]  LEDG,
    output logic [6:0]  HEX0,
    output logic [6:0]  HEX1,
    output logic [6:0]  HEX4,
    output logic [6:0]  HEX5
);
    localparam int unsigned DEBOUNCE_CYCLES = 500000;  // 10 ms @ 50 MHz
    localparam int unsigned COUNT_BITS = $clog2(DEBOUNCE_CYCLES);
    // Quartus preservation/CDC assignments name these registers in synchronizers.qsf.
    logic [1:0] reset_sync, rx_sync, key_sync;
    logic [17:0] sw_meta, sw_sync;
    wire rst_n = reset_sync[1];

    always_ff @(posedge CLOCK_50 or negedge KEY[0]) begin
        if (!KEY[0])
            reset_sync <= 2'b00;
        else
            reset_sync <= {reset_sync[0], 1'b1};
    end
    always_ff @(posedge CLOCK_50 or negedge rst_n) begin
        if (!rst_n) begin
            rx_sync <= 2'b11;
            key_sync <= 2'b00;
            sw_meta <= '0;
            sw_sync <= '0;
        end else begin
            rx_sync <= {rx_sync[0], GPIO_UART_RX};
            key_sync <= {key_sync[0], !KEY[1]};
            sw_meta <= SW;
            sw_sync <= sw_meta;
        end
    end

    logic [COUNT_BITS-1:0] debounce_count;
    logic key_down, key_press;
    always_ff @(posedge CLOCK_50 or negedge rst_n) begin
        if (!rst_n) begin
            debounce_count <= '0;
            key_down <= 1'b0;
            key_press <= 1'b0;
        end else begin
            key_press <= 1'b0;
            if (key_sync[1] == key_down) begin
                debounce_count <= '0;
            end else if (debounce_count == COUNT_BITS'(DEBOUNCE_CYCLES - 1)) begin
                debounce_count <= '0;
                key_down <= key_sync[1];
                key_press <= key_sync[1];
            end else begin
                debounce_count <= debounce_count + 1'b1;
            end
        end
    end

    logic [11:0] paddr;
    logic [31:0] pwdata, prdata;
    logic pwrite, psel, penable, pready, pslverr;
    logic init_done, fault, even_mode, irq;
    logic [7:0] last_rx, last_lsr;

    de2_pulp_uart_master master (
        .clk(CLOCK_50), .rst_n(rst_n), .key_press(key_press), .key_byte(sw_sync[7:0]),
        .even_select(sw_sync[14]), .hold_rx(sw_sync[16]), .echo_enable(sw_sync[17]),
        .paddr(paddr), .pwdata(pwdata), .pwrite(pwrite), .psel(psel), .penable(penable),
        .prdata(prdata), .pready(pready), .pslverr(pslverr),
        .init_done(init_done), .fault(fault), .even_mode(even_mode),
        .last_rx(last_rx), .last_lsr(last_lsr)
    );
    apb_uart_sv uart (
        .CLK(CLOCK_50), .RSTN(rst_n), .PADDR(paddr), .PWDATA(pwdata), .PWRITE(pwrite),
        .PSEL(psel), .PENABLE(penable), .PRDATA(prdata), .PREADY(pready), .PSLVERR(pslverr),
        .rx_i(rx_sync[1]), .tx_o(GPIO_UART_TX), .event_o(irq)
    );

    function automatic logic [6:0] segments(input logic [3:0] nibble);
        case (nibble)  // g..a, active low
            4'h0: segments = 7'h40; 4'h1: segments = 7'h79;
            4'h2: segments = 7'h24; 4'h3: segments = 7'h30;
            4'h4: segments = 7'h19; 4'h5: segments = 7'h12;
            4'h6: segments = 7'h02; 4'h7: segments = 7'h78;
            4'h8: segments = 7'h00; 4'h9: segments = 7'h10;
            4'ha: segments = 7'h08; 4'hb: segments = 7'h03;
            4'hc: segments = 7'h46; 4'hd: segments = 7'h21;
            4'he: segments = 7'h06; default: segments = 7'h0e;
        endcase
    endfunction

    assign HEX0 = segments(sw_sync[3:0]);
    assign HEX1 = segments(sw_sync[7:4]);
    assign HEX4 = segments(last_rx[3:0]);
    assign HEX5 = segments(last_rx[7:4]);
    assign LEDR = last_lsr[4:0];
    assign LEDG = {irq, 1'b0, last_lsr[6:5], sw_sync[17], sw_sync[16],
                   even_mode, fault, init_done};
endmodule
