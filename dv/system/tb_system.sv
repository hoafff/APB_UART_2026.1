`timescale 1ns/1ps
module tb_system;
    localparam int BIT_NS=8640, DEBOUNCE=500000;
    logic clk=0; always #10 clk=~clk;
    logic [1:0] key=2'b10;
    logic [17:0] sw=0;
    logic rx=1,tx;
    logic [4:0] ledr;
    logic [8:0] ledg;
    logic [6:0] h0,h1,h4,h5;
    int parity_mode,init_count,init_cycles,checks,tx_frames,send_pulses;
    bit init_seen;
    bit measure_default_poll;
    int clock_index,last_lsr,poll_samples;
    byte expected_wire[$],received_wire[$];
    time stable_start,release_start;
    bit release_seen;
    de2_115_apb_uart_bringup dut(.CLOCK_50(clk),.KEY(key),.SW(sw),.GPIO_UART_RX(rx),.GPIO_UART_TX(tx),
        .LEDR(ledr),.LEDG(ledg),.HEX0(h0),.HEX1(h1),.HEX4(h4),.HEX5(h5));
    function automatic logic [6:0] expected_hex(input int n);
        string glyphs[16]='{"abcdef","bc","abdeg","abcdg","bcfg","acdfg","acdefg","abc","abcdefg","abcdfg","abcefg","cdefg","adef","bcdeg","adefg","aefg"};
        logic [6:0] segments;
        segments='1;
        for(int k=0;k<glyphs[n].len();k++) segments[int'(glyphs[n].getc(k))-97]=0;
        return segments;
    endfunction
    task automatic check(input bit ok,input string why);
        checks++; if(!ok) $fatal(1,"SYSTEM_CHECK %s",why);
    endtask
    task automatic cycles(input int n); repeat(n) @(negedge clk); endtask
    task automatic boot(input int p);
        parity_mode=p; sw=0; sw[14]=(p!=0); sw[15]=(p==2);
        key=2'b10; rx=1; #1ps; check(!dut.rst_n && tx,"async reset assert");
        cycles(64); key[0]=1;
        @(posedge clk); #1ps; check(!dut.rst_n,"reset release must wait first clock");
        @(posedge clk); #1ps; check(dut.rst_n,"reset release after second clock");
        cycles(40); check(ledg[0] && !ledg[1],"init success within bound");
        check(init_count==6,"exactly six init writes"); cycles(1000);
    endtask
    task automatic peer(input byte data,input bit bad_parity=0,input bit bad_stop=0);
        bit parity;
        parity=^data; if(parity_mode==1) parity=~parity;
        rx=0; #(BIT_NS);
        for(int b=0;b<8;b++) begin rx=data[b]; #(BIT_NS); end
        if(parity_mode!=0) begin rx=parity^bad_parity; #(BIT_NS); end
        rx=!bad_stop; #(BIT_NS); rx=1; #(BIT_NS);
    endtask
    always @(posedge clk) begin
        int expected_addr,expected_data;
        clock_index++;
        if(measure_default_poll && dut.rst_n && dut.psel && dut.penable && dut.pready && !dut.pwrite && dut.paddr==20) begin
            if(poll_samples>0) check(clock_index-last_lsr>=5000 && clock_index-last_lsr<=5003,"default board poll 5000 cycles");
            last_lsr=clock_index; poll_samples++;
        end
        if(!dut.rst_n) begin init_count=0; init_cycles=0; init_seen=0; expected_wire.delete(); end
        else begin
            init_cycles++;
            if(ledg[0] && !init_seen) begin check(init_cycles<=32,"init latency <=32 clocks"); init_seen=1; end
            check(ledg[7:2]==0,"unused LEDs zero");
            if(dut.psel && dut.penable && dut.pready) begin
                check(!dut.pslverr,"no unexpected APB error");
                if(init_count<6) begin
                    case(init_count)
                        0:begin expected_addr=12; expected_data='h83; end
                        1:begin expected_addr=0; expected_data=27; end
                        2:begin expected_addr=4; expected_data=0; end
                        3:begin expected_addr=12; expected_data=(parity_mode==0 ? 3:(parity_mode==1 ? 'h0b:'h1b)); end
                        4:begin expected_addr=8; expected_data=7; end
                        default:begin expected_addr=4; expected_data=5; end
                    endcase
                    check(dut.pwrite && dut.paddr==expected_addr && dut.pwdata==expected_data,"init address/data/order");
                    init_count++;
                end else if(dut.pwrite && dut.paddr==0) expected_wire.push_back(dut.pwdata[7:0]);
            end
        end
    end
    always @(posedge dut.key_sync[1]) stable_start=$time;
    always @(negedge dut.key_sync[1]) if(dut.rst_n) begin release_start=$time; release_seen=1; end
    always @(negedge dut.stable_q) if(dut.rst_n && release_seen)
        check($time-release_start==DEBOUNCE*20,"exact 500000 synchronized samples release");
    always @(posedge dut.send_pulse) begin
        send_pulses++;
        check($time-stable_start==DEBOUNCE*20,"exact 500000 synchronized samples press_count_before press pulse");
    end
    initial begin : decode
        byte value,expected;
        bit parity;
        forever begin
            @(negedge tx);
            if(!dut.rst_n) continue;
            #(BIT_NS/2); check(tx==0,"start bit center");
            value=0; parity=0;
            for(int b=0;b<8;b++) begin #(BIT_NS); value[b]=tx; parity^=tx; end
            if(parity_mode!=0) begin #(BIT_NS); check(tx==(parity_mode==2 ? parity:~parity),"TX parity"); end
            #(BIT_NS); check(tx==1,"stop bit"); #(BIT_NS/2);
            check(expected_wire.size()>0,"no spurious UART frame");
            expected=expected_wire.pop_front(); check(value==expected,"wire byte matches successful THR");
            received_wire.push_back(value); tx_frames++;
        end
    end
    initial begin : main
        byte value;
        int press_count_before;
        boot(0);
        sw[13:8]=6'b101101; sw[7:0]='h41; cycles(50000); // setup data >=1 ms press_count_before press
        check(h1==7'b0011001 && h0==7'b1111001,"TX HEX nibble/polarity");
        // Short bounce must not produce a request.
        press_count_before=send_pulses;
        repeat(4) begin key[1]=0; cycles(3); key[1]=1; cycles(3); end
        cycles(30); check(send_pulses==press_count_before,"bounce rejected");
        key[1]=0; wait(dut.send_pulse); #1ns; sw[7:0]='h42;
        cycles(DEBOUNCE+10000); check(send_pulses==press_count_before+1,"held button one pulse");
        check(received_wire.size()==1,"one manual UART frame"); value=received_wire.pop_front(); check(value=='h41,"manual byte captured press_count_before SW change");
        // Release bounce and N-1 samples cannot re-arm a held key.
        repeat(3) begin key[1]=1; cycles(40); key[1]=0; cycles(40); end
        cycles(DEBOUNCE+10);
        check(send_pulses==press_count_before+1,"release bounce must not re-arm");
        key[1]=1;
        @(negedge dut.key_sync[1]);
        repeat(DEBOUNCE-1) @(posedge clk);
        #1ps; check(dut.stable_q==1,"release N-1 remains pressed");
        @(posedge clk); #1ps; check(dut.stable_q==0,"release N becomes stable");
        @(negedge clk);
        key[1]=0; wait(dut.send_pulse); cycles(10000);
        check(received_wire.size()==1,"new press after stable release"); value=received_wire.pop_front(); check(value=='h42,"second manual byte");
        key[1]=1; cycles(DEBOUNCE+10);
        $display("SYS_COV|debounce_exact_bounce_hold_release|1");
        $display("SYS_COV|debounce_release_n_minus_1_n|1");
        $display("SYS_COV|debounce_release_bounce|1");
        $display("SYS_COV|manual_capture_hex|1");
        $display("SYS_COV|reset_sync_and_reserved_switches|1");
        for(int p=0;p<3;p++) begin
            boot(p); peer('h3c); cycles(6000);
            check(h5==7'b0110000 && h4==7'b1000110,"RX HEX =3C");
            sw[17]=1; cycles(100);
            peer('h5a); peer('ha5); cycles(16000);
            check(received_wire.size()==2,"two echo frames");
            value=received_wire.pop_front(); check(value=='h5a,"echo first byte");
            value=received_wire.pop_front(); check(value=='ha5,"echo second byte");
            // Changing parity switches without reset must not change active config.
            sw[14]=!sw[14]; sw[15]=!sw[15]; cycles(100);
            peer('h69); cycles(10000); value=received_wire.pop_front(); check(value=='h69,"parity mode latched until reset");
            sw[17]=0; sw[16]=1; cycles(1000);
            for(int k=0;k<17;k++) peer(byte'(k));
            cycles(11000); check(ledr[1],"hold-RX produces overrun LED");
            sw[16]=0; cycles(15000);
            check(ledr[1],"OE LED remains sticky after LSR ack");
            check(h5==7'b1000000 && h4==7'b0001110,"drop-new retains first sixteen, last displayed 0F");
            if(p!=0) begin peer('ha6,1); cycles(6000); check(ledr[2],"parity error LED"); end
            peer('ha6,0,1); cycles(6000); check(ledr[3],"framing error LED");
            rx=0; #(BIT_NS*16); rx=1; #(BIT_NS*2); cycles(6000); check(ledr[4],"break LED");
            check(ledg[1]==0,"no controller fault during normal use");
            $display("SYS_COV|mode_%0d_rx_echo_hold_errors|1",p);
        end
        boot(0); check(ledr==0 && ledg[1]==0,"reset clears sticky LEDs");
        sw[17]=1; cycles(100);
        for(int k=0;k<32;k++) peer(byte'(k));
        cycles(16000); check(received_wire.size()==32,"finite echo burst lossless");
        for(int k=0;k<32;k++) begin value=received_wire.pop_front(); check(value==k,"echo burst order"); end
        check(expected_wire.size()==0,"all accepted writes observed on wire");
        $display("SYS_COV|echo_burst32|1");
        boot(0); sw[16]=1; measure_default_poll=1; poll_samples=0;
        cycles(16000); measure_default_poll=0; check(poll_samples>=3,"three default board poll observations");
        $display("SYS_COV|default_poll_5000_cycles|1");
        // Exercise all segment patterns through the actual SW and serial paths.
        boot(0);
        for(int nibble=0;nibble<16;nibble++) begin
            sw[7:0]=8'(nibble*17); cycles(8);
            check(h0==expected_hex(nibble) && h1==expected_hex(nibble),"all TX HEX patterns");
            peer(8'(nibble*17)); cycles(6000);
            check(h4==expected_hex(nibble) && h5==expected_hex(nibble),"all RX HEX patterns");
        end
        $display("SYS_COV|hex_all_16_patterns|1");
        $display("SYS_TEST_COMPLETED|checks=%0d|tx=%0d|press=%0d",checks,tx_frames,send_pulses);
        $finish;
    end
    initial begin #200_000_000; $fatal(1,"SYSTEM_WATCHDOG"); end
endmodule
