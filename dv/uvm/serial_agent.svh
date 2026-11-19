class frame_mode extends uvm_object;
    `uvm_object_utils(frame_mode)
    int unsigned width=8, stops=1, cycles=434;
    bit parity;
    function new(string name="mode"); super.new(name); endfunction
endclass

class frame_observation extends uvm_sequence_item;
    `uvm_object_utils(frame_observation)
    bit is_tx, start_only, parity, bad_parity, bad_stop;
    int unsigned width, stops;
    logic [7:0] data;
    logic parity_pin;
    time started;
    function new(string name="frame"); super.new(name); endfunction
endclass

class serial_driver extends uvm_component;
    `uvm_component_utils(serial_driver)
    virtual uart_if vif;
    frame_mode mode;
    bit nominal_115200;
    function new(string name, uvm_component parent); super.new(name,parent); endfunction
    task symbol(bit value);
        vif.rx = value;
        if (nominal_115200) #(1s / 115200.0);
        else repeat (mode.cycles) @(negedge vif.clk);
    endtask
    task send(bit [7:0] data, bit bad_parity, bit bad_stop);
        bit parity_bit = 0;
        @(negedge vif.clk);
        symbol(0);
        for (int i=0; i<mode.width; i++) begin
            symbol(data[i]);
            parity_bit ^= data[i];
        end
        if (mode.parity) symbol(parity_bit ^ bad_parity);
        for (int i=0; i<mode.stops; i++) symbol(!(bad_stop && i==0));
        symbol(1); // Known idle between independently injected frames.
    endtask
endclass

// The two passive decoders sample package pins. Neither consumes driver items.
class serial_monitor extends uvm_monitor;
    `uvm_component_utils(serial_monitor)
    virtual uart_if vif;
    frame_mode mode;
    bit is_tx;
    uvm_analysis_port #(frame_observation) observed;
    function new(string name, uvm_component parent);
        super.new(name,parent);
        observed = new("observed",this);
    endfunction
    function logic pin_value();
        return is_tx ? vif.tx : vif.rx;
    endfunction
    task run_phase(uvm_phase phase);
        frame_observation f;
        int unsigned cycles;
        forever begin
            if (is_tx) @(negedge vif.tx); else @(negedge vif.rx);
            if (!vif.rst_n) continue;
            f = new("observed_frame");
            f.is_tx=is_tx; f.started=$time; f.width=mode.width; f.stops=mode.stops;
            f.parity=mode.parity; f.data='0; f.start_only=1;
            cycles=mode.cycles;
            observed.write(f);
            repeat (cycles/2) @(posedge vif.clk);
            if (pin_value() !== 1'b0) `uvm_error("WIRE_START","Start center was not low")
            for (int i=0; i<f.width; i++) begin
                repeat (cycles) @(posedge vif.clk);
                f.data[i]=pin_value();
            end
            if (f.parity) begin
                repeat (cycles) @(posedge vif.clk);
                f.parity_pin=pin_value();
                f.bad_parity=(f.parity_pin !== (^f.data));
            end
            for (int i=0; i<f.stops; i++) begin
                repeat (cycles) @(posedge vif.clk);
                if (pin_value() !== 1'b1) f.bad_stop=1;
            end
            f.start_only=0;
            observed.write(f);
        end
    endtask
endclass
