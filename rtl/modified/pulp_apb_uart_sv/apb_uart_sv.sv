// Copyright 2017 ETH Zurich and University of Bologna.
// Copyright and related rights are licensed under the Solderpad Hardware
// License, Version 0.51 (the “License”); you may not use this file except in
// compliance with the License.  You may obtain a copy of the License at
// http://solderpad.org/licenses/SHL-0.51. Unless required by applicable law
// or agreed to in writing, software, hardware and materials distributed under
// this License is distributed on an “AS IS” BASIS, WITHOUT WARRANTIES OR
// CONDITIONS OF ANY KIND, either express or implied. See the License for the
// specific language governing permissions and limitations under the License.

// Modified from the PULP APB UART architecture (see vendor baseline and LICENSE).
// TARGET-v1.0 replaces byte addressing/direct divider/error/IRQ contracts.
module apb_uart_sv #(parameter int APB_ADDR_WIDTH = 12) (
    input logic CLK, RSTN,
    input logic [APB_ADDR_WIDTH-1:0] PADDR,
    input logic [31:0] PWDATA,
    input logic PWRITE, PSEL, PENABLE,
    output logic [31:0] PRDATA,
    output logic PREADY, PSLVERR,
    input logic rx_i,
    output logic tx_o, event_o
);
    logic [7:0] dll_q, dlm_q, lcr_q, ier_q;
    logic fifo_enable_q;
    logic [1:0] trigger_q;
    logic [4:0] capacity, threshold, tx_count, rx_count, tx_next, rx_next;
    logic transfer, wr, rd, thr_write, fcr_write, lsr_read, rbr_read;
    logic tx_clear, rx_clear, tx_pending_q, oe_q;
    logic tx_ready, tx_busy, tx_pop, tx_push, tx_pop_ok, rx_push_ok, rx_pop_ok;
    logic tx_unused_error, rx_any_error, rx_done;
    logic [7:0] tx_data, iir, lsr;
    logic [10:0] rx_frame, rx_data;
    logic [15:0] divisor;
    assign divisor = {dlm_q,dll_q};
    assign PREADY = 1;
    assign transfer = RSTN && PSEL && PENABLE;
    assign wr = transfer && PWRITE;
    assign rd = transfer && !PWRITE;
    assign fcr_write = wr && PADDR == 'h008;
    assign lsr_read = rd && PADDR == 'h014;
    assign rbr_read = rd && PADDR == 'h000 && !lcr_q[7];
    assign tx_clear = fcr_write && (PWDATA[2] || PWDATA[0] != fifo_enable_q);
    assign rx_clear = fcr_write && (PWDATA[1] || PWDATA[0] != fifo_enable_q);
    assign capacity = fifo_enable_q ? 5'd16 : 5'd1;
    always_comb begin
        case (trigger_q)
            0: threshold = 1;
            1: threshold = 4;
            2: threshold = 8;
            default: threshold = 14;
        endcase
        if (!fifo_enable_q) threshold = 1;
        lsr = 0;
        lsr[0] = rx_count != 0;
        lsr[1] = oe_q;
        lsr[4:2] = rx_data[10:8];
        lsr[5] = tx_count == 0;
        lsr[6] = tx_count == 0 && !tx_busy;
        lsr[7] = rx_any_error;
        iir = fifo_enable_q ? 8'hc1 : 8'h01;
        if (ier_q[2] && (oe_q || |rx_data[10:8])) iir[3:0] = 4'h6;
        else if (ier_q[0] && rx_count >= threshold) iir[3:0] = 4'h4;
        else if (ier_q[1] && tx_pending_q) iir[3:0] = 4'h2;
        PRDATA = 0;
        PSLVERR = 0;
        if (transfer) begin
            case (PADDR)
                'h000: begin
                    if (!PWRITE) PRDATA = {24'b0,lcr_q[7] ? dll_q : rx_data[7:0]};
                    else if (!lcr_q[7] && (divisor == 0 || (tx_count == capacity && !tx_pop))) PSLVERR = 1;
                end
                'h004: if (!PWRITE) PRDATA = {24'b0,lcr_q[7] ? dlm_q : ier_q};
                'h008: if (!PWRITE) PRDATA = {24'b0,iir};
                'h00c: if (!PWRITE) PRDATA = {24'b0,lcr_q};
                'h014: if (!PWRITE) PRDATA = {24'b0,lsr}; else PSLVERR = 1;
                default: PSLVERR = 1;
            endcase
        end
    end
    assign event_o = RSTN && !iir[0];
    assign thr_write = wr && PADDR == 'h000 && !lcr_q[7] && !PSLVERR;
    assign tx_pop = tx_ready && tx_count != 0 && divisor != 0 && !tx_clear;
    uart_fifo #(.WIDTH(8)) tx_fifo (
        .clk(CLK), .rst_n(RSTN), .clear_i(tx_clear), .capacity_i(capacity),
        .push_i(thr_write), .pop_i(tx_pop), .ack_error_i(1'b0), .data_i(PWDATA[7:0]),
        .data_o(tx_data), .push_ok_o(tx_push), .pop_ok_o(tx_pop_ok),
        .any_error_o(tx_unused_error), .count_o(tx_count), .next_count_o(tx_next)
    );
    uart_tx tx (
        .clk(CLK), .rst_n(RSTN), .valid_i(tx_pop), .data_i(tx_data),
        .cfg_i(lcr_q[4:0]), .divisor_i(divisor), .ready_o(tx_ready), .busy_o(tx_busy), .tx_o(tx_o)
    );
    uart_rx rx (
        .clk(CLK), .rst_n(RSTN), .rx_i(rx_i), .cfg_i(lcr_q[4:0]), .divisor_i(divisor),
        .done_o(rx_done), .data_o(rx_frame)
    );
    uart_fifo #(.WIDTH(11)) rx_fifo (
        .clk(CLK), .rst_n(RSTN), .clear_i(rx_clear), .capacity_i(capacity),
        .push_i(rx_done), .pop_i(rbr_read), .ack_error_i(lsr_read), .data_i(rx_frame),
        .data_o(rx_data), .push_ok_o(rx_push_ok), .pop_ok_o(rx_pop_ok),
        .any_error_o(rx_any_error), .count_o(rx_count), .next_count_o(rx_next)
    );
    always_ff @(posedge CLK or negedge RSTN) begin
        if (!RSTN) begin
            dll_q <= 0; dlm_q <= 0; lcr_q <= 0; ier_q <= 0;
            fifo_enable_q <= 0; trigger_q <= 0; oe_q <= 0; tx_pending_q <= 0;
        end else begin
            if (wr && !PSLVERR) case (PADDR)
                'h000: if (lcr_q[7]) dll_q <= PWDATA[7:0];
                'h004: if (lcr_q[7]) dlm_q <= PWDATA[7:0]; else ier_q <= PWDATA[7:0] & 8'h07;
                'h008: begin fifo_enable_q <= PWDATA[0]; trigger_q <= PWDATA[7:6]; end
                'h00c: lcr_q <= PWDATA[7:0] & 8'h9f;
                default: ;
            endcase
            if (lsr_read) oe_q <= 0;
            if (rx_done && !rx_push_ok && !rx_clear) oe_q <= 1;
            if (rx_clear) oe_q <= 0;
            if (thr_write || (rd && PADDR == 'h008 && iir[3:0] == 4'h2)) tx_pending_q <= 0;
            if ((tx_count != 0 && tx_next == 0) ||
                (wr && PADDR == 'h004 && !lcr_q[7] && !ier_q[1] && PWDATA[1] && tx_count == 0))
                tx_pending_q <= 1;
        end
    end
endmodule
