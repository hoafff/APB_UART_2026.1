`timescale 1ns/1ps

module tb_fifo;
    localparam int Depth = 16;
    logic clk = 0, rst_n = 0, offer = 0, take = 0;
    logic [8:0] incoming = 0;
    bit control, flip_ninth_bit = 0;
    wire [7:0] head8;
    wire [8:0] head9;
    wire [4:0] count8, count9;
    wire valid8, valid9, ready8, ready9;

    always #5 clk = ~clk;
    io_generic_fifo #(.DATA_WIDTH(8), .BUFFER_DEPTH(Depth)) tx_width (
        .clk_i(clk), .rstn_i(rst_n), .clr_i(1'b0), .elements_o(count8),
        .data_o(head8), .valid_o(valid8), .ready_i(take),
        .valid_i(offer), .data_i(incoming[7:0]), .ready_o(ready8)
    );
    io_generic_fifo #(.DATA_WIDTH(9), .BUFFER_DEPTH(Depth)) rx_width (
        .clk_i(clk), .rstn_i(rst_n), .clr_i(1'b0), .elements_o(count9),
        .data_o(head9), .valid_o(valid9), .ready_i(take),
        .valid_i(offer), .data_i({incoming[8] ^ flip_ninth_bit, incoming[7:0]}), .ready_o(ready9)
    );

    logic [8:0] expected[$];
    int attempts = 0, accepted = 0, removed = 0, steps = 0;
    int simultaneous[0:Depth];

    task automatic check_ports(input string phase_name);
        int n;
        logic [8:0] head;
        logic valid, ready;
        n = expected.size();
        valid = n > 0;
        ready = n < Depth;
        if (count8 !== 5'(n) || count9 !== 5'(n) ||
            {valid8, ready8} !== {valid, ready} || {valid9, ready9} !== {valid, ready})
            $fatal(1, "FIFO flags step=%0d %s expected_count=%0d counts=%0d/%0d valid:ready=%b/%b",
                   steps, phase_name, n, count8, count9, {valid8, ready8}, {valid9, ready9});
        if (valid) begin
            head = expected[0];
            if (head8 !== head[7:0] || head9 !== head)
                $fatal(1, "FIFO order step=%0d %s n=%0d expected=%03h got8=%02h got9=%03h",
                       steps, phase_name, n, head, head8, head9);
        end
    endtask

    task automatic step(input bit push_req, input bit pop_req);
        int before_count;
        logic [8:0] popped;
        @(negedge clk);
        steps++;
        offer = push_req;
        take = pop_req;
        flip_ninth_bit = control && steps == 64;
        if (offer) begin
            // All attempts, including rejected offers, have distinct low bytes in this run.
            incoming = {attempts[0], 8'(73 * attempts + 25)};
            attempts++;
        end
        #1;
        check_ports("before");
        before_count = expected.size();
        @(posedge clk);
        // Advance only from the requests and old software queue, never from DUT flags.
        if (pop_req && before_count > 0) begin
            popped = expected.pop_front();
            removed++;
        end
        if (push_req && before_count < Depth) begin
            expected.push_back(incoming);
            accepted++;
        end
        #1;
        check_ports("after");
        if (push_req && pop_req)
            simultaneous[before_count]++;
    endtask

    initial begin
        control = $test$plusargs("corrupt_wrap_word");
        for (int i = 0; i <= Depth; i++) simultaneous[i] = 0;
        repeat (2) @(negedge clk);
        rst_n = 1;
        step(0, 1);
        step(1, 1);                    // Empty: accept only the offer.
        for (int n = 1; n < Depth; n++) begin
            step(1, 1);                // Exchange at each possible middle occupancy.
            step(1, 0);
        end
        step(1, 0);                    // Full, stalled.
        step(1, 1);                    // Full: return old head, discard distinct offer.
        repeat (7) step(0, 1);
        repeat (35) step(1, 1);        // Both ends traverse all 16 slots twice at count 8.
        repeat (8) step(1, 0);
        step(1, 1);
        step(1, 0);                    // Refill with a fresh tag after the dropped offer.
        repeat (Depth) step(0, 1);
        step(0, 1);
        for (int i = 0; i <= Depth; i++)
            if (simultaneous[i] < 1) $fatal(1, "FIFO collision missing at count=%0d", i);
        if (simultaneous[8] != 36 || simultaneous[Depth] != 2 ||
            expected.size() != 0 || accepted != removed || attempts >= 256)
            $fatal(1, "FIFO stimulus or drain incomplete");
        $display("PASS fifo FIFO-01,FIFO-02 widths=8,9 depth=16 pre_counts=0..16 empty_both=%0d count8_both=%0d full_both=%0d offers=%0d accepted=%0d checked_pops=%0d steps=%0d",
                 simultaneous[0], simultaneous[8], simultaneous[Depth], attempts, accepted, removed, steps);
        $finish;
    end

    initial begin
        repeat (160) @(posedge clk);
        $fatal(1, "FIFO simulation watchdog");
    end
endmodule
