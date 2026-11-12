// Copyright 2017 ETH Zurich and University of Bologna.
// Copyright and related rights are licensed under the Solderpad Hardware
// License, Version 0.51 (the “License”); you may not use this file except in
// compliance with the License.  You may obtain a copy of the License at
// http://solderpad.org/licenses/SHL-0.51. Unless required by applicable law
// or agreed to in writing, software, hardware and materials distributed under
// this License is distributed on an “AS IS” BASIS, WITHOUT WARRANTIES OR
// CONDITIONS OF ANY KIND, either express or implied. See the License for the
// specific language governing permissions and limitations under the License.

// TARGET-v1.0: three-stage CDC, majority 7/8/9, atomic data/error completion.
module uart_rx (
    input logic clk, rst_n, rx_i,
    input logic [4:0] cfg_i,
    input logic [15:0] divisor_i,
    output logic done_o,
    output logic [10:0] data_o
);
    (* async_reg = "true" *) logic [2:0] sync_q;
    logic prev_q, armed_q, active_q, all_low_q;
    logic [19:0] high_q;
    logic [15:0] divisor_q, timer_q;
    logic [4:0] cfg_q;
    logic [7:0] tick_q, byte_q;
    logic [1:0] ones_q;
    logic pe_q, fe_q;
    integer tick_now, bit_index, n, parity_bits, total_ticks;
    logic majority;
    always_comb begin
        tick_now = int'(tick_q)+1;
        bit_index = tick_now/16;
        n = 5+int'(cfg_q[1:0]);
        parity_bits = int'(cfg_q[3]);
        total_ticks = 16*(1+n+parity_bits+1+int'(cfg_q[2]));
        majority = (int'(ones_q)+int'(sync_q[2])) >= 2;
    end
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            sync_q <= '1; prev_q <= 1;
            armed_q <= 0; active_q <= 0; all_low_q <= 0;
            high_q <= 0; divisor_q <= 0; timer_q <= 0;
            cfg_q <= 0; tick_q <= 0; byte_q <= 0; ones_q <= 0;
            pe_q <= 0; fe_q <= 0; done_o <= 0; data_o <= 0;
        end else begin
            sync_q <= {sync_q[1:0],rx_i};
            prev_q <= sync_q[2];
            done_o <= 0;
            if (!active_q) begin
                if (divisor_i == 0) begin armed_q <= 0; high_q <= 0; end
                else if (armed_q && prev_q && !sync_q[2]) begin
                    active_q <= 1; armed_q <= 0;
                    divisor_q <= divisor_i; cfg_q <= cfg_i;
                    timer_q <= divisor_i-1'b1; tick_q <= 0;
                    byte_q <= 0; ones_q <= 0; pe_q <= 0; fe_q <= 0;
                    all_low_q <= 1; high_q <= 0;
                end else if (sync_q[2]) begin
                    if (high_q < {divisor_i,4'b0}) high_q <= high_q+1'b1;
                    if (high_q >= {divisor_i,4'b0}-1'b1) armed_q <= 1;
                end else high_q <= 0;
            end else begin
                if (sync_q[2]) all_low_q <= 0;
                if (timer_q != 0) timer_q <= timer_q-1'b1;
                else begin
                    timer_q <= divisor_q-1'b1;
                    tick_q <= 8'(tick_now);
                    case (tick_now % 16)
                        7: ones_q <= {1'b0,sync_q[2]};
                        8: ones_q <= ones_q+{1'b0,sync_q[2]};
                        9: begin
                            if (bit_index == 0) begin
                                if (majority) begin active_q <= 0; high_q <= 0; armed_q <= 0; end
                            end else if (bit_index <= n) byte_q[bit_index-1] <= majority;
                            else if (cfg_q[3] && bit_index == n+1)
                                pe_q <= majority != (cfg_q[4] ? ^byte_q : ~(^byte_q));
                            else begin
                                fe_q <= fe_q || !majority;
                                if (bit_index == total_ticks/16-1 && !fe_q && majority) begin
                                    data_o <= {1'b0,1'b0,pe_q,byte_q};
                                    done_o <= 1; active_q <= 0; armed_q <= 1; high_q <= 0;
                                end
                            end
                        end
                        default: ;
                    endcase
                    if (tick_now == total_ticks) begin
                        data_o <= {all_low_q && !sync_q[2],fe_q,pe_q,byte_q};
                        done_o <= 1; active_q <= 0; armed_q <= 0; high_q <= 0;
                    end
                end
            end
        end
    end
endmodule
