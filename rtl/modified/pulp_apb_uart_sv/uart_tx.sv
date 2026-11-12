// Copyright 2017 ETH Zurich and University of Bologna.
// Copyright and related rights are licensed under the Solderpad Hardware
// License, Version 0.51 (the “License”); you may not use this file except in
// compliance with the License.  You may obtain a copy of the License at
// http://solderpad.org/licenses/SHL-0.51. Unless required by applicable law
// or agreed to in writing, software, hardware and materials distributed under
// this License is distributed on an “AS IS” BASIS, WITHOUT WARRANTIES OR
// CONDITIONS OF ANY KIND, either express or implied. See the License for the
// specific language governing permissions and limitations under the License.

// TARGET-v1.0: 16x divisor, configuration captured per frame.
module uart_tx (
    input logic clk, rst_n,
    input logic valid_i,
    input logic [7:0] data_i,
    input logic [4:0] cfg_i,
    input logic [15:0] divisor_i,
    output logic ready_o, busy_o, tx_o
);
    logic [11:0] frame_q, frame_d;
    logic [3:0] bits_q, length_d;
    logic [19:0] period_q, timer_q;
    logic parity_d;
    integer n;
    always_comb begin
        n = 5 + int'(cfg_i[1:0]);
        frame_d = '1;
        frame_d[0] = 0;
        parity_d = 0;
        for (int k=0; k<8; k++)
            if (k<n) begin
                frame_d[k+1] = data_i[k];
                parity_d ^= data_i[k];
            end
        if (cfg_i[3]) frame_d[1+n] = cfg_i[4] ? parity_d : ~parity_d;
        length_d = 4'(1+n+int'(cfg_i[3])+1+int'(cfg_i[2]));
    end
    assign busy_o = bits_q != 0;
    assign ready_o = bits_q == 0 || (bits_q == 1 && timer_q == 0);
    assign tx_o = bits_q == 0 ? 1'b1 : frame_q[0];
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            frame_q <= '1; bits_q <= 0; period_q <= 0; timer_q <= 0;
        end else if (ready_o && valid_i && divisor_i != 0) begin
            frame_q <= frame_d;
            bits_q <= length_d;
            period_q <= {divisor_i,4'b0};
            timer_q <= {divisor_i,4'b0}-1'b1;
        end else if (bits_q != 0) begin
            if (timer_q == 0) begin
                frame_q <= {1'b1,frame_q[11:1]};
                bits_q <= bits_q-1'b1;
                timer_q <= period_q-1'b1;
            end else timer_q <= timer_q-1'b1;
        end
    end
endmodule
