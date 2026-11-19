class bus_item extends uvm_sequence_item;
    `uvm_object_utils(bus_item)
    rand bit [11:0] addr;
    rand bit [31:0] data;
    rand bit wr;
    logic [31:0] rdata;
    logic irq;
    function new(string name="bus_item"); super.new(name); endfunction
endclass

class bus_seq extends uvm_sequence #(bus_item);
    `uvm_object_utils(bus_seq)
    bus_item item;
    function new(string name="bus_seq"); super.new(name); endfunction
    task body();
        start_item(item);
        finish_item(item);
    endtask
endclass

class bus_driver extends uvm_driver #(bus_item);
    `uvm_component_utils(bus_driver)
    virtual uart_if vif;
    function new(string name, uvm_component parent); super.new(name,parent); endfunction
    task run_phase(uvm_phase phase);
        bus_item t;
        forever begin
            seq_item_port.get_next_item(t);
            @(negedge vif.clk);
            vif.addr = t.addr;
            vif.wdata = t.data;
            vif.wr = t.wr;
            vif.sel = 1;
            vif.enable = 0;
            @(negedge vif.clk);
            vif.enable = 1;
            do @(posedge vif.clk); while (vif.ready !== 1'b1);
            t.rdata = vif.rdata; // Active edge before register/FIFO NBA updates.
            t.irq = vif.irq;
            @(negedge vif.clk);
            vif.sel = 0;
            vif.enable = 0;
            vif.wr = 0;
            seq_item_port.item_done();
        end
    endtask
endclass

class bus_monitor extends uvm_monitor;
    `uvm_component_utils(bus_monitor)
    virtual uart_if vif;
    uvm_analysis_port #(bus_item) observed;
    int unsigned setups, accesses, gated_cycles;
    function new(string name, uvm_component parent);
        super.new(name,parent);
        observed = new("observed",this);
    endfunction
    task run_phase(uvm_phase phase);
        bit have_setup;
        logic [11:0] addr;
        logic [31:0] wdata;
        logic wr;
        bus_item t;
        forever begin
            @(posedge vif.clk);
            if (!vif.rst_n) begin
                have_setup = 0;
                continue;
            end
            if ({vif.ready,vif.slverr} !== 2'b10)
                `uvm_error("APB_RESPONSE","Expected PREADY=1 and PSLVERR=0")
            if (!(vif.sel && vif.enable && !vif.wr)) begin
                gated_cycles++;
                if (vif.rdata !== 32'b0) `uvm_error("READ_GATE","PRDATA outside read ACCESS")
            end
            if (vif.sel && !vif.enable) begin
                setups++;
                have_setup = 1;
                addr = vif.addr; wdata = vif.wdata; wr = vif.wr;
            end else if (vif.sel && vif.enable) begin
                if (!have_setup || addr !== vif.addr || wr !== vif.wr || (wr && wdata !== vif.wdata))
                    `uvm_error("APB_PHASE","ACCESS lacks a matching stable SETUP")
                if (vif.ready) begin
                    accesses++;
                    t = new("sample");
                    t.addr=vif.addr; t.wr=vif.wr; t.data=vif.wdata;
                    t.rdata=vif.rdata; t.irq=vif.irq;
                    observed.write(t);
                    have_setup = 0;
                end
            end else have_setup = 0;
        end
    endtask
endclass
