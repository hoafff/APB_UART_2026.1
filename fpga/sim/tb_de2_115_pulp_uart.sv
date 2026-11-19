module tb_de2_115_pulp_uart;
    timeunit 1ns;
    timeprecision 1ps;
    localparam realtime PEER_BIT = 1.0e9 / 115200.0;  // peer's own oscillator, ns
    bit CLOCK_50;
    logic [1:0] KEY = 2'b11;
    logic [17:0] SW = '0;
    logic GPIO_UART_RX = 1'b1;
    wire GPIO_UART_TX;
    wire [4:0] LEDR;
    wire [8:0] LEDG;
    wire [6:0] HEX0, HEX1, HEX4, HEX5;
    always #10ns CLOCK_50 = !CLOCK_50;
    de2_115_pulp_uart dut (.*);

    typedef logic [7:0] octet;
    typedef struct packed {bit even_mode; bit abort_on_reset; octet data;} frame_t;
    octet expect_rbr[$], expect_thr[$];
    frame_t expect_pin[$];
    bit expected_even, decoding, previous_setup, saved_write;
    logic [11:0] saved_addr;
    logic [31:0] saved_wdata;
    logic [7:0] observed_lsr;
    int init_step, init_count, setups, accesses, polls, pops, pushes;
    int complete_frames, aborted_frames, parity_zero, parity_one, scenarios;
    localparam logic [11:0] INIT_ADDR [0:5] = '{3, 0, 1, 3, 2, 1};
    localparam octet INIT_DATA [0:5] = '{'h83, 'hb1, 'h01, 'h03, 'h07, 'h05};
    localparam logic [6:0] DIGIT [0:15] = '{
        'h40, 'h79, 'h24, 'h30, 'h19, 'h12, 'h02, 'h78,
        'h00, 'h10, 'h08, 'h03, 'h46, 'h21, 'h06, 'h0e
    };

    task automatic require(input logic ok, input string why);
        if (ok !== 1'b1) $fatal(1, "%0t %s", $time, why);
    endtask
    task automatic passed(input string name);
        scenarios++;
        $display("BOARD CASE %02d PASS  %s", scenarios, name);
    endtask
    function automatic logic [13:0] display_byte(input octet value);
        return {DIGIT[value[7:4]], DIGIT[value[3:0]]};
    endfunction
    // A permutation of 0..255. Both parity polarities and all data bits occur.
    function automatic octet pattern(input int index);
        return octet'(index * 73 + 37);
    endfunction

    // Passive APB observer. Sample the pins seen by the slave BEFORE NBA on
    // the rising edge, including RBR data before the FIFO advances.
    always @(posedge CLOCK_50) begin : check_apb
        octet expected;
        if (!dut.rst_n) begin
            previous_setup = 0;
            init_step = 0;
            observed_lsr = '0;
        end else begin
            require(dut.pready && !dut.pslverr, "original APB ready/error constants");
            require(dut.penable == previous_setup, "setup must lead to exactly one access");
            if (dut.penable) begin
                require(dut.psel && {dut.paddr, dut.pwrite, dut.pwdata} ===
                        {saved_addr, saved_write, saved_wdata}, "APB controls changed during transfer");
                accesses++;
                if (init_step < 6) begin
                    expected = init_step == 3 && expected_even ? 8'h0b : INIT_DATA[init_step];
                    require(!LEDG[0] && dut.pwrite && dut.paddr == INIT_ADDR[init_step] &&
                            dut.pwdata == {24'b0, expected}, $sformatf("init write %0d", init_step));
                    init_step++;
                    if (init_step == 6) init_count++;
                end else begin
                    require(LEDG[0], "runtime access before init");
                    if (!dut.pwrite && dut.paddr == 12'h005) begin
                        polls++;
                        observed_lsr = dut.prdata[7:0];
                        require((dut.prdata & 32'hffffff9e) == 0, "unexpected original LSR bits");
                    end else if (!dut.pwrite && dut.paddr == 0) begin
                        require(observed_lsr[0], "RBR pop without DR");
                        require(expect_rbr.size() > 0, "unexpected or duplicate RBR pop");
                        expected = expect_rbr.pop_front();
                        require(dut.prdata == {24'b0, expected}, $sformatf("RBR expected %02x got %02x", expected, dut.prdata));
                        pops++;
                    end else if (dut.pwrite && dut.paddr == 0) begin
                        require(observed_lsr[5], "THR push without TX FIFO empty");
                        require(expect_thr.size() > 0, "unexpected or duplicate THR push");
                        expected = expect_thr.pop_front();
                        require(dut.pwdata == {24'b0, expected}, $sformatf("THR expected %02x got %02x", expected, dut.pwdata));
                        pushes++;
                    end else $fatal(1, "unexpected runtime access wr=%b addr=%03x", dut.pwrite, dut.paddr);
                end
            end
            previous_setup = dut.psel && !dut.penable;
            if (previous_setup) begin
                setups++;
                saved_addr = dut.paddr;
                saved_write = dut.pwrite;
                saved_wdata = dut.pwdata;
            end
        end
    end

    // Decode physical TX without consulting APB, the UART FSM or its baud counter.
    initial forever begin : pin_receiver
        frame_t item;
        octet decoded;
        @(negedge GPIO_UART_TX);
        require(expect_pin.size() > 0, "unexpected TX start on GPIO");
        item = expect_pin.pop_front();
        decoding = 1;
        if (item.abort_on_reset) begin
            @(negedge KEY[0]);
            #1ns;
            require(GPIO_UART_TX, "reset failed to return TX to mark");
            aborted_frames++;
        end else begin
            #(PEER_BIT / 2.0);
            require(!GPIO_UART_TX, "TX start midpoint");
            for (int i = 0; i < 8; i++) begin
                #(PEER_BIT);
                decoded[i] = GPIO_UART_TX;
            end
            require(decoded === item.data, $sformatf("TX pin expected %02x got %02x", item.data, decoded));
            if (item.even_mode) begin
                #(PEER_BIT);
                require(GPIO_UART_TX === (^decoded), "TX even parity at peer sample");
                if (GPIO_UART_TX) parity_one++; else parity_zero++;
            end
            #(PEER_BIT);
            require(GPIO_UART_TX, "TX stop midpoint");
            complete_frames++;
        end
        decoding = 0;
    end

    task automatic want_tx(input octet data, input bit abort_on_reset = 0);
        frame_t item;
        item = '{expected_even, abort_on_reset, data};
        // Independent checker control. Leave TX stimulus and APB expectations intact.
        if ($test$plusargs("negative-pin") && pushes == 0) item.data ^= 8'h01;
        expect_thr.push_back(data);
        expect_pin.push_back(item);
    endtask
    task automatic peer_cell(input bit match_divisor);
        if (match_divisor) #8680ns;
        else #(PEER_BIT);
    endtask
    // Successive calls put the next start directly after one stop cell.
    // The full-FIFO characterization alone uses the matched 8680 ns source.
    task automatic peer_frame(input octet data, input bit corrupt_parity = 0,
                              input bit match_divisor = 0);
        GPIO_UART_RX = 0;
        peer_cell(match_divisor);
        for (int i = 0; i < 8; i++) begin
            GPIO_UART_RX = data[i];
            peer_cell(match_divisor);
        end
        if (expected_even) begin
            GPIO_UART_RX = (^data) ^ corrupt_parity;
            peer_cell(match_divisor);
        end
        GPIO_UART_RX = 1;
        peer_cell(match_divisor);
    endtask
    task automatic drain;
        while (expect_pin.size() != 0 || expect_thr.size() != 0 || expect_rbr.size() != 0 || decoding)
            @(negedge CLOCK_50);
        #(PEER_BIT); // past the last stop cell and any unexpected adjacent start
    endtask
    task automatic board_reset(input bit mode_even);
        expected_even = mode_even;
        SW[14] = mode_even;
        KEY[0] = 0;
        #1us;
        require(!dut.rst_n && LEDG == 0 && LEDR == 0 && GPIO_UART_TX, "reset-held board outputs");
        @(negedge CLOCK_50);
        #3ns;
        KEY[0] = 1;
        @(posedge CLOCK_50);
        #1ns;
        require(!dut.rst_n, "reset released on first edge");
        @(posedge CLOCK_50);
        #1ns;
        require(dut.rst_n, "reset still held after second edge");
        wait (LEDG[0] && LEDG[6:5] == 2'b11);
        #1ns;
        require(LEDG[2] == mode_even && !LEDG[1] && LEDR == 0, "ready, format, LSR LEDs");
        require(LEDG[8] && !LEDG[7], "raw event at idle and spare LED");
        require({HEX5, HEX4} == display_byte(0), "reset RX display");
    endtask
    task automatic press_and_release(input octet data);
        SW[7:0] = data;
        #1us;
        require({HEX1, HEX0} == display_byte(data), "TX switch display");
        want_tx(data);
        KEY[1] = 0;
        #11ms;
        KEY[1] = 1;
        #11ms;
    endtask
    task automatic stream(input int count);
        octet data;
        int before_frames;
        before_frames = complete_frames;
        for (int i = 0; i < count; i++) begin
            data = pattern(i);
            expect_rbr.push_back(data);
            want_tx(data);
            peer_frame(data);
        end
        drain();
        require(complete_frames == before_frames + count, "missing contiguous echo");
        require({HEX5, HEX4} == display_byte(data), "last contiguous RX display");
        $display("BOARD STREAM parity=%s contiguous=%0d echo=%0d", expected_even ? "E" : "N", count, count);
    endtask

    initial begin : exercise
        realtime previous_edge, interval;
        int before_pops, before_pushes, before_polls;
        #7ns;
        SW[15] = 1;
        board_reset(0);
        before_polls = polls;
        repeat (4999) @(posedge CLOCK_50);
        #1ns;
        require(polls == before_polls && !dut.psel && LEDG[8], "idle poll bypassed timer on raw event");
        @(posedge CLOCK_50);
        #1ns;
        require(dut.psel && !dut.penable && dut.paddr == 5, "5000-clock idle poll threshold");
        passed("8N1 init, synchronized release, idle TX/event/LEDs, 5000-clock poll");

        SW[7:0] = 8'h55;
        #1us;
        KEY[1] = 0;
        #4ms;
        KEY[1] = 1;
        #2ms;
        require(pushes == 0 && {HEX1, HEX0} == display_byte('h55), "short key bounce or HEX");
        want_tx('h55);
        fork
            begin
                @(negedge GPIO_UART_TX);
                previous_edge = $realtime;
                for (int i = 0; i < 9; i++) begin
                    @(GPIO_UART_TX);
                    interval = $realtime - previous_edge;
                    previous_edge = $realtime;
                    require(interval == ((i == 0) ? 8700.0 : 8680.0),
                            $sformatf("0x55 pin spacing edge=%0d ns=%0.3f", i, interval));
                end
                $display("BOARD BAUD 0x55 start=8700 ns regular_intervals=8 x 8680 ns = 434 CLOCK_50 cycles");
            end
            begin
                KEY[1] = 0;
                #9.99ms;
                require(pushes == 0, "keypress accepted before debounce interval");
                #0.31ms;
                SW[7:0] = 'ha6;
                #11ms;  // second full debounce interval, still held
                KEY[1] = 1;
                #3ms;
                KEY[1] = 0; // release bounce does not rearm the key
                #1ms;
                KEY[1] = 1;
                #11ms;
            end
        join
        drain();
        require(pushes == 1 && complete_frames == 1, "key held repeated");
        passed("real 10 ms debounce, press/release bounce, held KEY1, 0x55 at measured baud");

        expect_rbr.push_back('h41);
        peer_frame('h41);
        drain();
        require({HEX5, HEX4} == display_byte('h41) && complete_frames == 1, "RX-only character");
        passed("peer 0x41 reaches RX display with echo disabled");

        SW[17:16] = 2'b11;
        #1us;
        require(LEDG[4:3] == 2'b11, "hold and echo LEDs");
        before_pops = pops;
        for (int i = 0; i < 16; i++) peer_frame(pattern(i));
        #110us;
        require(pops == before_pops && LEDR == 5'b00001 &&
                {HEX5, HEX4} == display_byte('h41), "hold admitted an RBR or missed DR");
        press_and_release('ha6);
        require(pops == before_pops, "manual TX released RX hold");
        for (int i = 0; i < 16; i++) begin
            expect_rbr.push_back(pattern(i));
            want_tx(pattern(i));
        end
        SW[16] = 0;
        drain();
        require(pops == before_pops + 16 && {HEX5, HEX4} == display_byte(pattern(15)), "held FIFO order/count");
        passed("all 16 FIFO entries held, KEY1 TX while held, ordered echo after release");

        // FIFO-04: the seventeenth byte waits in SAVE_DATA outside the full FIFO.
        SW[16] = 1;
        #1us;
        before_pops = pops;
        for (int i = 0; i < 18; i++) begin
            peer_frame(octet'('h40 + i), 0, 1);
            #8680ns;
        end
        #110us;
        require(pops == before_pops && LEDR == 1, "full FIFO while held");
        for (int i = 0; i < 17; i++) begin
            expect_rbr.push_back(octet'('h40 + i));
            want_tx(octet'('h40 + i));
        end
        SW[16] = 0;
        drain();
        #110us;
        require(pops == before_pops + 17 && {HEX5, HEX4} == display_byte('h50) && LEDR == 0,
                "unexpected full-FIFO retention or overrun flag");
        passed("held 18 timed input frames, 16 FIFO + one waiting byte recovered, no OE");

        SW[14] = 1;  // apply E on the next reset
        SW[15] = 0;
        stream(4);
        stream(16);
        stream(64);
        require(!LEDG[2], "live format switched before reset");
        passed("uninterrupted 4/16/64-byte 8N1 streams with live mode switch change");

        SW[15] = 1;
        board_reset(1);
        press_and_release('h01);
        drain();
        SW[15] = 0;
        stream(4);
        stream(16);
        stream(64);
        require(LEDG[2] && parity_zero > 0 && parity_one > 0, "even parity coverage");
        passed("8E1 KEY1 and 4/16/64 contiguous echoes with both TX parity polarities");

        expect_rbr.push_back('h27);
        want_tx('h27);
        peer_frame('h27, 1);
        drain();
        require(!LEDR[2] && {HEX5, HEX4} == display_byte('h27), "original bad-parity behavior");
        passed("inverted incoming parity accepted with LSR[2] clear, valid even echo");

        before_pushes = pushes;
        expect_rbr.push_back('h00);
        want_tx('h00, 1);
        // Abort a low outgoing frame and a second, partial incoming frame.
        peer_frame('h00);
        wait (decoding);
        require(!GPIO_UART_TX, "reset test needs an active low TX pin");
        GPIO_UART_RX = 0;
        #1.5us;
        GPIO_UART_RX = 1;
        board_reset(0);
        require(aborted_frames == 1 && pushes == before_pushes + 1, "aborted transmission");
        #150us;
        expect_rbr.push_back('h5a);
        want_tx('h5a);
        peer_frame('h5a);
        drain();
        require({HEX5, HEX4} == display_byte('h5a) && !LEDG[1], "traffic after mid-frame reset");
        passed("reset interrupts TX/RX, clears stale bytes and reinitializes 8N1 echo");

        require(init_count == 3 && accesses == 6 * init_count + polls + pops + pushes &&
                setups == accesses && expect_rbr.size() == 0 && expect_thr.size() == 0 &&
                expect_pin.size() == 0, "APB/serial accounting");
        $display("BOARD PASS cases=%0d init_sequences=%0d setups=%0d accesses=%0d lsr=%0d rbr=%0d thr=%0d tx_frames=%0d reset_aborts=%0d even_p0=%0d even_p1=%0d",
                 scenarios, init_count, setups, accesses, polls, pops, pushes, complete_frames,
                 aborted_frames, parity_zero, parity_one);
        $finish;
    end
    initial begin
        #180ms;
        $fatal(1, "board timeout case=%0d expected RBR/THR/pin=%0d/%0d/%0d frames=%0d",
               scenarios + 1, expect_rbr.size(), expect_thr.size(), expect_pin.size(), complete_frames);
    end
endmodule
