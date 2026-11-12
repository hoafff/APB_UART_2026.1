class uart_rx_bfm extends uvm_component;
    `uvm_component_utils(uart_rx_bfm)
    virtual uart_apb_if vif;
    uart_cfg cfg;
    uvm_analysis_port #(uart_frame) start_ap,ap;
    function new(string name,uvm_component parent); super.new(name,parent); ap=new("ap",this); start_ap=new("start_ap",this); endfunction
    function void build_phase(uvm_phase phase);
        super.build_phase(phase);
        if(!uvm_config_db#(virtual uart_apb_if)::get(this,"","vif",vif)) `uvm_fatal("VIF","RX vif missing")
        if(!uvm_config_db#(uart_cfg)::get(this,"","cfg",cfg)) `uvm_fatal("CFG","RX config missing")
    endfunction
    // Independent serial transmitter: real-time delays, no DUT counter/state access.
    task send(uart_byte_t data,bit bad_parity=0,bit[1:0] bad_stops=0,real rate=1.0,int idle_bits=1,bit is_break=0,bit discard_at_flush=0,int glitch_bit=-1);
        uart_frame f;
        real bit_ns;
        bit parity;
        f=uart_frame::type_id::create("peer_frame");
        f.data_bits=cfg.data_bits; f.parity_mode=cfg.parity_mode; f.stop_bits=cfg.stop_bits; f.divisor=cfg.divisor;
        f.data=data & uart_byte_t'(255>>(8-f.data_bits));
        bit_ns=real'(cfg.cycles())*20.0/rate;
        parity=^f.data;
        if(f.parity_mode==1) parity=~parity;
        start_ap.write(f);
        if(is_break) begin
            f.data=0; f.errors={1'b1,1'b1,(f.parity_mode==1)};
            vif.rx_i=0;
            #(bit_ns*(1+f.data_bits+(f.parity_mode!=0)+f.stop_bits+2));
            vif.rx_i=1;
        end else begin
            f.errors={1'b0,(|(bad_stops & (f.stop_bits==2 ? 2'b11:2'b01))),bad_parity && f.parity_mode!=0};
            vif.rx_i=0; #(bit_ns);
            for(int k=0;k<f.data_bits;k++) begin
                vif.rx_i=f.data[k];
                if(k==glitch_bit) begin
                    #(bit_ns/2-20.0); vif.rx_i=~f.data[k]; #40ns; vif.rx_i=f.data[k]; #(bit_ns/2-20.0);
                end else #(bit_ns);
            end
            if(f.parity_mode!=0) begin vif.rx_i=parity^bad_parity; #(bit_ns); end
            for(int k=0;k<f.stop_bits;k++) begin vif.rx_i=!bad_stops[k]; #(bit_ns); end
            vif.rx_i=1;
        end
        // FE/break completion follows end-of-frame plus CDC; do not pop early.
        if(f.errors[1]) #200ns;
        if(!discard_at_flush) ap.write(f);
        #(bit_ns*idle_bits);
    endtask
endclass

class uart_tx_monitor extends uvm_component;
    `uvm_component_utils(uart_tx_monitor)
    virtual uart_apb_if vif;
    uart_cfg cfg;
    uvm_analysis_port #(uart_frame) start_ap,ap;
    bit inject_corruption;
    function new(string name,uvm_component parent);
        super.new(name,parent); start_ap=new("start_ap",this); ap=new("ap",this);
    endfunction
    function void build_phase(uvm_phase phase);
        super.build_phase(phase);
        if(!uvm_config_db#(virtual uart_apb_if)::get(this,"","vif",vif)) `uvm_fatal("VIF","TX vif missing")
        if(!uvm_config_db#(uart_cfg)::get(this,"","cfg",cfg)) `uvm_fatal("CFG","TX config missing")
        inject_corruption=$test$plusargs("NEGATIVE_TX_DATA");
    endfunction
    task run_phase(uvm_phase phase);
        uart_frame f;
        bit level,parity,aborted;
        int total,bit_cycles;
        forever begin
            if(vif.tx_o!==0) @(negedge vif.tx_o);
            if(!vif.RSTN) continue;
            f=uart_frame::type_id::create("decoded");
            f.data_bits=cfg.data_bits; f.parity_mode=cfg.parity_mode; f.stop_bits=cfg.stop_bits; f.divisor=cfg.divisor;
            bit_cycles=cfg.cycles(); total=1+f.data_bits+(f.parity_mode!=0)+f.stop_bits;
            start_ap.write(f); aborted=0; parity=0;
            // Check every cycle of every bit, including both stop bits.
            for(int b=0;b<total;b++) begin
                for(int c=0;c<bit_cycles;c++) begin
                    @(negedge vif.CLK);
                    if(!vif.RSTN) begin aborted=1; break; end
                    if(c==0) level=vif.tx_o;
                    else if(vif.tx_o!==level) f.wire_ok=0;
                end
                if(aborted) break;
                if(b==0 && level!=0) f.wire_ok=0;
                else if(b>=1 && b<=f.data_bits) begin f.data[b-1]=level; parity^=level; end
                else if(f.parity_mode!=0 && b==f.data_bits+1) begin
                    if(level!=(f.parity_mode==2 ? parity:~parity)) f.wire_ok=0;
                end else if(b>f.data_bits && level!=1) f.wire_ok=0;
            end
            if(!aborted) begin
                @(posedge vif.CLK);
                #1ps; // Publish after the APB pre-NBA snapshot, then catch an immediate next start.
                if(inject_corruption) f.data^=8'h01;
                ap.write(f);
            end
        end
    endtask
endclass
