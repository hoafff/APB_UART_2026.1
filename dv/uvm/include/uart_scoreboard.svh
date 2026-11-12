class uart_scoreboard extends uvm_component;
    `uvm_component_utils(uart_scoreboard)
    uvm_analysis_imp_apb #(apb_tx,uart_scoreboard) apb_imp;
    uvm_analysis_imp_tx_start #(uart_frame,uart_scoreboard) tx_start_imp;
    uvm_analysis_imp_tx #(uart_frame,uart_scoreboard) tx_imp;
    uvm_analysis_imp_rx #(uart_frame,uart_scoreboard) rx_imp;
    virtual uart_apb_if vif;
    coverage_ledger cov;
    uart_byte_t tx_queue[$],inflight[$];
    uart_frame rx_queue[$];
    uart_byte_t lcr,ier,dll,dlm;
    bit fifo_on,oe,tx_pending;
    int trigger_code;
    int checks,tx_checked,rx_checked,rx_dropped,reset_epoch;
    time last_thr_accept,last_rx_clear;
    function new(string name,uvm_component parent); super.new(name,parent); endfunction
    function void build_phase(uvm_phase phase);
        super.build_phase(phase);
        apb_imp=new("apb_imp",this); tx_start_imp=new("tx_start_imp",this);
        tx_imp=new("tx_imp",this); rx_imp=new("rx_imp",this);
        if(!uvm_config_db#(virtual uart_apb_if)::get(this,"","vif",vif)) `uvm_fatal("VIF","SB vif missing")
        if(!uvm_config_db#(coverage_ledger)::get(this,"","cov",cov)) `uvm_fatal("COV","ledger missing")
    endfunction
    function void reset_model();
        tx_queue.delete(); inflight.delete(); rx_queue.delete(); reset_epoch++;
        lcr=0; ier=0; dll=0; dlm=0; fifo_on=0; oe=0; tx_pending=0; trigger_code=0;
        cov.hit("reset.observed");
    endfunction
    task run_phase(uvm_phase phase);
        forever begin @(negedge vif.RSTN); reset_model(); end
    endtask
    function int threshold();
        if(!fifo_on) return 1;
        case(trigger_code) 0:return 1; 1:return 4; 2:return 8; default:return 14; endcase
    endfunction
    function uart_byte_t lsr_value();
        uart_byte_t v;
        v=0;
        v[0]=rx_queue.size()!=0; v[1]=oe;
        if(rx_queue.size()!=0) v[4:2]=rx_queue[0].errors;
        v[5]=tx_queue.size()==0; v[6]=(tx_queue.size()==0 && inflight.size()==0);
        foreach(rx_queue[k]) v[7]|=(rx_queue[k].errors!=0);
        return v;
    endfunction
    function uart_byte_t iir_value();
        uart_byte_t code;
        if(ier[2] && (oe || (rx_queue.size()!=0 && rx_queue[0].errors!=0))) code=6;
        else if(ier[0] && rx_queue.size()>=threshold()) code=4;
        else if(ier[1] && tx_pending) code=2;
        else code=1;
        return code|(fifo_on ? 8'hc0:8'h00);
    endfunction
    function void compare(string label,bit[31:0] actual,bit[31:0] expected);
        checks++;
        if(actual!==expected) `uvm_error("SCOREBOARD",$sformatf("%s actual=%08h expected=%08h",label,actual,expected))
    endfunction
    function void write_apb(apb_tx t);
        uart_byte_t expected,discard;
        bit valid_address,dlab_before;
        uart_frame popped;
        valid_address=t.addr inside {12'h000,12'h004,12'h008,12'h00c,12'h014};
        dlab_before=lcr[7];
        cov.hit($sformatf("apb.%03h.%0b.%0b.%0b",t.addr,t.write,dlab_before,t.slverr));
        if(!valid_address || (t.write && t.addr==12'h014)) begin
            compare("invalid PSLVERR",t.slverr,1); compare("invalid PRDATA",t.rdata,0); return;
        end
        if(t.slverr) begin
            // FIFO full/D=0 are checked by the directed oracle at the request.
            if(!(t.write && t.addr==0 && !lcr[7])) `uvm_error("UNEXPECTED_ERROR","Mapped register error")
            compare("error data",t.rdata,0); return;
        end
        if(t.write) begin
            compare("write PRDATA",t.rdata,0);
            case(t.addr)
                0: if(lcr[7]) dll=t.data[7:0]; else begin tx_queue.push_back(t.data[7:0]); last_thr_accept=$time; tx_pending=0; end
                4: if(lcr[7]) dlm=t.data[7:0]; else begin
                    if(!ier[1] && t.data[1] && tx_queue.size()==0) tx_pending=1;
                    ier=t.data[7:0]&7;
                end
                8: begin
                    if(t.data[1] || t.data[0]!=fifo_on) begin rx_queue.delete(); oe=0; last_rx_clear=$time; end
                    if(t.data[2] || t.data[0]!=fifo_on) begin
                        if(tx_queue.size()!=0) tx_pending=1;
                        tx_queue.delete();
                    end
                    fifo_on=t.data[0]; trigger_code=int'(t.data[7:6]);
                end
                12: lcr=t.data[7:0]&8'h9f;
                default: ;
            endcase
        end else begin
            expected=0;
            case(t.addr)
                0: if(lcr[7]) expected=dll;
                   else if(rx_queue.size()!=0) begin
                       popped=rx_queue.pop_front(); expected=popped.data; rx_checked++;
                       cov.hit($sformatf("rx.occupancy.%0d",rx_queue.size()));
                   end
                4: expected=lcr[7] ? dlm:ier;
                8: begin expected=iir_value(); if(expected[3:0]==2) tx_pending=0; end
                12: expected=lcr;
                20: begin
                    expected=lsr_value(); oe=0;
                    if(rx_queue.size()!=0) rx_queue[0].errors=0;
                end
                default: ;
            endcase
            compare($sformatf("read %03h",t.addr),t.rdata,{24'b0,expected});
        end
    endfunction
    function void write_tx_start(uart_frame f);
        uart_byte_t data;
        if(tx_queue.size()==0) begin `uvm_error("TX_SPURIOUS","Start without accepted THR") return; end
        data=tx_queue.pop_front(); inflight.push_back(data);
        if(tx_queue.size()==0) tx_pending=1;
    endfunction
    function void write_tx(uart_frame f);
        uart_byte_t expected;
        if(inflight.size()==0) begin `uvm_error("TX_SPURIOUS","Frame without start") return; end
        expected=inflight.pop_front(); expected &= uart_byte_t'(255>>(8-f.data_bits));
        compare("TX decoded data",{24'b0,f.data},{24'b0,expected});
        if(!f.wire_ok) `uvm_error("TX_FORMAT","Wrong bit duration/parity/stop on serial wire")
        tx_checked++; cov.frame(1,f);
        if(tx_queue.size() > (last_thr_accept==$time ? 1:0) && {dlm,dll}!=0)
            compare("back-to-back next start",vif.tx_o,0);
    endfunction
    function void write_rx(uart_frame f);
        if(last_rx_clear==$time) begin cov.hit("rx.flush_drops_completion"); return; end
        if(rx_queue.size()>=(fifo_on ? 16:1)) begin oe=1; rx_dropped++; cov.hit("rx.drop_new"); end
        else rx_queue.push_back(f);
        cov.frame(0,f);
        cov.hit($sformatf("rx.error.%0d",f.errors));
        cov.hit($sformatf("rx.occupancy.%0d",rx_queue.size()));
    endfunction
    function void check_phase(uvm_phase phase);
        super.check_phase(phase);
        if(tx_queue.size()!=0 || inflight.size()!=0 || rx_queue.size()!=0)
            `uvm_error("PENDING",$sformatf("Unconsumed TX=%0d active=%0d RX=%0d",tx_queue.size(),inflight.size(),rx_queue.size()))
        if(checks==0) `uvm_error("VACUOUS","No scoreboard comparisons")
        $display("SB_RESULT|checks=%0d|tx=%0d|rx=%0d|dropped=%0d",checks,tx_checked,rx_checked,rx_dropped);
        cov.dump();
    endfunction
endclass

class apb_uart_env extends uvm_env;
    `uvm_component_utils(apb_uart_env)
    virtual uart_apb_if vif;
    uart_cfg cfg;
    coverage_ledger cov;
    apb_sequencer seqr;
    apb_driver drv;
    apb_monitor mon;
    uart_rx_bfm rx_bfm;
    uart_rx_observer rx_mon;
    uart_tx_monitor tx_mon;
    uart_scoreboard sb;
    function new(string name,uvm_component parent); super.new(name,parent); endfunction
    function void build_phase(uvm_phase phase);
        super.build_phase(phase);
        if(!uvm_config_db#(virtual uart_apb_if)::get(this,"","vif",vif)) `uvm_fatal("VIF","Env vif missing")
        cfg=uart_cfg::type_id::create("cfg"); cov=coverage_ledger::type_id::create("cov");
        uvm_config_db#(uart_cfg)::set(this,"*","cfg",cfg);
        uvm_config_db#(coverage_ledger)::set(this,"*","cov",cov);
        seqr=apb_sequencer::type_id::create("seqr",this);
        drv=apb_driver::type_id::create("drv",this); mon=apb_monitor::type_id::create("mon",this);
        rx_bfm=uart_rx_bfm::type_id::create("rx_bfm",this); tx_mon=uart_tx_monitor::type_id::create("tx_mon",this);
        rx_mon=uart_rx_observer::type_id::create("rx_mon",this);
        sb=uart_scoreboard::type_id::create("sb",this);
    endfunction
    function void connect_phase(uvm_phase phase);
        super.connect_phase(phase);
        drv.seq_item_port.connect(seqr.seq_item_export); mon.ap.connect(sb.apb_imp);
        rx_mon.ap.connect(sb.rx_imp); tx_mon.start_ap.connect(sb.tx_start_imp); tx_mon.ap.connect(sb.tx_imp);
    endfunction
endclass
