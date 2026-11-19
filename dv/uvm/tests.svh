class apb_agent extends uvm_agent;
    `uvm_component_utils(apb_agent)
    uvm_sequencer #(bus_item) seqr;
    bus_driver drv;
    bus_monitor mon;
    function new(string name, uvm_component parent); super.new(name,parent); endfunction
    function void build_phase(uvm_phase phase);
        seqr=new("seqr",this);
        drv=bus_driver::type_id::create("driver",this);
        mon=bus_monitor::type_id::create("monitor",this);
    endfunction
    function void connect_phase(uvm_phase phase);
        drv.seq_item_port.connect(seqr.seq_item_export);
    endfunction
endclass

class uart_env extends uvm_env;
    `uvm_component_utils(uart_env)
    virtual uart_if vif;
    apb_agent apb;
    frame_mode mode;
    serial_driver peer;
    serial_monitor tx, rx;
    uart_scoreboard sb;
    function new(string name, uvm_component parent); super.new(name,parent); endfunction
    function void build_phase(uvm_phase phase);
        if (!uvm_config_db#(virtual uart_if)::get(this,"","vif",vif)) `uvm_fatal("CONFIG","Missing uart_if")
        apb=apb_agent::type_id::create("apb",this);
        mode=new("peer_mode");
        peer=serial_driver::type_id::create("peer",this);
        tx=serial_monitor::type_id::create("tx",this);
        rx=serial_monitor::type_id::create("rx",this);
        sb=uart_scoreboard::type_id::create("sb",this);
    endfunction
    function void connect_phase(uvm_phase phase);
        apb.drv.vif=vif; apb.mon.vif=vif;
        tx.vif=vif; rx.vif=vif; peer.vif=vif;
        tx.mode=mode; rx.mode=mode; peer.mode=mode;
        tx.is_tx=1;
        apb.mon.observed.connect(sb.bus_in);
        tx.observed.connect(sb.wire_in);
        rx.observed.connect(sb.wire_in);
    endfunction
endclass

class traffic_pattern extends uvm_sequence_item;
    `uvm_object_utils(traffic_pattern)
    rand bit [3:0] width, gap;
    rand bit [1:0] stops, reserved_mode;
    rand bit parity, tx_dir;
    rand bit [7:0] data;
    rand bit [8:0] bank;
    constraint legal {
        width inside {[5:8]}; stops inside {1,2}; gap inside {[0:7]};
        bank inside {0,1,9'h15,9'h1ff};
    }
    function new(string name="pattern"); super.new(name); endfunction
endclass

class pulp_uart_test extends uvm_test;
    `uvm_component_utils(pulp_uart_test)
    uart_env e;
    string scenario;
    int unsigned seed;
    function new(string name, uvm_component parent); super.new(name,parent); endfunction
    function void build_phase(uvm_phase phase);
        e=uart_env::type_id::create("env",this);
        if (!$value$plusargs("CASE=%s",scenario)) scenario="baud";
        if (!$value$plusargs("SEED=%d",seed)) seed=17;
    endfunction
    task clocks(int n); repeat (n) @(negedge e.vif.clk); endtask
    task reset_uart();
        clocks(1);
        e.vif.rst_n=0;
        e.sb.reset_model();
        clocks(6); e.vif.rst_n=1; clocks(3);
        void'(e.sb.compare("RESET_TX_IDLE",e.vif.tx,1));
        void'(e.sb.compare("RESET_IRQ",e.vif.irq,0));
    endtask
    task transfer(bus_item item);
        bus_seq seq=new("access");
        seq.item=item;
        seq.start(e.apb.seqr);
    endtask
    task wr(bit [11:0] addr, bit [31:0] data);
        bus_item t=new("write");
        t.wr=1; t.addr=addr; t.data=data; transfer(t);
    endtask
    task rd(bit [11:0] addr, output logic [31:0] data);
        bus_item t=new("read");
        t.addr=addr; transfer(t); data=t.rdata;
    endtask
    task rd_check(bit [11:0] addr, logic [31:0] want, logic [31:0] mask='1);
        logic [31:0] data;
        rd(addr,data);
        void'(e.sb.compare("APB_VALUE",data & mask,want));
        $display("READ|addr=%03h|value=%08h|mask=%08h|want=%08h",addr,data,mask,want);
    endtask
    task irq_check(string label_name, bit [7:0] want, bit irq);
        bus_item t=new("iir_sample");
        bit code_ok, pin_ok;
        t.addr=2; transfer(t);
        code_ok=e.sb.compare("IIR_CODE",t.rdata,want);
        pin_ok=e.sb.compare("EVENT",t.irq,irq);
        $display("IRQ|case=%s|iir=%02h|event=%0d",label_name,t.rdata[7:0],t.irq);
        if (code_ok && pin_ok) e.sb.hit("irq",label_name);
    endtask
    task configure(int div, int width=8, bit parity=0, int stops=1, bit [1:0] reserved_mode=0);
        bit [7:0] lcr=8'(width-5) | (8'(stops-1)<<2) | (8'(parity)<<3) | (8'(reserved_mode)<<4);
        wr(3,lcr|8'h80); wr(0,div & 'hff); wr(1,(div>>8) & 'hff); wr(3,lcr);
        e.mode.cycles=div+1; e.mode.width=width; e.mode.parity=parity; e.mode.stops=stops;
    endtask
    task send_rx(bit [7:0] data, bit bad_parity=0, bit bad_stop=0);
        e.sb.expect_wire(data,e.mode.width,bad_parity,bad_stop);
        e.peer.send(data,bad_parity,bad_stop);
    endtask
    task pop_rx(bit [11:0] addr=0);
        logic [31:0] data;
        rd(addr,data); // Passive RBR scoreboard compares this bus completion to decoded rx_i.
    endtask
    task setup_probe(bit [11:0] addr, bit is_write, bit select_pin);
        clocks(1);
        e.vif.addr=addr; e.vif.wdata=32'hdeadbeef;
        e.vif.wr=is_write; e.vif.sel=select_pin; e.vif.enable=0;
        clocks(1); e.vif.sel=0; e.vif.wr=0; clocks(1);
    endtask
    task registers_case();
        logic [31:0] data;
        rd_check(3,0); rd_check(1,0); rd_check(5,'h60); irq_check("disabled",'hc1,0);
        wr(3,'h80); rd_check(0,0); rd_check(1,0);
        configure(31);
        send_rx(8'h62);
        setup_probe(3,1,0); setup_probe(3,1,1); setup_probe(0,0,1);
        rd_check(3,'h03); rd_check(5,1,1);
        wr(1,32'h123456a0); rd_check(1,'ha0);
        wr(1,32'hfedcbaa0); rd_check(1,'ha0); irq_check("disabled",'hc1,0);
        wr('h00b,'h83);
        for (int i=0; i<8; i++) begin
            case (i)
                0: data='h1f;
                1,2: data=0;
                3: data='h83;
                default: data='h7d;
            endcase
            wr(12'h288+i,32'h5a000000 | data);
            rd(i,data);
        end
        rd_check('h008,'h1f); rd_check('h009,0); rd_check('h00b,'h83);
        rd_check('h00c,0); rd_check('h014,0);
        void'(e.sb.compare("DLAB_SUPPRESSES_THR",e.sb.tx_starts.size(),0));
        wr(3,'h03); rd_check(1,'ha0); rd_check(5,1,1);
        for (int i=0; i<8; i++) begin
            case (i)
                0: data='h41;
                1: data='ha0;
                2: data=0;
                3: data=3;
                default: data='h6e;
            endcase
            wr(i,32'hface0000 | data);
            rd(12'hff8+i,data);
        end
        clocks(12*32);
        rd_check(5,'h60);
        void'(e.sb.compare("BANK_TX_COUNT",e.sb.tx_frames,1));
        void'(e.sb.compare("BANK_RBR_COUNT",e.sb.rx_reads,1));
        // Consecutive write/read with PSEL continuously high and no IDLE cycle.
        clocks(1); e.vif.sel=1; e.vif.enable=0; e.vif.wr=1;
        e.vif.addr=3; e.vif.wdata='h0b;
        clocks(1); e.vif.enable=1;
        clocks(1); e.vif.enable=0; e.vif.wr=0;
        clocks(1); e.vif.enable=1;
        @(posedge e.vif.clk);
        void'(e.sb.compare("BACK_TO_BACK",e.vif.rdata,'h0b));
        clocks(1); e.vif.enable=0; e.vif.sel=0;
        configure(31,8,1);
        for (int bits_654=0; bits_654<8; bits_654++) begin
            data='h0b | (bits_654<<4);
            wr(3,data); rd_check(3,data);
            void'(e.sb.compare("NO_TX_BREAK",e.vif.tx,1));
            wr(0,'h41); wr(0,'h01); // Even parity symbols 0 then 1.
            clocks(24*32);
            e.sb.hit("lcr",$sformatf("bits654_%0d",bits_654));
        end
        void'(e.sb.compare("LCR_TX_COUNT",e.sb.tx_frames,17));
    endtask
    task measure_55(int div);
        time edge_time, previous;
        int delta;
        @(negedge e.vif.tx);
        previous=$time;
        $display("EDGE|div=%0d|i=0|ns=%0d|level=0|clocks=0",div,previous);
        for (int i=1; i<=9; i++) begin
            @(e.vif.tx);
            edge_time=$time;
            delta=int'((edge_time-previous)/20ns);
            void'(e.sb.compare("EDGE_LEVEL",e.vif.tx,i%2));
            void'(e.sb.compare("EDGE_PERIOD_NS",edge_time-previous,(div+1+int'(i==1))*20));
            $display("EDGE|div=%0d|i=%0d|ns=%0d|level=%b|clocks=%0d",div,i,edge_time,e.vif.tx,delta);
            previous=edge_time;
        end
    endtask
    task baud_case();
        int div;
        for (int pass=0; pass<3; pass++) begin
            div=(pass==2)?27:433;
            configure(div,8,(pass==1),1,(pass==1)?3:0);
            e.peer.nominal_115200=(div==433);
            if (pass!=1) fork
                begin measure_55(div); end
                begin wr(0,'h55); end
                begin send_rx(8'h96); end
            join
            else fork
                begin wr(0,'hd3); end
                begin send_rx(8'h97); end
            join
            rd_check(5,'h61); pop_rx(); rd_check(5,'h60);
        end
        void'(e.sb.compare("BAUD_TX_COUNT",e.sb.tx_frames,3));
        void'(e.sb.compare("BAUD_RX_COUNT",e.sb.rx_reads,3));
    endtask
    task modes_case();
        int first, symbols, div;
        time spacing;
        for (int width=5; width<=8; width++)
            for (int p=0; p<2; p++)
                for (int stops=1; stops<=2; stops++) begin
                    div=(width==8 && p==0)?433:31;
                    configure(div,width,bit'(p),stops,2'(width-5));
                    first=e.sb.tx_starts.size();
                    fork
                        begin wr(0,'h41); wr(0,'ha6); end
                        begin send_rx(8'hd2 ^ 8'(width)); send_rx('h79); end
                    join
                    pop_rx(); pop_rx();
                    void'(e.sb.compare("MODE_STARTS",e.sb.tx_starts.size()-first,2));
                    symbols=1+width+p+stops;
                    if (e.sb.tx_starts.size()>=first+2) begin
                        spacing=e.sb.tx_starts[first+1]-e.sb.tx_starts[first];
                        void'(e.sb.compare("QUEUED_FRAME_NS",spacing,(symbols*(div+1)+2)*20));
                        $display("SPACING|bits=%0d|parity=%0d|stops=%0d|div=%0d|clocks=%0d",width,p,stops,div,spacing/20ns);
                    end
                end
        void'(e.sb.compare("MATRIX_TX",e.sb.tx_frames,32));
        void'(e.sb.compare("MATRIX_RBR",e.sb.rx_reads,32));
    endtask
    task fifo_case();
        int first;
        configure(31);
        for (int en=0; en<2; en++) begin
            wr(2,'h38|en);
            send_rx('h37); send_rx('hb1);
            rd_check(5,'h61); pop_rx(); rd_check(5,'h61); pop_rx(); rd_check(5,'h60);
            e.sb.hit("fifo",$sformatf("bit0_%0d",en));
        end
        send_rx('h81); send_rx('h82); rd_check(5,'h61);
        wr(0,'h71); wr(0,'h72); wr(2,'h02); clocks(3); rd_check(5,0,'h61);
        clocks(23*32); rd_check(5,'h60);
        void'(e.sb.compare("RX_CLEAR_LEAVES_TX",e.sb.tx_frames,2));
        send_rx('h21); pop_rx(); rd_check(5,'h60); e.sb.hit("fifo","rx_clear");
        first=e.sb.rx_reads;
        for (int i=0; i<18; i++) send_rx(8'h40+8'(i));
        for (int i=0; i<17; i++) begin rd_check(5,'h61); pop_rx(); end
        clocks(3*32); rd_check(5,'h60);
        void'(e.sb.compare("RX_RETAINED",e.sb.rx_reads-first,17));
        void'(e.sb.compare("RX_EXCESS",e.sb.rx_drop,1));
        e.sb.hit("fifo","rx_17_of_18");
        first=e.sb.tx_frames;
        for (int i=0; i<18; i++) wr(0,'h80+i);
        rd_check(5,0,'h60);
        clocks(18*11*32);
        rd_check(5,'h60);
        void'(e.sb.compare("TX_RETAINED",e.sb.tx_frames-first,17));
        void'(e.sb.compare("TX_EXCESS",e.sb.tx_drop,1));
        e.sb.hit("fifo","tx_17_of_18");
        first=e.sb.tx_frames;
        send_rx('h7e);
        wr(0,'hac); wr(0,'hde); wr(0,'had);
        rd_check(5,0,'h60); wr(2,'h04); clocks(3); rd_check(5,'h20,'h60);
        clocks(3*11*32); rd_check(5,'h61); pop_rx(); rd_check(5,'h60);
        void'(e.sb.compare("TX_CLEAR_SURVIVOR",e.sb.tx_frames-first,1));
        e.sb.hit("fifo","tx_clear_inflight");
        for (int en=0; en<2; en++) begin
            send_rx('h91); send_rx('h92);
            first=e.sb.tx_frames;
            wr(0,'h73); wr(0,'h74); rd_check(5,1,'h61);
            wr(2,6|en); clocks(3); rd_check(5,'h20);
            clocks(23*32); rd_check(5,'h60);
            void'(e.sb.compare("BOTH_CLEAR",e.sb.tx_frames-first,1));
            e.sb.hit("fifo",$sformatf("both_clear_%0d",6|en));
        end
    endtask
    task errors_case();
        logic [31:0] lsr;
        bit bad_parity, bad_stop;
        configure(31,8,1); wr(1,4);
        for (int i=0; i<4; i++) send_rx(8'h31+8'(i),bit'(i),bit'(i>>1));
        for (int i=0; i<4; i++) begin
            bad_parity=bit'(i); bad_stop=bit'(i>>1);
            rd(5,lsr);
            void'(e.sb.compare("HEAD_LSR",lsr,'h61));
            irq_check("line_status_silent",'hc1,0);
            pop_rx();
            e.sb.hit("fault",$sformatf("pe%0d_stop%0d",bad_parity,bad_stop));
            $display("FAULT|index=%0d|inverted_parity=%0d|low_stop=%0d|head_lsr=%02h",
                     i,bad_parity,bad_stop,lsr[7:0]);
        end
        rd_check(5,'h60);
    endtask
    task irq_case();
        configure(31); rd_check(5,'h60); irq_check("disabled",'hc1,0);
        wr(1,1); clocks(3); rd_check(5,'h60); irq_check("rda_empty",'hc8,1);
        send_rx('h39); rd_check(5,'h61); irq_check("rda_with_rx",'hc8,1);
        wr(1,0); pop_rx(); clocks(3); irq_check("clear_code_zero",'hc0,1);
        reset_uart(); wr(1,2); clocks(3); irq_check("thre_empty",'hc4,1);
        irq_check("thre_empty",'hc4,1);
        wr(1,0); clocks(3); irq_check("masked_first",'hc4,1); irq_check("masked_second",'hc0,1);
        reset_uart(); wr(1,3); clocks(3); irq_check("rda_over_thre",'hc8,1);
        wr(1,0); wr(3,'h80); rd_check(0,0); rd_check(1,0); rd_check(3,'h80);
        wr(3,0); rd_check(1,0); irq_check("unrelated_reads",'hc8,1);
        e.sb.permit_empty_rbr=1; pop_rx(); irq_check("empty_rbr_ack",'hc0,1);
        reset_uart(); configure(31); send_rx('hd8); wr(1,1); clocks(3);
        wr(1,0); rd_check(5,'h61); irq_check("lsr_ack",'hc0,1); pop_rx(); rd_check(5,'h60);
    endtask
    task thresholds_case();
        int levels[4]='{1,4,8,14};
        bus_item t;
        int occupancy;
        for (int k=0; k<4; k++)
            for (int offset=-1; offset<=1; offset++) begin
                reset_uart(); configure(31); wr(2,k<<6);
                occupancy=levels[k]+offset;
                for (int i=0; i<occupancy; i++) send_rx(8'h61+8'(i));
                // With IER still zero, queue two TX words to hold LSR[5] low.
                wr(0,'h35); wr(0,'h4a); rd_check(5,(occupancy!=0),'h61);
                wr(1,1); clocks(3);
                t=new("threshold_iir"); t.addr=2; transfer(t);
                void'(e.sb.compare("THRESHOLD_IIR",t.rdata,offset==0?'hc8:'hc1));
                void'(e.sb.compare("THRESHOLD_PIN",t.irq,offset==0));
                $display("THRESHOLD|level=%0d|rx_count=%0d|iir=%02h|event=%0d",levels[k],occupancy,t.rdata[7:0],t.irq);
                e.sb.hit("trigger",$sformatf("%0d_%0d",levels[k],occupancy));
                wr(1,0);
                for (int i=0; i<occupancy; i++) pop_rx();
                clocks(23*32); rd_check(5,'h60);
                void'(e.sb.compare("POINT_TX_DRAIN",e.sb.tx_queue.size()+int'(e.sb.tx_busy),0));
            end
    endtask
    task random_case();
        traffic_pattern p=new("pattern");
        bus_item reg_op=new("random_register");
        int tx_count, rx_count;
        logic [31:0] data;
        p.srandom(seed);
        reg_op.srandom(seed ^ 32'h41b5);
        for (int i=0; i<48; i++) begin
            if (!reg_op.randomize() with { addr[2:0] inside {1,3,4,6,7}; addr[11:3] inside {0,1,9'h15}; })
                `uvm_fatal("RAND_REG","Register constraints unsatisfied")
            $display("STIM|reg|%0d|%03h|%0d|%08h",i,reg_op.addr,reg_op.wr,reg_op.data);
            transfer(reg_op);
        end
        for (int i=0; i<32; i++) begin
            if (!p.randomize()) `uvm_fatal("RAND_FRAME","Frame constraints unsatisfied")
            $display("STIM|frame|%0d|%0d|%0d|%0d|%0d|%02h|%03h|%0d|%0d",i,p.tx_dir,p.width,p.parity,p.stops,p.data,p.bank,p.gap,p.reserved_mode);
            configure(31,p.width,p.parity,p.stops,p.reserved_mode);
            clocks(p.gap);
            if (p.tx_dir) begin
                tx_count++; wr({p.bank,3'b0},32'h125a0000|p.data); clocks(14*32);
            end else begin
                rx_count++; send_rx(p.data); rd_check(5,1,1); rd({p.bank,3'b0},data);
            end
        end
        void'(e.sb.compare("RANDOM_TX",e.sb.tx_frames,tx_count));
        void'(e.sb.compare("RANDOM_RBR",e.sb.rx_reads,rx_count));
        void'(e.sb.compare("BOTH_DIRECTIONS",tx_count>0 && rx_count>0,1));
    endtask
    task run_phase(uvm_phase phase);
        phase.raise_objection(this);
        reset_uart();
        case (scenario)
            "registers": registers_case();
            "baud": baud_case();
            "modes": modes_case();
            "fifo": fifo_case();
            "errors": errors_case();
            "irq": irq_case();
            "thresholds": thresholds_case();
            "random": random_case();
            default: `uvm_fatal("UNKNOWN_CASE",scenario)
        endcase
        $display("DONE|case=%s|seed=%0d|setups=%0d|accesses=%0d|gated=%0d",
                 scenario,seed,e.apb.mon.setups,e.apb.mon.accesses,e.apb.mon.gated_cycles);
        phase.drop_objection(this);
    endtask
endclass
