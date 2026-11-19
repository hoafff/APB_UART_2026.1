class uart_scoreboard extends uvm_scoreboard;
    `uvm_component_utils(uart_scoreboard)
    uvm_analysis_imp_bus #(bus_item,uart_scoreboard) bus_in;
    uvm_analysis_imp_wire #(frame_observation,uart_scoreboard) wire_in;
    logic [7:0] lcr, ier, dll, dlm, active_tx;
    logic [7:0] tx_queue[$];
    frame_observation rx_intent[$], rx_queue[$];
    time tx_starts[$];
    bit tx_busy, invert_tx, invert_rbr, permit_empty_rbr;
    int unsigned checks, tx_frames, rx_wire, rx_reads, tx_drop, rx_drop;
    int unsigned bins_hit[string];

    covergroup apb_cg with function sample(bit wr, bit [2:0] off, bit page);
        option.per_instance=1;
        rw: coverpoint wr;
        reg_off: coverpoint off { bins offsets[]={[0:7]}; }
        bank: coverpoint page;
        access_cross: cross rw, reg_off, bank;
    endgroup
    covergroup serial_cg with function sample(bit is_tx, int width, bit parity, int stops);
        option.per_instance=1;
        dir: coverpoint is_tx;
        bits_per_word: coverpoint width { bins sizes[]={[5:8]}; }
        parity_enable: coverpoint parity;
        stop_symbols: coverpoint stops { bins count[]={[1:2]}; }
        frame_cross: cross dir, bits_per_word, parity_enable, stop_symbols;
    endgroup
    function new(string name, uvm_component parent);
        super.new(name,parent);
        bus_in=new("bus_in",this); wire_in=new("wire_in",this);
        apb_cg=new(); serial_cg=new();
        invert_tx=$test$plusargs("NEG_TX");
        invert_rbr=$test$plusargs("NEG_RBR");
    endfunction
    function void reset_model();
        lcr=0; ier=0; dll=0; dlm=0;
        tx_busy=0; tx_queue.delete(); rx_intent.delete(); rx_queue.delete();
    endfunction
    function void hit(string group_name, string bin_name);
        string key={group_name,"|",bin_name};
        bins_hit[key]++;
    endfunction
    function bit compare(string id, logic [31:0] got, logic [31:0] want);
        checks++;
        if (got !== want) begin
            `uvm_error(id,$sformatf("observed=%08h expected=%08h",got,want))
            return 0;
        end
        return 1;
    endfunction
    function void cover_frame(frame_observation f);
        serial_cg.sample(f.is_tx,f.width,f.parity,f.stops);
        hit("serial",$sformatf("%s_%0d_%0d_%0d",f.is_tx?"TX":"RX",f.width,f.parity,f.stops));
    endfunction
    function void expect_wire(bit [7:0] data, int width, bit bad_parity, bit bad_stop);
        frame_observation f=new("intent");
        f.data=data & (8'hff >> (8-width));
        f.bad_parity=bad_parity; f.bad_stop=bad_stop;
        rx_intent.push_back(f);
    endfunction
    function void write_wire(frame_observation f);
        frame_observation wanted;
        logic [7:0] expected;
        bit good_data, good_parity, good_stop;
        if (f.start_only) begin
            if (f.is_tx) begin
                tx_starts.push_back(f.started);
                if (tx_busy || !tx_queue.size()) `uvm_error("TX_START","No waiting THR at start")
                else active_tx=tx_queue.pop_front();
                tx_busy=1;
            end
            return;
        end
        if (f.is_tx) begin
            tx_frames++;
            expected=active_tx & (8'hff >> (8-f.width));
            if (invert_tx) begin
                expected^=8'h01; invert_tx=0;
                $display("INJECT|TX_DATA|wire=%02h|perturbed_expected=%02h",f.data,expected);
            end
            good_data=compare("TX_DATA",f.data,expected);
            good_parity=compare("TX_PARITY",f.bad_parity,0);
            good_stop=compare("TX_STOP",f.bad_stop,0);
            if (good_data && good_parity && good_stop) cover_frame(f);
            tx_busy=0;
        end else begin
            rx_wire++;
            if (!rx_intent.size()) begin
                `uvm_error("RX_WIRE_EXTRA","RX pin frame without requested stimulus")
                return;
            end
            wanted=rx_intent.pop_front();
            void'(compare("RX_WIRE_DATA",f.data,wanted.data));
            void'(compare("RX_WIRE_PARITY",f.bad_parity,wanted.bad_parity));
            void'(compare("RX_WIRE_STOP",f.bad_stop,wanted.bad_stop));
            // In the quiescent overflow experiment: 16 queued + 1 stalled word.
            // Reads/clears are deliberately outside incoming frames.
            if (rx_queue.size()<17) rx_queue.push_back(f);
            else rx_drop++;
        end
        $display("WIRE|%s|ns=%0t|data=%02h|bits=%0d|parity=%0d|pin=%b|stops=%0d|bad_pe=%0d|bad_stop=%0d",
                 f.is_tx?"TX":"RX",f.started,f.data,f.width,f.parity,f.parity_pin,f.stops,f.bad_parity,f.bad_stop);
    endfunction
    function void write_bus(bus_item t);
        bit [2:0] off=t.addr[2:0];
        string rw=t.wr?"W":"R";
        frame_observation f;
        logic [7:0] expected;
        apb_cg.sample(t.wr,off,lcr[7]);
        hit("apb",$sformatf("%s_%0d_%0d",rw,off,lcr[7]));
        hit("alias",$sformatf("%s_%0d",rw,(t.addr[11:3]!=0)));
        if (t.wr) begin
            case (off)
                0: if (lcr[7]) dll=t.data[7:0];
                   else if (tx_queue.size()<16) tx_queue.push_back(t.data[7:0]);
                   else tx_drop++;
                1: if (lcr[7]) dlm=t.data[7:0]; else ier=t.data[7:0];
                2: begin
                    if (t.data[1]) rx_queue.delete();
                    if (t.data[2]) tx_queue.delete(); // A frame already on tx_o survives.
                end
                3: lcr=t.data[7:0];
                default: ;
            endcase
        end else begin
            void'(compare("UPPER_READ",t.rdata[31:8],0));
            case (off)
                0: if (lcr[7]) void'(compare("DLL",t.rdata,dll));
                   else if (rx_queue.size()) begin
                       f=rx_queue.pop_front();
                       expected=f.data;
                       if (invert_rbr) begin
                           expected^=8'h01; invert_rbr=0;
                           $display("INJECT|RBR_DATA|wire=%02h|perturbed_expected=%02h",f.data,expected);
                       end
                       rx_reads++;
                       if (compare("RBR_DATA",t.rdata,expected) && !f.bad_parity && !f.bad_stop) cover_frame(f);
                       $display("RBR|addr=%03h|wire=%02h|read=%02h|bad_pe=%0d|bad_stop=%0d",
                                t.addr,f.data,t.rdata[7:0],f.bad_parity,f.bad_stop);
                   end else if (permit_empty_rbr) begin
                       permit_empty_rbr=0;
                       $display("EMPTY_RBR|value=%02h",t.rdata[7:0]); // Value is unqualified.
                   end else `uvm_error("RBR_EMPTY","Unscheduled empty RBR read")
                1: void'(compare("IER_DLM",t.rdata,lcr[7]?dlm:ier));
                2: begin
                    void'(compare("IIR_HIGH",t.rdata[7:4],4'hc));
                    void'(compare("IRQ_PIN",t.irq,!t.rdata[0]));
                end
                3: void'(compare("LCR",t.rdata,lcr));
                4,6,7: void'(compare("UNMAPPED",t.rdata,0));
                5: begin
                    void'(compare("DR",t.rdata[0],rx_queue.size()!=0));
                    hit("lsr",$sformatf("dr_%0d",t.rdata[0]));
                    hit("lsr",$sformatf("tx_%02b",t.rdata[6:5]));
                end
            endcase
        end
    endfunction
    function void check_phase(uvm_phase phase);
        void'(compare("TX_REMAIN",tx_queue.size()+int'(tx_busy),0));
        void'(compare("RX_REMAIN",rx_queue.size()+rx_intent.size(),0));
        void'(compare("UNUSED_INJECTION",invert_tx||invert_rbr,0));
    endfunction
    function void report_phase(uvm_phase phase);
        foreach (bins_hit[k]) $display("COV|%s|%0d",k,bins_hit[k]);
        $display("SB|checks=%0d|tx=%0d|rx_wire=%0d|rbr=%0d|tx_drop=%0d|rx_drop=%0d",
                 checks,tx_frames,rx_wire,rx_reads,tx_drop,rx_drop);
    endfunction
endclass
