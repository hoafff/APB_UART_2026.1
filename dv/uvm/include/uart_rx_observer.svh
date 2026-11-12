// Passive SPEC 7.3 oracle. Uses only serial input, CLK/RSTN and accepted APB writes.
// Absolute sample deadlines intentionally avoid the DUT's timer/state/probes.
class uart_rx_observer extends uvm_component;
    `uvm_component_utils(uart_rx_observer)
    virtual uart_apb_if vif;
    uvm_analysis_port #(uart_frame) ap;
    uart_byte_t lcr,dll,dlm;
    bit [2:0] wire_history;
    bit previous,armed,active,all_low;
    int high_clocks,age,bit_number,votes,epoch;
    uart_frame frame,pending;
    function new(string name,uvm_component parent);
        super.new(name,parent); ap=new("ap",this);
    endfunction
    function void build_phase(uvm_phase phase);
        super.build_phase(phase);
        if(!uvm_config_db#(virtual uart_apb_if)::get(this,"","vif",vif)) `uvm_fatal("VIF","RX observer vif missing")
    endfunction
    function void reset_observer();
        lcr=0; dll=0; dlm=0; wire_history=3'b111; previous=1;
        armed=0; active=0; high_clocks=0; pending=null; epoch++;
    endfunction
    task run_phase(uvm_phase phase);
        bit level,majority;
        int d,total_bits,offset;
        uart_frame publish;
        reset_observer();
        forever begin
            @(posedge vif.CLK or negedge vif.RSTN);
            if(!vif.RSTN) begin reset_observer(); continue; end
            level=wire_history[2]; wire_history={wire_history[1:0],vif.rx_i};
            // The prior clock's completed frame becomes FIFO-visible this clock.
            publish=pending; pending=null;
            d=int'({dlm,dll});
            if(!active) begin
                if(d==0) begin armed=0; high_clocks=0; end
                else if(armed && previous && !level) begin
                    frame=uart_frame::type_id::create("wire_rx");
                    frame.data_bits=5+int'(lcr[1:0]); frame.stop_bits=1+int'(lcr[2]);
                    frame.parity_mode=lcr[3] ? (lcr[4] ? 2:1):0;
                    frame.divisor=d; frame.data=0; frame.errors=0;
                    frame.target_enabled=1; frame.reset_epoch=epoch;
                    active=1; armed=0; age=0; bit_number=0; votes=0; all_low=1; high_clocks=0;
                end else if(level) begin
                    high_clocks++; if(high_clocks>=16*d) armed=1;
                end else high_clocks=0;
            end else begin
                age++; all_low &= !level;
                total_bits=1+frame.data_bits+(frame.parity_mode!=0)+frame.stop_bits;
                offset=age-16*bit_number*frame.divisor;
                if(offset==7*frame.divisor || offset==8*frame.divisor) votes+=int'(level);
                if(offset==9*frame.divisor) begin
                    majority=(votes+int'(level)>=2); votes=0;
                    if(bit_number==0 && majority) begin active=0; high_clocks=0; armed=0; end
                    else if(bit_number>0 && bit_number<=frame.data_bits) frame.data[bit_number-1]=majority;
                    else if(frame.parity_mode!=0 && bit_number==frame.data_bits+1)
                        frame.errors[0]=(majority!=(frame.parity_mode==2 ? ^frame.data:~(^frame.data)));
                    else if(bit_number>frame.data_bits) frame.errors[1]|=!majority;
                    if(active && bit_number==total_bits-1 && !frame.errors[1]) begin
                        pending=frame; active=0; armed=1; high_clocks=0;
                    end
                    bit_number++;
                end
                if(active && age==16*total_bits*frame.divisor) begin
                    frame.errors[2]=all_low; pending=frame; active=0; armed=0; high_clocks=0;
                end
            end
            previous=level;
            // Snapshot above uses the pre-edge configuration, just like the contract.
            if(vif.PSEL && vif.PENABLE && vif.PREADY && !vif.PSLVERR && vif.PWRITE) begin
                case(vif.PADDR)
                    0: if(lcr[7]) dll=vif.PWDATA[7:0];
                    4: if(lcr[7]) dlm=vif.PWDATA[7:0];
                    12: lcr=vif.PWDATA[7:0]&8'h9f;
                    default: ;
                endcase
            end
            // APB monitor observes pre-edge FIFO/head; then process the new arrival.
            #1ps;
            if(vif.RSTN && publish!=null) ap.write(publish);
        end
    endtask
endclass
