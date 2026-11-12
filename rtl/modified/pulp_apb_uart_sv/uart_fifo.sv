// Copyright 2017 ETH Zurich and University of Bologna.
// Copyright and related rights are licensed under the Solderpad Hardware
// License, Version 0.51 (the “License”); you may not use this file except in
// compliance with the License.  You may obtain a copy of the License at
// http://solderpad.org/licenses/SHL-0.51. Unless required by applicable law
// or agreed to in writing, software, hardware and materials distributed under
// this License is distributed on an “AS IS” BASIS, WITHOUT WARRANTIES OR
// CONDITIONS OF ANY KIND, either express or implied. See the License for the
// specific language governing permissions and limitations under the License.

// TARGET-v1.0 derivative; see LICENSE and vendor baseline provenance.
module uart_fifo #(
    parameter int WIDTH = 8
) (
    input logic clk, rst_n, clear_i,
    input logic [4:0] capacity_i,
    input logic push_i, pop_i, ack_error_i,
    input logic [WIDTH-1:0] data_i,
    output logic [WIDTH-1:0] data_o,
    output logic push_ok_o, pop_ok_o, any_error_o,
    output logic [4:0] count_o, next_count_o
);
    logic [WIDTH-1:0] mem [0:15];
    logic [3:0] rd_q, wr_q;
    assign data_o = count_o != 0 ? mem[rd_q] : '0;
    assign pop_ok_o = pop_i && count_o != 0 && !clear_i;
    assign push_ok_o = push_i && (count_o < capacity_i || pop_ok_o) && !clear_i;
    always_comb begin
        next_count_o = count_o;
        if (clear_i) next_count_o = 0;
        else case ({push_ok_o,pop_ok_o})
            2'b10: next_count_o = count_o + 1'b1;
            2'b01: next_count_o = count_o - 1'b1;
            default: ;
        endcase
        any_error_o = 0;
        if (WIDTH > 8)
            for (int k=0; k<16; k++)
                if (k < count_o) any_error_o |= |(mem[4'(rd_q+k)] >> 8);
    end
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            count_o <= 0; rd_q <= 0; wr_q <= 0;
        end else if (clear_i) begin
            count_o <= 0; rd_q <= 0; wr_q <= 0;
        end else begin
            count_o <= next_count_o;
            // Acknowledge only the old head; simultaneous replacement wins.
            if (ack_error_i && count_o != 0) mem[rd_q] <= mem[rd_q] & WIDTH'(8'hff);
            if (pop_ok_o) rd_q <= rd_q + 1'b1;
            if (push_ok_o) begin
                mem[wr_q] <= data_i;
                wr_q <= wr_q + 1'b1;
            end
        end
    end
endmodule
