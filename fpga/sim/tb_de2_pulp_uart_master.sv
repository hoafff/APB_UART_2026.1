// Exercise conditions the original always-ready, never-error slave cannot drive.
module tb_de2_pulp_uart_master;
    timeunit 1ns;
    timeprecision 1ps;
    bit clk;
    always #10ns clk = !clk;
    logic rst_n = 1, key_press = 0, even_select = 1, hold_rx = 0, echo_enable = 1;
    logic [7:0] key_byte = 0;
    wire [11:0] paddr;
    wire [31:0] pwdata;
    wire pwrite, psel, penable;
    logic [31:0] prdata = 0;
    logic pready = 0, pslverr = 0;
    wire init_done, fault, even_mode;
    wire [7:0] last_rx, last_lsr;
    de2_pulp_uart_master dut (.*);
    int transfers, wait_edges, cases_done;

    task automatic check(input logic ok, input string detail);
        if (ok !== 1'b1) $fatal(1, "master %s at %0t", detail, $time);
    endtask
    task automatic passed(input string name);
        cases_done++;
        $display("MASTER CASE %02d PASS  %s", cases_done, name);
    endtask
    task automatic reset_master;
        rst_n = 0;
        repeat (3) @(negedge clk);
        rst_n = 1;
    endtask
    task automatic transfer(input logic [11:0] addr, input bit wr, input logic [31:0] data,
                            input logic [31:0] readback = 0, input int stalls = 0,
                            input bit error_response = 0);
        while (!(psel && !penable)) @(negedge clk);
        check({paddr, pwrite, pwdata} === {addr, wr, data}, "unexpected SETUP");
        pready = 0;
        prdata = 32'hcafef00d;
        @(posedge clk);
        @(negedge clk);
        repeat (stalls) begin
            check(psel && penable && {paddr, pwrite, pwdata} === {addr, wr, data}, "wait payload");
            wait_edges++;
            @(negedge clk);
        end
        check(psel && penable && {paddr, pwrite, pwdata} === {addr, wr, data}, "completing ACCESS");
        pready = 1;
        pslverr = error_response;
        prdata = readback;
        @(posedge clk);
        #1ns;
        pready = 0;
        pslverr = 0;
        prdata = 32'hdeadbeef;
        transfers++;
        check(!penable, "duplicated ACCESS");
    endtask
    task automatic key(input logic [7:0] data);
        key_byte = data;
        key_press = 1;
        @(posedge clk);
        #2ns;
        key_press = 0;
    endtask

    initial begin
        #3ns;
        reset_master();
        transfer(3, 1, 'h83, 0, 2);
        transfer(0, 1, 'hb1, 0, 1);
        transfer(1, 1, 'h01, 0, 3);
        transfer(3, 1, 'h0b);
        transfer(2, 1, 'h07);
        check(!init_done, "init early");
        transfer(1, 1, 'h05, 0, 4);
        check(init_done && even_mode && !fault, "init completion");
        passed("six writes stable across zero to four wait states");

        transfer(5, 0, 0, 'h01);
        hold_rx = 1;
        echo_enable = 0;
        fork
            begin transfer(0, 0, 0, 'h5a, 3); end
            begin key('hb1); end
        join
        check(last_rx == 'h5a, "RBR sampling edge");
        transfer(5, 0, 0, 'h01); // RX held, queued echo and key, TX still busy
        transfer(5, 0, 0, 'h20);
        check(last_lsr == 'h20, "LSR sampling edge");
        passed("committed RBR/echo survives hold/mode change and waits for FIFO empty");

        fork
            begin transfer(0, 1, 'hb1, 0, 2); end
            begin wait (pready && penable); key('hb2); end
        join
        transfer(5, 0, 0, 'h20);
        transfer(0, 1, 'h5a);
        transfer(5, 0, 0, 'h20);
        transfer(0, 1, 'hb2);
        check(!fault, "same-edge mailbox refill");
        passed("manual and echo arbitration, simultaneous manual consume/refill");

        fork
            begin transfer(5, 0, 0, 'h00, 5); end
            begin
                key('h11);
                @(negedge clk);
                key('h22);
            end
        join
        check(fault && init_done, "lost press indication");
        transfer(5, 0, 0, 'h20);
        transfer(0, 1, 'h11);
        passed("busy manual slot keeps older byte and sets fault LED");

        transfer(5, 0, 0, 'hff, 2, 1);
        check(fault && !init_done && last_lsr == 'h20, "failed read committed");
        repeat (12) begin @(negedge clk); check(!psel, "traffic after PSLVERR"); end
        reset_master();
        check(!fault && !init_done, "fault reset");
        transfer(3, 1, 'h83);
        transfer(0, 1, 'hb1, 0, 2, 1);
        repeat (12) begin @(negedge clk); check(!psel && fault && !init_done, "init error halt"); end
        passed("runtime and init APB errors halt until reset");

        $display("MASTER PASS cases=%0d transfers=%0d inserted_wait_edges=%0d", cases_done, transfers, wait_edges);
        $finish;
    end
    initial begin #1ms; $fatal(1, "master timeout case=%0d transfers=%0d", cases_done + 1, transfers); end
endmodule
