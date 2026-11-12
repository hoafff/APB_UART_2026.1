class target_base_test extends uvm_test;
    `uvm_component_utils(target_base_test)
    apb_uart_env e;
    int test_id;
    int explicit_checks;
    function new(string name,uvm_component parent); super.new(name,parent); endfunction
    function void build_phase(uvm_phase phase);
        super.build_phase(phase); e=apb_uart_env::type_id::create("e",this);
    endfunction
    function void check(bit ok,string why);
        explicit_checks++;
        if(!ok) `uvm_error("TEST_CHECK",why)
    endfunction
    task transfer(bit write,bit[11:0] addr,bit[31:0] data,output bit[31:0] value,input bit error=0);
        apb_single_seq s=apb_single_seq::type_id::create("single");
        s.tr=apb_tx::type_id::create("request");
        s.tr.write=write; s.tr.addr=addr; s.tr.data=data; s.tr.expected_error=error;
        s.start(e.seqr); value=s.tr.rdata;
    endtask
    task wr(bit[11:0] addr,bit[31:0] data,bit error=0);
        bit[31:0] ignored; transfer(1,addr,data,ignored,error);
    endtask
    task rd(bit[11:0] addr,output bit[31:0] value,input bit error=0); transfer(0,addr,0,value,error); endtask
    task expect_reg(bit[11:0] addr,bit[31:0] expected,bit error=0);
        bit[31:0] value; rd(addr,value,error);
        check(value===expected,$sformatf("address=%03h read=%08h expected=%08h",addr,value,expected));
    endtask
    task reset_dut();
        @(negedge e.vif.CLK);
        e.vif.RSTN=0; e.vif.PSEL=0; e.vif.PENABLE=0; e.vif.rx_i=1;
        repeat(6) @(negedge e.vif.CLK);
        e.vif.RSTN=1;
        repeat(3) @(negedge e.vif.CLK);
    endtask
    task configure(int divisor=27,int n=8,int parity_mode=0,int stops=1,uart_byte_t fcr=7);
        e.cfg.divisor=divisor; e.cfg.data_bits=n; e.cfg.parity_mode=parity_mode; e.cfg.stop_bits=stops;
        wr('h00c,8'h80|e.cfg.lcr()); wr(0,divisor&255); wr(4,(divisor>>8)&255);
        wr('h00c,e.cfg.lcr()); wr(8,fcr); wr(4,0);
        repeat(16*divisor+8) @(negedge e.vif.CLK);
    endtask
    task wait_frames(int count=3);
        repeat(count*12*e.cfg.cycles()+8) @(negedge e.vif.CLK);
    endtask
    task check_irq(uart_byte_t expected,bit level);
        #1ns;
        check(e.vif.event_o===level,$sformatf("IRQ actual=%b expected=%b",e.vif.event_o,level));
        expect_reg(8,expected);
    endtask
    task reg_case();
        bit[31:0] value;
        expect_reg(0,0); expect_reg(4,0); expect_reg(8,1); expect_reg(12,0); expect_reg(20,'h60);
        wr(0,'h41,1); // divisor zero
        wr(12,'hffff_ffff); expect_reg(12,'h9f);
        wr(0,'h123456ab); wr(4,'h98765412); expect_reg(0,'hab); expect_reg(4,'h12);
        expect_reg(8,1); expect_reg(20,'h60); wr(20,255,1); wr(8,7); expect_reg(8,'hc1);
        wr(12,3); wr(4,255); expect_reg(4,7); wr(4,0);
        for(int k=0;k<4096;k++) begin
            if(!(k inside {0,4,8,12,20})) begin
                rd(12'(k),value,1); check(value==0,"Invalid address must read zero");
            end
        end
        wr(20,'hff,1); wr('h003,'h83,1); wr('h02c,'hff,1); wr('h80c,0,1); expect_reg(12,3);
        // Setup without ACCESS must have no write side effect.
        @(negedge e.vif.CLK); e.vif.PSEL=1; e.vif.PENABLE=0; e.vif.PWRITE=1; e.vif.PADDR=12; e.vif.PWDATA='h1b;
        repeat(3) @(negedge e.vif.CLK);
        e.vif.PSEL=0; e.vif.PWRITE=0;
        expect_reg(12,3); wr(8,7); expect_reg(8,'hc1);
        e.cov.hit("apb.full_address_no_alias"); e.cov.hit("apb.setup_no_side_effect");
        // Back-to-back two transfers, continuously selected, explicit SETUP between.
        @(negedge e.vif.CLK); e.vif.PSEL=1; e.vif.PENABLE=0; e.vif.PWRITE=1; e.vif.PADDR=12; e.vif.PWDATA=3;
        @(negedge e.vif.CLK); e.vif.PENABLE=1;
        @(negedge e.vif.CLK); e.vif.PENABLE=0; e.vif.PADDR=4; e.vif.PWDATA=0;
        @(negedge e.vif.CLK); e.vif.PENABLE=1;
        @(negedge e.vif.CLK); e.vif.PSEL=0; e.vif.PENABLE=0; e.vif.PWRITE=0;
        expect_reg(4,0); e.cov.hit("apb.back_to_back");
        if($test$plusargs("NEGATIVE_APB_PROTOCOL")) begin
            @(negedge e.vif.CLK); e.vif.PSEL=1; e.vif.PENABLE=1;
            repeat(2) @(negedge e.vif.CLK);
        end
    endtask
    task tx_case();
        for(int n=5;n<=8;n++) for(int p=0;p<3;p++) for(int s=1;s<=2;s++) begin
            reset_dut(); configure(2,n,p,s);
            wr(0,'h55); wr(0,'haa); wr(0,0); wr(0,'hff);
            wait_frames(5); expect_reg(20,'h60);
        end
        check(e.sb.tx_checked==96,"24 formats x four TX patterns must be observed");
        e.cov.hit("tx.24_modes_four_patterns");
    endtask
    task rx_case();
        uart_byte_t patterns[4]='{'h00,'hff,'h55,'haa};
        bit[31:0] value;
        for(int n=5;n<=8;n++) for(int p=0;p<3;p++) for(int s=1;s<=2;s++) begin
            reset_dut(); configure(2,n,p,s);
            foreach(patterns[k]) begin
                e.rx_bfm.send(patterns[k]);
                expect_reg(20,'h61); expect_reg(0,patterns[k]&(255>>(8-n))); expect_reg(20,'h60);
            end
        end
        check(e.sb.rx_checked==96,"24 formats x four RX patterns must be compared");
        e.cov.hit("rx.24_modes_four_patterns");
    endtask
    task tolerance_case();
        real rates[3]='{0.98,1.0,1.02};
        int phases[5]='{0,5,10,15,19};
        for(int n=5;n<=8;n++) for(int p=0;p<3;p++) for(int s=1;s<=2;s++)
        foreach(rates[r]) foreach(phases[h]) begin
            reset_dut(); configure(2,n,p,s);
            #(phases[h]);
            e.rx_bfm.send('h55,0,0,rates[r],0);
            e.rx_bfm.send('haa,0,0,rates[r],1);
            expect_reg(20,'h61); expect_reg(0,'h55&(255>>(8-n))); expect_reg(0,'haa&(255>>(8-n)));
            expect_reg(20,'h60);
            e.cov.hit($sformatf("tolerance.%0d.%0d.%0d.%0d.%0d",n,p,s,r,h));
        end
        // Default board divisor and minimum divisor have different quantization.
        for(int d=1;d<=27;d+=26) foreach(rates[r]) foreach(phases[h]) begin
            reset_dut(); configure(d,8,2,2); #(phases[h]);
            e.rx_bfm.send('h55,0,0,rates[r],0); e.rx_bfm.send('haa,0,0,rates[r],1);
            expect_reg(0,'h55); expect_reg(0,'haa); expect_reg(20,'h60);
            e.cov.hit($sformatf("tolerance.divisor.%0d.%0d.%0d",d,r,h));
        end
    endtask
    task error_case();
        bit[31:0] value;
        for(int p=1;p<=2;p++) begin
            reset_dut(); configure(3,8,p,2);
            e.rx_bfm.send('h41); e.rx_bfm.send('ha6,1); e.rx_bfm.send('h3c);
            expect_reg(20,'he1); // clean head, error behind it
            expect_reg(0,'h41); expect_reg(20,'he5); expect_reg(20,'h61);
            expect_reg(0,'ha6); expect_reg(0,'h3c); expect_reg(20,'h60);
            e.cov.hit($sformatf("error.parity.%0d",p));
        end
        for(int s=1;s<=2;s++) for(int bit_index=0;bit_index<s;bit_index++) begin
            reset_dut(); configure(3,8,0,s);
            e.rx_bfm.send('ha6,0,2'(1<<bit_index));
            expect_reg(20,'he9); expect_reg(20,'h61); expect_reg(0,'ha6);
            e.rx_bfm.send('h5a); expect_reg(0,'h5a);
            e.cov.hit($sformatf("error.stop.%0d.%0d",s,bit_index));
        end
        for(int p=0;p<3;p++) begin
            reset_dut(); configure(3,8,p,1);
            e.rx_bfm.send(0,0,0,1.0,2,1);
            expect_reg(20,p==1 ? 'hfd:'hf9); expect_reg(20,'h61); expect_reg(0,0); expect_reg(0,0);
            e.rx_bfm.send('h3c); expect_reg(0,'h3c);
            e.cov.hit($sformatf("error.break.%0d",p));
        end
        reset_dut(); configure(2,5,0,1);
        e.rx_bfm.send('hff,1); expect_reg(20,'h61); expect_reg(0,'h1f);
        e.cov.hit("error.parity_disabled");
        reset_dut(); configure(2,5,1,1);
        e.rx_bfm.send('hff,1); expect_reg(20,'he5); expect_reg(0,'h1f);
        e.cov.hit("error.parity_five_bits");
    endtask
    task fifo_case();
        bit[31:0] value;
        reset_dut(); configure(2);
        for(int round=0;round<3;round++) begin
            for(int k=0;k<17;k++) e.rx_bfm.send(uart_byte_t'(round*32+k),0,0,1.0,0);
            repeat(e.cfg.cycles()+8) @(negedge e.vif.CLK);
            expect_reg(20,'h63); expect_reg(20,'h61);
            for(int k=0;k<16;k++) expect_reg(0,round*32+k);
            expect_reg(0,0); expect_reg(20,'h60);
        end
        e.cov.hit("fifo.capacity16_drop17"); e.cov.hit("fifo.pointer_wrap");
        wr(8,0);
        e.rx_bfm.send('h41); e.rx_bfm.send('h42);
        expect_reg(20,'h63); expect_reg(0,'h41); expect_reg(0,0);
        e.cov.hit("fifo.capacity1_drop2");
        wr(8,7); e.rx_bfm.send('h66); wr(8,3); expect_reg(0,0); expect_reg(20,'h60);
        e.cov.hit("fifo.rx_clear");
        e.rx_bfm.send('h77); wr(8,0); expect_reg(0,0); expect_reg(8,1); wr(8,7);
        e.cov.hit("fifo.enable_flush");
        fork
            e.rx_bfm.send('h5a);
            begin repeat(4*e.cfg.cycles()) @(negedge e.vif.CLK); wr(8,3); end
        join
        expect_reg(0,'h5a); e.cov.hit("fifo.rx_clear_active");
        reset_dut(); configure(27);
        for(int k=0;k<17;k++) wr(0,k);
        wr(0,18,1); expect_reg(20,0); // TX full/active, no RX OE
        wr(8,5); expect_reg(20,'h20); wait_frames(2); expect_reg(20,'h60);
        e.cov.hit("fifo.tx_full_error"); e.cov.hit("fifo.tx_clear_active");
    endtask
    task irq_case();
        int levels[4]='{1,4,8,14};
        bit[31:0] value;
        foreach(levels[t]) begin
            reset_dut(); configure(2,8,0,1,uart_byte_t'(7|(t<<6))); wr(4,1);
            for(int k=0;k<levels[t]-1;k++) e.rx_bfm.send(uart_byte_t'(k));
            check_irq('hc1,0);
            e.rx_bfm.send('ha1); check_irq('hc4,1);
            e.rx_bfm.send('ha2); check_irq('hc4,1); rd(0,value); check_irq('hc4,1);
            rd(0,value); check_irq('hc1,0);
            wr(4,0); wr(8,7);
            e.cov.hit($sformatf("irq.threshold.%0d",levels[t]));
        end
        reset_dut(); configure(3,8,2,1); wr(4,7);
        e.rx_bfm.send('ha5,1);
        check_irq('hc6,1); check_irq('hc6,1); // IIR read does not acknowledge RLS
        expect_reg(20,'he5); check_irq('hc4,1); expect_reg(0,'ha5);
        check_irq('hc2,1); check_irq('hc1,0);
        wr(0,'h55); repeat(8) @(negedge e.vif.CLK);
        check_irq('hc2,1); check_irq('hc1,0); wait_frames(2);
        e.cov.hit("irq.priority_rls_rda_thre"); e.cov.hit("irq.thre_ack");
        for(int mask=0;mask<8;mask++) begin
            wr(4,mask); rd(8,value); wr(4,0); check_irq('hc1,0);
            e.cov.hit($sformatf("irq.mask.%0d",mask));
        end
        check(e.vif.event_o==0,"IRQ must deassert with every source masked");
        e.cov.hit("irq.no_stuck_c0");
        for(int mask=0;mask<8;mask++) for(int sources=0;sources<8;sources++) begin
            int code;
            reset_dut(); configure(1,8,2,1,0);
            if(sources&1) wr(4,2); // establish pending even if subsequently masked
            wr(4,mask);
            if(!(sources&1) && (mask&2)) expect_reg(8,2); // acknowledge automatic enable-empty event
            if((sources&4) && !(sources&2)) begin
                e.rx_bfm.send('h11); e.rx_bfm.send('h22); expect_reg(0,'h11); // OE without DR
            end else if(sources&2) e.rx_bfm.send('ha5,(sources&4)!=0);
            code=((mask&4)&&(sources&4)) ? 6 : ((mask&1)&&(sources&2)) ? 4 : ((mask&2)&&(sources&1)) ? 2 : 1;
            check_irq(uart_byte_t'(code),code!=1);
            wr(4,0); wr(8,7);
            e.cov.hit($sformatf("irq.source_mask.%0d.%0d",sources,mask));
        end
    endtask
    task reset_case();
        int delays[6]='{0,1,5,9,10,11};
        bit[31:0] value;
        foreach(delays[k]) begin
            reset_dut(); configure(3,8,2,2); wr(4,7); wr(0,'h55); wr(0,'haa);
            e.vif.rx_i=0;
            repeat(delays[k]*e.cfg.cycles()) @(negedge e.vif.CLK);
            reset_dut(); expect_reg(20,'h60); expect_reg(8,1); expect_reg(0,0);
            check(e.vif.tx_o==1 && e.vif.event_o==0,"Reset idle TX/IRQ");
            e.cov.hit($sformatf("reset.frame_phase.%0d",k));
        end
        reset_dut(); configure(2);
        for(int k=0;k<16;k++) e.rx_bfm.send(uart_byte_t'(k));
        wr(4,1); reset_dut(); expect_reg(20,'h60); expect_reg(0,0); expect_reg(8,1);
        e.cov.hit("reset.fifo_full_irq");
        for(int phase=0;phase<2;phase++) begin
            @(negedge e.vif.CLK); e.vif.PSEL=1; e.vif.PENABLE=0; e.vif.PWRITE=1; e.vif.PADDR=12; e.vif.PWDATA='h83;
            if(phase==1) begin @(negedge e.vif.CLK); e.vif.PENABLE=1; end
            #1ns; e.vif.RSTN=0; e.vif.PSEL=0; e.vif.PENABLE=0;
            repeat(4) @(negedge e.vif.CLK);
            e.vif.RSTN=1; expect_reg(12,0); expect_reg(8,1);
            e.cov.hit($sformatf("reset.apb_phase.%0d",phase));
        end
        configure(2); e.rx_bfm.send('h3c); expect_reg(0,'h3c);
    endtask
    task snapshot_case();
        bit[31:0] value;
        reset_dut(); configure(3); wr(0,'h55); wr(0,'ha6);
        repeat(2*e.cfg.cycles()) @(negedge e.vif.CLK);
        wr(12,'h8b); wr(0,4); wr(4,0); wr(12,'h0f);
        e.cfg.divisor=4; e.cfg.parity_mode=1; e.cfg.stop_bits=2;
        wait_frames(3); expect_reg(20,'h60);
        check(e.sb.tx_checked==2,"Both frames survive mid-frame config update");
        e.cov.hit("config.tx_snapshot");
        reset_dut(); configure(3); wr(0,'h55); wr(0,'ha6); wr(0,'h5a);
        aligned_access(1,12,'h0f,value,1);
        e.cfg.parity_mode=1; e.cfg.stop_bits=2;
        wait_frames(4); expect_reg(20,'h60); e.cov.hit("config.tx_same_edge");
        reset_dut(); configure(3); wr(0,'h55); wr(0,'ha6);
        repeat(e.cfg.cycles()) @(negedge e.vif.CLK);
        wr(12,'h83); wr(0,0); wr(4,0); wr(12,3); wr(0,'hff,1);
        wait_frames(2);
        check(e.sb.tx_queue.size()==1,"D=0 preserves queued uart_byte_t");
        wr(12,'h83); wr(0,3); wr(4,0); wr(12,3); wait_frames(2);
        expect_reg(20,'h60); e.cov.hit("config.divisor_zero_pause");
        reset_dut(); configure(3,8,2,2);
        fork
            e.rx_bfm.send('ha6);
            begin
                repeat(4*e.cfg.cycles()) @(negedge e.vif.CLK);
                wr(12,3);
            end
        join
        expect_reg(0,'ha6); expect_reg(20,'h60); e.cov.hit("config.rx_snapshot");
        reset_dut(); configure(3,8,2,2);
        fork e.rx_bfm.send('h96); aligned_access(1,12,3,value,0,1); join
        expect_reg(0,'h96); expect_reg(20,'h60); e.cov.hit("config.rx_same_edge");
        reset_dut(); configure(3);
        fork
            e.rx_bfm.send('h5a);
            begin repeat(3*e.cfg.cycles()) @(negedge e.vif.CLK); wr(12,'h83); wr(0,0); wr(4,0); wr(12,3); end
        join
        expect_reg(0,'h5a); e.rx_bfm.send('ha6); expect_reg(0,0); expect_reg(20,'h60);
        wr(12,'h83); wr(0,3); wr(4,0); wr(12,3); repeat(e.cfg.cycles()+8) @(negedge e.vif.CLK);
        e.rx_bfm.send('h3c); expect_reg(0,'h3c); e.cov.hit("config.rx_disable_active_rearm");
    endtask
    task baud_case();
        int divisors[4]='{1,27,326,65535};
        foreach(divisors[k]) begin
            reset_dut(); configure(divisors[k],5,0,1); wr(0,'h15);
            repeat(8*e.cfg.cycles()+8) @(negedge e.vif.CLK);
            expect_reg(20,'h60); e.cov.hit($sformatf("baud.divisor.%0d",divisors[k]));
        end
        reset_dut(); wr(0,'h55,1); expect_reg(20,'h60);
        e.cov.hit("baud.divisor.0"); check(e.sb.tx_checked==4,"Every baud sweep frame decoded");
    endtask
    task random_case();
        apb_tx tr;
        bit[31:0] value;
        int n,p,s,d;
        uart_byte_t data;
        bit bad;
        for(int k=0;k<300;k++) begin
            tr=apb_tx::type_id::create("random_register");
            if(!tr.randomize() with {addr inside {12'h004,12'h00c,12'h003,12'h02c,12'h014,12'h038};})
                `uvm_fatal("RANDOMIZE","APB constraints failed")
            transfer(tr.write,tr.addr,tr.data,value,
                !(tr.addr inside {12'h004,12'h00c,12'h014}) || (tr.write && tr.addr==12'h014));
        end
        for(int k=0;k<64;k++) begin
            if(!std::randomize(n,p,s,d,data,bad) with {n inside {[5:8]}; p inside {[0:2]}; s inside {[1:2]}; d inside {1,2,3,27};})
                `uvm_fatal("RANDOMIZE","UART constraints failed")
            reset_dut(); configure(d,n,p,s);
            fork
                e.rx_bfm.send(data,bad);
                wr(0,~data & 255);
            join
            wait_frames(2); rd(20,value); expect_reg(0,data&(255>>(8-n))); expect_reg(20,'h60);
        end
        e.cov.hit("random.register_300"); e.cov.hit("random.full_duplex_64");
        check(e.sb.tx_checked==64 && e.sb.rx_checked==64,"Random full-duplex completion counts");
    endtask
    task false_start_case();
        reset_dut(); configure(8);
        @(negedge e.vif.CLK); e.vif.rx_i=0;
        repeat(2*8) @(negedge e.vif.CLK); e.vif.rx_i=1;
        repeat(3*e.cfg.cycles()) @(negedge e.vif.CLK);
        expect_reg(20,'h60); expect_reg(0,0); e.cov.hit("rx.false_start");
        e.rx_bfm.send('h55); expect_reg(0,'h55); expect_reg(20,'h60);
        e.cov.hit("rx.rearm_after_false_start");
        e.rx_bfm.send('h55,0,0,1.0,1,0,0); expect_reg(20,'h61); expect_reg(0,'h55);
        e.cov.hit("rx.majority_single_sample_noise");
    endtask
    // Internal pulses align stimulus only; expected APB/data/error values remain independent.
    task aligned_access(bit write,bit[11:0] addr,bit[31:0] data,output bit[31:0] result,input bit align_tx=0,input bit align_rx_start=0);
        @(negedge e.vif.CLK); e.vif.PSEL=1; e.vif.PENABLE=0; e.vif.PWRITE=write; e.vif.PADDR=addr; e.vif.PWDATA=data;
        if(align_tx) wait(e.vif.tx_ready_probe);
        else if(align_rx_start) wait(e.vif.rx_start_probe); else wait(e.vif.rx_done_probe);
        @(negedge e.vif.CLK); e.vif.PENABLE=1;
        @(posedge e.vif.CLK); result=e.vif.PRDATA;
        check(e.vif.PSLVERR==0,"Simultaneous valid transfer unexpectedly rejected");
        @(negedge e.vif.CLK); e.vif.PSEL=0; e.vif.PENABLE=0; e.vif.PWRITE=0;
    endtask
    // APB completion is placed by the SPEC timeline, never by rx_done_probe.
    task rx_rearm_boundary_case();
        for(int clocks=31;clocks<=32;clocks++) begin
            reset_dut(); configure(2);
            @(negedge e.vif.CLK); e.vif.rx_i=0;
            repeat(12*32) @(negedge e.vif.CLK);
            expect_reg(20,'hf9); expect_reg(0,0); expect_reg(20,'h60);
            // Break recovery requires 32 consecutive synchronized high samples.
            @(negedge e.vif.CLK); e.vif.rx_i=1;
            repeat(clocks) @(negedge e.vif.CLK);
            e.rx_bfm.send(0);
            expect_reg(20,clocks==32 ? 'h61:'h60);
            expect_reg(0,0); expect_reg(20,'h60);
            e.rx_bfm.send('h3c); expect_reg(0,'h3c);
            e.cov.hit($sformatf("rx.rearm_high_clocks.%0d",clocks));
        end
    endtask
    task rx_divisor_snapshot_case();
        bit[31:0] ignored;
        for(int high_byte=0;high_byte<2;high_byte++) begin
            reset_dut(); configure(3); wr(12,'h83);
            fork
                e.rx_bfm.send('ha5);
                aligned_access(1,high_byte ? 4:0,high_byte ? 1:5,ignored,0,1);
            join
            wr(12,3); expect_reg(0,'ha5); expect_reg(20,'h60);
            e.cov.hit($sformatf("config.rx_divisor_start.%0d",high_byte));
        end
    endtask
    task rx_visibility_case();
        bit[31:0] value;
        int d;
        for(int di=0;di<2;di++) begin
            d=di==0 ? 1:27;
            for(int regsel=0;regsel<2;regsel++) for(int delta=-1;delta<=1;delta++) begin
                reset_dut(); configure(d);
                fork
                    e.rx_bfm.send('ha5);
                    begin
                        repeat(153*d+3+delta) @(negedge e.vif.CLK);
                        e.vif.PSEL=1; e.vif.PENABLE=0; e.vif.PWRITE=0;
                        e.vif.PADDR=regsel==0 ? 20:0;
                        @(negedge e.vif.CLK); e.vif.PENABLE=1;
                        @(posedge e.vif.CLK); value=e.vif.PRDATA;
                        check(value==(regsel==0 ? (delta>0 ? 'h61:'h60):(delta>0 ? 'ha5:0)),
                              "RX visibility before/at/after SPEC enqueue");
                        @(negedge e.vif.CLK); e.vif.PSEL=0; e.vif.PENABLE=0;
                    end
                join
                if(regsel==0 || delta<=0) expect_reg(0,'ha5);
                expect_reg(20,'h60);
                e.cov.hit($sformatf("rx.visibility.%0d.%0d.%0d",d,regsel,delta));
            end
        end
    endtask
    task concurrency_case();
        bit[31:0] result;
        reset_dut(); configure(3);
        fork e.rx_bfm.send('h9c); aligned_access(0,0,0,result); join
        check(result==0,"Empty+arrival read must not bypass"); expect_reg(0,'h9c);
        e.cov.hit("concurrency.empty_pop_push");
        for(int k=0;k<16;k++) e.rx_bfm.send(uart_byte_t'(k));
        fork e.rx_bfm.send('ha5); aligned_access(0,0,0,result); join
        check(result==0,"Full pop must return the original head"); expect_reg(20,'h61);
        for(int k=1;k<16;k++) expect_reg(0,k);
        expect_reg(0,'ha5); e.cov.hit("concurrency.full_pop_push");
        for(int k=0;k<17;k++) e.rx_bfm.send(uart_byte_t'(k));
        fork e.rx_bfm.send('hbb); aligned_access(0,20,0,result); join
        check(result=='h63,"LSR snapshot must contain old OE"); expect_reg(20,'h63); expect_reg(20,'h61);
        for(int k=0;k<16;k++) expect_reg(0,k);
        e.cov.hit("concurrency.oe_set_over_clear");
        reset_dut(); configure(3,8,2,1);
        fork e.rx_bfm.send('ha5,1); aligned_access(0,20,0,result); join
        check(result=='h60,"LSR at arrival samples empty pre-state"); expect_reg(20,'he5); expect_reg(0,'ha5);
        e.cov.hit("concurrency.lsr_no_ack_new_head");
        e.rx_bfm.send('h11);
        fork e.rx_bfm.send('h22,0,0,1.0,1,0); aligned_access(1,8,3,result); join
        expect_reg(20,'h60); expect_reg(0,0); e.cov.hit("concurrency.flush_drops_completion");
        reset_dut(); configure(27);
        for(int k=0;k<17;k++) wr(0,k);
        aligned_access(1,0,'haa,result,1);
        wait_frames(20); expect_reg(20,'h60); e.cov.hit("concurrency.tx_full_pop_write");
        reset_dut(); configure(3); wr(0,'h55);
        aligned_access(1,0,'haa,result,1);
        wait_frames(3); expect_reg(20,'h60); e.cov.hit("concurrency.tx_empty_arrival_no_bypass");
    endtask
    task run_phase(uvm_phase phase);
        phase.raise_objection(this);
        wait(e.vif.RSTN); repeat(2) @(negedge e.vif.CLK);
        case(test_id)
            1:reg_case(); 2:tx_case(); 3:rx_case(); 4:tolerance_case(); 5:error_case();
            6:fifo_case(); 7:irq_case(); 8:reset_case(); 9:begin snapshot_case(); rx_divisor_snapshot_case(); end
            10:baud_case(); 11:random_case(); 12:begin false_start_case(); rx_rearm_boundary_case(); end 13:begin concurrency_case(); rx_visibility_case(); end
            default:`uvm_fatal("CASE","No test selected")
        endcase
        repeat(4) @(negedge e.vif.CLK);
        $display("TEST_COMPLETED|%s|checks=%0d|apb=%0d",get_type_name(),explicit_checks,e.mon.completed);
        phase.drop_objection(this);
    endtask
endclass

class target_apb_test extends target_base_test;
    `uvm_component_utils(target_apb_test)
    function new(string name,uvm_component parent); super.new(name,parent); test_id=1; endfunction
endclass

class target_tx_modes_test extends target_base_test;
    `uvm_component_utils(target_tx_modes_test)
    function new(string name,uvm_component parent); super.new(name,parent); test_id=2; endfunction
endclass

class target_rx_modes_test extends target_base_test;
    `uvm_component_utils(target_rx_modes_test)
    function new(string name,uvm_component parent); super.new(name,parent); test_id=3; endfunction
endclass

class target_tolerance_test extends target_base_test;
    `uvm_component_utils(target_tolerance_test)
    function new(string name,uvm_component parent); super.new(name,parent); test_id=4; endfunction
endclass

class target_errors_test extends target_base_test;
    `uvm_component_utils(target_errors_test)
    function new(string name,uvm_component parent); super.new(name,parent); test_id=5; endfunction
endclass

class target_fifo_test extends target_base_test;
    `uvm_component_utils(target_fifo_test)
    function new(string name,uvm_component parent); super.new(name,parent); test_id=6; endfunction
endclass

class target_irq_test extends target_base_test;
    `uvm_component_utils(target_irq_test)
    function new(string name,uvm_component parent); super.new(name,parent); test_id=7; endfunction
endclass

class target_reset_test extends target_base_test;
    `uvm_component_utils(target_reset_test)
    function new(string name,uvm_component parent); super.new(name,parent); test_id=8; endfunction
endclass

class target_snapshot_test extends target_base_test;
    `uvm_component_utils(target_snapshot_test)
    function new(string name,uvm_component parent); super.new(name,parent); test_id=9; endfunction
endclass

class target_baud_test extends target_base_test;
    `uvm_component_utils(target_baud_test)
    function new(string name,uvm_component parent); super.new(name,parent); test_id=10; endfunction
endclass

class target_random_test extends target_base_test;
    `uvm_component_utils(target_random_test)
    function new(string name,uvm_component parent); super.new(name,parent); test_id=11; endfunction
endclass

class target_false_start_test extends target_base_test;
    `uvm_component_utils(target_false_start_test)
    function new(string name,uvm_component parent); super.new(name,parent); test_id=12; endfunction
endclass

class target_concurrency_test extends target_base_test;
    `uvm_component_utils(target_concurrency_test)
    function new(string name,uvm_component parent); super.new(name,parent); test_id=13; endfunction
endclass
