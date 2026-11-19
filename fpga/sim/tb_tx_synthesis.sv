`timescale 1ns/1ps

module tb_tx_synthesis;
    reg CLK = 0, RSTN = 1, PWRITE = 0, PSEL = 0, PENABLE = 0, rx_i = 1;
    reg [11:0] PADDR = 0;
    reg [31:0] PWDATA = 0;
    wire [35:0] reference_ports, netlist_ports;
    apb_uart_sv rtl (.PRDATA(reference_ports[35:4]), .PREADY(reference_ports[3]),
                     .PSLVERR(reference_ports[2]), .tx_o(reference_ports[1]),
                     .event_o(reference_ports[0]), .*);
    apb_uart_sv_mapped netlist (.PRDATA(netlist_ports[35:4]), .PREADY(netlist_ports[3]),
                         .PSLVERR(netlist_ports[2]), .tx_o(netlist_ports[1]),
                         .event_o(netlist_ports[0]), .*);

    reg dlab = 0, clear_pending = 0, have_held = 0, corrupt_store;
    reg [7:0] held, memory [0:15];
    reg [255:0] stored_bytes = 0;
    integer cycles = 0, comparisons = 0, stores = 0, refused = 0, divergent_idle = 0;
    integer count = 0, wrptr = 0, clears = 0, divisor_writes = 0;

    task automatic compare_ports;
        if ((^reference_ports === 1'bx) || reference_ports !== netlist_ports)
            $fatal(1, "port mismatch cycle=%0d clk=%b RTL=%h net=%h", cycles, CLK,
                   reference_ports, netlist_ports);
        comparisons++;
    endtask

    // One settled pre-edge sample and one post-NBA sample. Track DLAB and
    // delayed FCR clear from APB, independent of the DUT's write decode.
    task automatic tick;
        reg access_wr, offer, store_byte, pop_byte;
        #4;
        compare_ports();
        access_wr = PSEL && PENABLE && PWRITE;
        offer = access_wr && PADDR[2:0] == 0 && !dlab;
        if (rtl.fifo_tx_valid !== offer)
            $fatal(1, "write decode cycle=%0d", cycles);
        if (offer) begin
            held = PWDATA[7:0];
            have_held = 1;
        end else if (have_held && held != PWDATA[7:0])
            divergent_idle++;
        if (have_held && rtl.fifo_tx_data !== held)
            $fatal(1, "held or offered byte cycle=%0d", cycles);

        store_byte = offer && count < 16;
        pop_byte = rtl.tx_ready && count != 0;
        if (!RSTN) begin
            count = 0;
            wrptr = 0;
            dlab = 0;
            clear_pending = 0;
            for (integer i = 0; i < 16; i++) memory[i] = 0;
        end else begin
            if (store_byte) begin
                memory[wrptr] = PWDATA[7:0] ^ {7'b0, corrupt_store};
                stored_bytes[PWDATA[7:0]] = 1;
                stores++;
            end else if (offer)
                refused++;
            if (clear_pending) begin
                count = 0;
                wrptr = 0;
                clears++;
            end else begin
                count = count + int'(store_byte) - int'(pop_byte);
                if (store_byte) wrptr = (wrptr + 1) % 16;
            end
            if (access_wr && PADDR[2:0] == 0 && dlab) divisor_writes++;
            if (access_wr && PADDR[2:0] == 3) dlab = PWDATA[7];
            clear_pending = access_wr && PADDR[2:0] == 2 && PWDATA[2];
        end
        CLK = 1;
        #1;
        compare_ports();
        if (rtl.tx_elements !== count[4:0] || rtl.uart_tx_fifo_i.pointer_in !== wrptr[3:0])
            $fatal(1, "FIFO occupancy/pointer cycle=%0d", cycles);
        for (integer i = 0; i < 16; i++)
            if (rtl.uart_tx_fifo_i.buffer[i] !== memory[i])
                $fatal(1, "FIFO slot mismatch cycle=%0d slot=%0d expected=%h got=%h",
                       cycles, i, memory[i], rtl.uart_tx_fifo_i.buffer[i]);
        #4;
        CLK = 0;
        #1;
        cycles++;
    endtask

    task automatic idle(input integer n);
        PSEL = 0;
        PENABLE = 0;
        repeat (n) begin
            PWDATA = (cycles * 73) ^ 32'ha55a4f0d;
            tick();
        end
    endtask

    task automatic transfer(input bit wr, input reg [11:0] addr, input reg [7:0] data);
        PSEL = 1;
        PENABLE = 0;
        PWRITE = wr;
        PADDR = addr;
        PWDATA = {24'h69c3af, data};
        tick();
        PENABLE = 1;
        tick();
    endtask

    task automatic configure;
        transfer(1, 3, 'h83);
        transfer(1, 'hf00, 15);
        transfer(1, 1, 0);
        transfer(1, 3, 'h03);
        transfer(1, 1, 'h05);
    endtask

    initial begin
        corrupt_store = $test$plusargs("negative-store");
        #1;
        RSTN = 0;
        idle(2);
        RSTN = 1;
        configure();
        // Full FIFO, back-to-back writes, clear while busy, reset during TX.
        for (integer i = 0; i < 24; i++) transfer(1, 'hd80, i * 29 + 7);
        transfer(1, 2, 'h07);
        idle(4);
        RSTN = 0;
        idle(2);
        RSTN = 1;
        configure();
        // Independent 8N1 peer at sixteen clocks/bit, then check RBR on ACCESS.
        rx_i = 0;
        idle(16);
        for (integer i = 0; i < 8; i++) begin
            rx_i = (8'ha6 >> i) & 1;
            idle(16);
        end
        rx_i = 1;
        idle(35);
        PSEL = 1; PENABLE = 0; PWRITE = 0; PADDR = 0;
        tick();
        PENABLE = 1;
        #1;
        if (reference_ports[35:4] !== 32'ha6) $fatal(1, "RBR peer byte");
        tick();
        // Every byte gets a slot. Interleave reads, SETUP and unrelated data.
        for (integer i = 0; i < 256; i++) begin
            while (count == 16) idle(1);
            transfer(1, 'ha40, i ^ 8'h95);
            transfer(0, 5, ~i);
        end
        idle(3000);
        if (reference_ports[1] !== 1 || count != 0 || stored_bytes !== {256{1'b1}} ||
            refused == 0 || divergent_idle == 0 || clears == 0 || divisor_writes != 2)
            $fatal(1, "coverage/idle endpoint");
        $display("PASS cycles=%0d port_samples=%0d store_edges=%0d refused_full=%0d idle_data_differs=%0d clears=%0d DLAB_writes=%0d distinct_bytes=256 RX=a6",
                 cycles, comparisons, stores, refused, divergent_idle, clears, divisor_writes);
        $finish;
    end
    initial #1500000 $fatal(1, "timeout");
endmodule
