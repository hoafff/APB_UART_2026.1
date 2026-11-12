class apb_sequencer extends uvm_sequencer #(apb_tx);
    `uvm_component_utils(apb_sequencer)
    function new(string name,uvm_component parent); super.new(name,parent); endfunction
endclass

class apb_driver extends uvm_driver #(apb_tx);
    `uvm_component_utils(apb_driver)
    virtual uart_apb_if vif;
    function new(string name,uvm_component parent); super.new(name,parent); endfunction
    function void build_phase(uvm_phase phase);
        super.build_phase(phase);
        if(!uvm_config_db#(virtual uart_apb_if)::get(this,"","vif",vif)) `uvm_fatal("VIF","Missing APB vif")
    endfunction
    task run_phase(uvm_phase phase);
        apb_tx tr;
        forever begin
            seq_item_port.get_next_item(tr);
            wait(vif.RSTN);
            @(negedge vif.CLK);
            vif.PSEL=1; vif.PENABLE=0; vif.PADDR=tr.addr; vif.PWRITE=tr.write; vif.PWDATA=tr.data;
            @(negedge vif.CLK); vif.PENABLE=1;
            @(posedge vif.CLK);
            if(vif.PREADY!==1) `uvm_fatal("APB_READY","SPEC forbids wait states")
            tr.rdata=vif.PRDATA; tr.slverr=vif.PSLVERR;
            if(tr.slverr!==tr.expected_error) `uvm_error("APB_ERROR",$sformatf("addr=%03h wr=%0b err=%0b expected=%0b",tr.addr,tr.write,tr.slverr,tr.expected_error))
            @(negedge vif.CLK);
            vif.PSEL=0; vif.PENABLE=0; vif.PWRITE=0; vif.PADDR=0; vif.PWDATA=0;
            seq_item_port.item_done();
        end
    endtask
endclass

class apb_monitor extends uvm_component;
    `uvm_component_utils(apb_monitor)
    virtual uart_apb_if vif;
    uvm_analysis_port #(apb_tx) ap;
    bit setup;
    bit [11:0] addr;
    bit [31:0] data;
    bit wr;
    int completed;
    function new(string name,uvm_component parent); super.new(name,parent); ap=new("ap",this); endfunction
    function void build_phase(uvm_phase phase);
        super.build_phase(phase);
        if(!uvm_config_db#(virtual uart_apb_if)::get(this,"","vif",vif)) `uvm_fatal("VIF","Missing monitor vif")
    endfunction
    task run_phase(uvm_phase phase);
        apb_tx tr;
        forever begin
            @(posedge vif.CLK);
            if(!vif.RSTN) setup=0;
            else if(vif.PSEL && !vif.PENABLE) begin
                setup=1; addr=vif.PADDR; data=vif.PWDATA; wr=vif.PWRITE;
            end else if(vif.PSEL && vif.PENABLE) begin
                if(!setup || addr!==vif.PADDR || wr!==vif.PWRITE || (wr && data!==vif.PWDATA))
                    `uvm_error("APB_PROTOCOL","Missing SETUP or changed APB controls")
                if(vif.PREADY) begin
                    tr=apb_tx::type_id::create("observed");
                    tr.addr=vif.PADDR; tr.data=vif.PWDATA; tr.write=vif.PWRITE;
                    tr.rdata=vif.PRDATA; tr.slverr=vif.PSLVERR;
                    ap.write(tr); completed++; setup=0;
                end
            end else setup=0;
        end
    endtask
endclass

class apb_single_seq extends uvm_sequence #(apb_tx);
    `uvm_object_utils(apb_single_seq)
    apb_tx tr;
    function new(string name="apb_single_seq"); super.new(name); endfunction
    task body(); start_item(tr); finish_item(tr); endtask
endclass
