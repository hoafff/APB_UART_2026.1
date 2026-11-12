typedef bit [7:0] uart_byte_t;
class uart_cfg extends uvm_object;
    `uvm_object_utils(uart_cfg)
    int unsigned divisor=27, data_bits=8, parity_mode=0, stop_bits=1;
    function new(string name="uart_cfg"); super.new(name); endfunction
    function int cycles(); return 16*divisor; endfunction
    function uart_byte_t lcr(); return uart_byte_t'(data_bits-5) | (stop_bits==2 ? 8'h04:0) |
        (parity_mode!=0 ? 8'h08:0) | (parity_mode==2 ? 8'h10:0); endfunction
endclass

class apb_tx extends uvm_sequence_item;
    `uvm_object_utils(apb_tx)
    rand bit [11:0] addr;
    rand bit [31:0] data;
    rand bit write;
    bit [31:0] rdata;
    bit slverr, expected_error;
    function new(string name="apb_tx"); super.new(name); endfunction
endclass

class uart_frame extends uvm_sequence_item;
    `uvm_object_utils(uart_frame)
    bit [7:0] data;
    bit [2:0] errors;
    int unsigned data_bits, parity_mode, stop_bits, divisor;
    bit wire_ok=1;
    bit target_enabled;
    int reset_epoch;
    function new(string name="uart_frame"); super.new(name); endfunction
endclass

class coverage_ledger extends uvm_object;
    `uvm_object_utils(coverage_ledger)
    int counts[string];
    covergroup modes with function sample(bit direction, int bits, int parity_mode, int stops);
        option.per_instance=1;
        cp_direction: coverpoint direction {bins rx={0}; bins tx={1};}
        cp_bits: coverpoint bits {bins widths[]={[5:8]};}
        cp_parity: coverpoint parity_mode {bins none={0}; bins odd={1}; bins even={2};}
        cp_stops: coverpoint stops {bins one={1}; bins two={2};}
        format_cross: cross cp_direction,cp_bits,cp_parity,cp_stops;
    endgroup
    function new(string name="coverage_ledger"); super.new(name); modes=new(); endfunction
    function void hit(string key); counts[key]++; endfunction
    function void frame(bit direction, uart_frame f);
        modes.sample(direction,f.data_bits,f.parity_mode,f.stop_bits);
        hit($sformatf("mode.%s.%0d.%0d.%0d",direction ? "tx":"rx",f.data_bits,f.parity_mode,f.stop_bits));
    endfunction
    function void dump();
        foreach(counts[key]) $display("COV|%s|%0d",key,counts[key]);
    endfunction
endclass
