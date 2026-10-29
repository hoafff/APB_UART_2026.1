`timescale 1ns/1ps
package apb_uart_uvm_pkg;
    import uvm_pkg::*;
    `include "uvm_macros.svh"

    `uvm_analysis_imp_decl(_apb)
    `uvm_analysis_imp_decl(_tx)
    `uvm_analysis_imp_decl(_rx)

    class uart_cfg extends uvm_object;
        `uvm_object_utils(uart_cfg)
        int unsigned bit_cycles = 434; // Candidate for DLL/DLM=0x01B1, NOT measured yet
        int unsigned data_bits = 8;
        int unsigned stop_bits = 1;
        bit parity_en = 0;
        function new(string name="uart_cfg"); super.new(name); endfunction
    endclass

    class apb_tx extends uvm_sequence_item;
        rand bit [11:0] addr;
        rand bit [31:0] data;
        rand bit write;
        bit [31:0] rdata;
        `uvm_object_utils_begin(apb_tx)
            `uvm_field_int(addr, UVM_ALL_ON)
            `uvm_field_int(data, UVM_ALL_ON)
            `uvm_field_int(write, UVM_ALL_ON)
            `uvm_field_int(rdata, UVM_ALL_ON)
        `uvm_object_utils_end
        function new(string name="apb_tx"); super.new(name); endfunction
    endclass

    class uart_frame extends uvm_sequence_item;
        bit [7:0] data;
        int unsigned data_bits = 8;
        int unsigned stop_bits = 1;
        bit parity_en;
        bit parity_good = 1;
        bit stop_good = 1;
        `uvm_object_utils_begin(uart_frame)
            `uvm_field_int(data, UVM_ALL_ON)
            `uvm_field_int(data_bits, UVM_ALL_ON)
            `uvm_field_int(stop_bits, UVM_ALL_ON)
            `uvm_field_int(parity_en, UVM_ALL_ON)
            `uvm_field_int(parity_good, UVM_ALL_ON)
            `uvm_field_int(stop_good, UVM_ALL_ON)
        `uvm_object_utils_end
        function new(string name="uart_frame"); super.new(name); endfunction
    endclass

    class apb_sequencer extends uvm_sequencer #(apb_tx);
        `uvm_component_utils(apb_sequencer)
        function new(string name, uvm_component parent); super.new(name,parent); endfunction
    endclass

    class apb_driver extends uvm_driver #(apb_tx);
        `uvm_component_utils(apb_driver)
        virtual uart_apb_if vif;
        function new(string name, uvm_component parent); super.new(name,parent); endfunction
        function void build_phase(uvm_phase phase);
            super.build_phase(phase);
            if (!uvm_config_db#(virtual uart_apb_if)::get(this,"","vif",vif))
                `uvm_fatal("NO_VIF","APB driver missing vif")
        endfunction
        task run_phase(uvm_phase phase);
            apb_tx tr;
            forever begin
                seq_item_port.get_next_item(tr);
                drive_one(tr);
                seq_item_port.item_done();
            end
        endtask
        task drive_one(apb_tx tr);
            while (!vif.RSTN) @(negedge vif.CLK);
            @(negedge vif.CLK);
            vif.PADDR   = tr.addr;
            vif.PWDATA  = tr.data;
            vif.PWRITE  = tr.write;
            vif.PSEL    = 1;
            vif.PENABLE = 0; // SETUP
            @(negedge vif.CLK);
            vif.PENABLE = 1; // ACCESS
            do begin
                @(posedge vif.CLK);
            end while (vif.PREADY !== 1'b1);
            if (!tr.write) tr.rdata = vif.PRDATA;
            if (vif.PSLVERR !== 1'b0) `uvm_error("APB_SLVERR","Unexpected PSLVERR")
            @(negedge vif.CLK);
            vif.PSEL = 0;
            vif.PENABLE = 0;
            vif.PWRITE = 0;
            vif.PADDR = '0;
            vif.PWDATA = '0;
        endtask
    endclass

    class apb_monitor extends uvm_component;
        `uvm_component_utils(apb_monitor)
        virtual uart_apb_if vif;
        uvm_analysis_port #(apb_tx) ap;
        bit saw_setup;
        bit [11:0] setup_addr;
        bit [31:0] setup_data;
        bit setup_write;
        function new(string name, uvm_component parent); super.new(name,parent); endfunction
        function void build_phase(uvm_phase phase);
            super.build_phase(phase);
            ap = new("ap",this);
            if (!uvm_config_db#(virtual uart_apb_if)::get(this,"","vif",vif))
                `uvm_fatal("NO_VIF","APB monitor missing vif")
        endfunction
        task run_phase(uvm_phase phase);
            apb_tx tr;
            forever begin
                @(posedge vif.CLK);
                if (!vif.RSTN) begin
                    saw_setup = 0;
                end else if (vif.PSEL && !vif.PENABLE) begin
                    setup_addr = vif.PADDR;
                    setup_data = vif.PWDATA;
                    setup_write = vif.PWRITE;
                    saw_setup = 1;
                end else if (vif.PSEL && vif.PENABLE) begin
                    if (!saw_setup) `uvm_error("APB_PROTOCOL","ACCESS without SETUP")
                    if (saw_setup &&
                        ((setup_addr !== vif.PADDR) ||
                         (setup_write !== vif.PWRITE) ||
                         (setup_write && setup_data !== vif.PWDATA)))
                        `uvm_error("APB_PROTOCOL","Address/control/data changed from SETUP")
                    if (vif.PREADY) begin
                        tr = apb_tx::type_id::create("observed");
                        tr.addr = vif.PADDR;
                        tr.data = vif.PWDATA;
                        tr.write = vif.PWRITE;
                        tr.rdata = vif.PRDATA; // sample BEFORE NBA side effects
                        ap.write(tr);
                        saw_setup = 0;
                    end
                end else begin
                    saw_setup = 0;
                end
            end
        endtask
    endclass

    class uart_rx_bfm extends uvm_component;
        `uvm_component_utils(uart_rx_bfm)
        virtual uart_apb_if vif;
        uart_cfg cfg;
        uvm_analysis_port #(uart_frame) sent_ap;
        function new(string name, uvm_component parent); super.new(name,parent); endfunction
        function void build_phase(uvm_phase phase);
            super.build_phase(phase);
            sent_ap = new("sent_ap",this);
            if (!uvm_config_db#(virtual uart_apb_if)::get(this,"","vif",vif))
                `uvm_fatal("NO_VIF","UART RX BFM missing vif")
            if (!uvm_config_db#(uart_cfg)::get(this,"","cfg",cfg))
                `uvm_fatal("NO_CFG","UART RX BFM missing cfg")
        endfunction

        // bit_cycles measured in FPGA clocks. Drive on negedge, hold exact cycles.
        task send_byte(bit [7:0] data, bit bad_parity=0);
            uart_frame frame;
            bit even_parity;
            frame = uart_frame::type_id::create("driven_rx");
            frame.data = data;
            frame.data_bits = cfg.data_bits;
            frame.stop_bits = cfg.stop_bits;
            frame.parity_en = cfg.parity_en;
            frame.parity_good = !bad_parity;
            even_parity = 0;
            @(negedge vif.CLK); vif.rx_i = 0;
            repeat (cfg.bit_cycles) @(negedge vif.CLK); // start bit
            for (int i=0; i<cfg.data_bits; i++) begin
                vif.rx_i = data[i];
                even_parity ^= data[i];
                repeat (cfg.bit_cycles) @(negedge vif.CLK);
            end
            if (cfg.parity_en) begin
                vif.rx_i = even_parity ^ bad_parity;
                repeat (cfg.bit_cycles) @(negedge vif.CLK);
            end
            for (int i=0; i<cfg.stop_bits; i++) begin
                vif.rx_i = 1;
                repeat (cfg.bit_cycles) @(negedge vif.CLK);
            end
            vif.rx_i = 1;
            repeat (cfg.bit_cycles) @(negedge vif.CLK); // idle gap
            sent_ap.write(frame);
        endtask
    endclass

    class uart_tx_monitor extends uvm_component;
        `uvm_component_utils(uart_tx_monitor)
        virtual uart_apb_if vif;
        uart_cfg cfg;
        uvm_analysis_port #(uart_frame) ap;
        function new(string name, uvm_component parent); super.new(name,parent); endfunction
        function void build_phase(uvm_phase phase);
            super.build_phase(phase);
            ap = new("ap",this);
            if (!uvm_config_db#(virtual uart_apb_if)::get(this,"","vif",vif))
                `uvm_fatal("NO_VIF","UART TX monitor missing vif")
            if (!uvm_config_db#(uart_cfg)::get(this,"","cfg",cfg))
                `uvm_fatal("NO_CFG","UART TX monitor missing cfg")
        endfunction
        task run_phase(uvm_phase phase);
            uart_frame frame;
            bit even_parity;
            time bit_ns;
            forever begin
                @(negedge vif.tx_o);
                if (!vif.RSTN) continue;
                bit_ns = cfg.bit_cycles * 20ns; // CLK=50MHz, candidate bit length
                #(bit_ns/2);
                if (vif.tx_o !== 1'b0) continue; // noise; start center
                frame = uart_frame::type_id::create("decoded_tx");
                frame.data = 0;
                frame.data_bits = cfg.data_bits;
                frame.stop_bits = cfg.stop_bits;
                frame.parity_en = cfg.parity_en;
                even_parity = 0;
                for (int i=0; i<cfg.data_bits; i++) begin
                    #(bit_ns);
                    frame.data[i] = vif.tx_o;
                    even_parity ^= vif.tx_o;
                end
                if (cfg.parity_en) begin
                    #(bit_ns);
                    frame.parity_good = (vif.tx_o === even_parity);
                end
                for (int i=0; i<cfg.stop_bits; i++) begin
                    #(bit_ns);
                    if (vif.tx_o !== 1'b1) frame.stop_good = 0;
                end
                ap.write(frame);
            end
        endtask
    endclass

    class apb_coverage extends uvm_subscriber #(apb_tx);
        `uvm_component_utils(apb_coverage)
        bit model_dlab;
        covergroup apb_cg with function sample(bit direction, bit [2:0] addr_low, bit dlab);
            option.per_instance = 1;
            cp_direction: coverpoint direction { bins read={0}; bins write={1}; }
            cp_address: coverpoint addr_low { bins each_addr[]={[0:7]}; }
            cp_dlab: coverpoint dlab { bins off={0}; bins on={1}; }
            cross cp_direction, cp_address, cp_dlab;
        endgroup
        function new(string name, uvm_component parent);
            super.new(name,parent);
            apb_cg = new();
        endfunction
        function void write(apb_tx t);
            apb_cg.sample(t.write,t.addr[2:0],model_dlab);
            if (t.write && (t.addr[2:0] == 3)) model_dlab = t.data[7];
        endfunction
    endclass

    class uart_scoreboard extends uvm_component;
        `uvm_component_utils(uart_scoreboard)
        uvm_analysis_imp_apb #(apb_tx, uart_scoreboard) apb_imp;
        uvm_analysis_imp_tx  #(uart_frame,uart_scoreboard) tx_imp;
        uvm_analysis_imp_rx  #(uart_frame,uart_scoreboard) rx_imp;
        virtual uart_apb_if vif;
        bit [7:0] expected_tx[$];
        bit [7:0] expected_rx[$];
        bit [7:0] lcr, ier, dll, dlm;
        int unsigned tx_checked = 0;
        int unsigned rx_checked = 0;
        covergroup uart_cg with function sample(bit is_tx, int unsigned bits, bit parity_mode, int unsigned stops, bit frame_ok);
            option.per_instance=1;
            cp_direction: coverpoint is_tx { bins rx={0}; bins tx={1}; }
            cp_data_bits: coverpoint bits { bins supported[]={[5:8]}; }
            cp_parity: coverpoint parity_mode { bins off={0}; bins on={1}; }
            cp_stop: coverpoint stops { bins one={1}; bins two={2}; }
            cp_frame: coverpoint frame_ok { bins good={1}; bins bad={0}; }
            cross cp_direction, cp_data_bits, cp_parity;
        endgroup

        function new(string name, uvm_component parent);
            super.new(name,parent);
            uart_cg=new();
        endfunction
        function void build_phase(uvm_phase phase);
            super.build_phase(phase);
            apb_imp=new("apb_imp",this);
            tx_imp=new("tx_imp",this);
            rx_imp=new("rx_imp",this);
            if (!uvm_config_db#(virtual uart_apb_if)::get(this,"","vif",vif))
                `uvm_fatal("NO_VIF","Scoreboard missing vif")
        endfunction
        function void write_apb(apb_tx t);
            bit [7:0] expected;
            int unsigned off;
            off = t.addr[2:0];
            if (t.write) begin
                case (off)
                    0: if (lcr[7]) dll=t.data[7:0];
                       else expected_tx.push_back(t.data[7:0]);
                    1: if (lcr[7]) dlm=t.data[7:0];
                       else ier=t.data[7:0];
                    2: begin // FCR write: RX clear (and TX clear if idle).
                        if (t.data[1]) expected_rx.delete();
                        // TX may already be in the shift register: do not
                        // blindly delete all pending TX frames here.
                    end
                    3: lcr=t.data[7:0];
                    default: ;
                endcase
            end else begin
                case (off)
                    0: begin
                        if (lcr[7]) begin
                            if (t.rdata !== {24'h0,dll})
                                `uvm_error("DLL_MISMATCH",`sformatf("read=%08h expected DLL=%02h",t.rdata,dll))
                        end else if (expected_rx.size() > 0) begin
                            expected = expected_rx.pop_front(); // read-side effect
                            rx_checked++;
                            if (t.rdata[7:0] !== expected)
                                `uvm_error("RBR_MISMATCH",`sformatf("RBR=%02h expected=%02h",t.rdata[7:0],expected))
                        end
                    end
                    1: begin
                        expected = lcr[7] ? dlm : ier;
                        if (t.rdata !== {24'h0,expected})
                            `uvm_error("REG_MISMATCH",`sformatf("offset1 read=%08h expected=%02h",t.rdata,expected))
                    end
                    2: begin
                        if (t.rdata[7:4] !== 4'hc)
                            `uvm_error("IIR_FMT",`sformatf("IIR upper nibble != C: %08h",t.rdata))
                    end
                    3: if (t.rdata !== {24'h0,lcr})
                           `uvm_error("LCR_MISMATCH",`sformatf("LCR=%08h expected=%02h",t.rdata,lcr))
                    4,6,7: if (t.rdata !== 32'h0)
                               `uvm_error("UNIMPL_REG",`sformatf("offset %0d read nonzero %08h",off,t.rdata))
                    5: if (expected_rx.size() > 0 && t.rdata[0] !== 1'b1)
                           `uvm_error("LSR_DR","RX pending but LSR[0]=0")
                    default: ;
                endcase
            end
        endfunction
        function void write_tx(uart_frame f);
            bit [7:0] expected;
            bit [7:0] mask;
            mask=(8'hff >> (8 - f.data_bits));
            tx_checked++;
            uart_cg.sample(1'b1,f.data_bits,f.parity_en,f.stop_bits,f.parity_good && f.stop_good);
            if (expected_tx.size()==0) begin
                `uvm_error("TX_UNEXPECTED","TX frame without matching THR write")
                return;
            end
            expected=expected_tx.pop_front();
            if ((f.data & mask) !== (expected & mask))
                `uvm_error("TX_DATA",`sformatf("TX=%02h expected=%02h",f.data,expected))
            if (!f.parity_good) `uvm_error("TX_PARITY","TX parity bit mismatch")
            if (!f.stop_good) `uvm_error("TX_STOP","TX stop bit mismatch")
            `uvm_info("TX_OK",`sformatf("decoded byte 0x%02h (%0d bits)",f.data,f.data_bits),UVM_LOW)
        endfunction
        function void write_rx(uart_frame f);
            bit [7:0] mask;
            mask=8'hff >> (8 - f.data_bits);
            expected_rx.push_back(f.data & mask);
            uart_cg.sample(1'b0,f.data_bits,f.parity_en,f.stop_bits,f.parity_good && f.stop_good);
        endfunction
        function void check_phase(uvm_phase phase);
            super.check_phase(phase);
            if (expected_tx.size()!=0)
                `uvm_error("TX_PENDING",`sformatf("%0d THR writes lack observed TX frames",expected_tx.size()))
            `uvm_info("SB_SUMMARY",`sformatf("TX verified=%0d, RX RBR verified=%0d, RX queue left=%0d",tx_checked,rx_checked,expected_rx.size()),UVM_NONE)
        endfunction
    endclass

    class apb_uart_env extends uvm_env;
        `uvm_component_utils(apb_uart_env)
        apb_sequencer seqr;
        apb_driver drv;
        apb_monitor mon;
        uart_rx_bfm rx_bfm;
        uart_tx_monitor tx_mon;
        uart_scoreboard sb;
        apb_coverage cov;
        uart_cfg cfg;
        virtual uart_apb_if vif;
        function new(string name, uvm_component parent); super.new(name,parent); endfunction
        function void build_phase(uvm_phase phase);
            super.build_phase(phase);
            if (!uvm_config_db#(virtual uart_apb_if)::get(this,"","vif",vif))
                `uvm_fatal("NO_VIF","Env missing vif")
            cfg=uart_cfg::type_id::create("cfg");
            uvm_config_db#(uart_cfg)::set(this,"*","cfg",cfg);
            seqr=apb_sequencer::type_id::create("seqr",this);
            drv=apb_driver::type_id::create("drv",this);
            mon=apb_monitor::type_id::create("mon",this);
            rx_bfm=uart_rx_bfm::type_id::create("rx_bfm",this);
            tx_mon=uart_tx_monitor::type_id::create("tx_mon",this);
            sb=uart_scoreboard::type_id::create("sb",this);
            cov=apb_coverage::type_id::create("cov",this);
        endfunction
        function void connect_phase(uvm_phase phase);
            super.connect_phase(phase);
            drv.seq_item_port.connect(seqr.seq_item_export);
            mon.ap.connect(sb.apb_imp);
            mon.ap.connect(cov.analysis_export);
            rx_bfm.sent_ap.connect(sb.rx_imp);
            tx_mon.ap.connect(sb.tx_imp);
        endfunction
    endclass

    class apb_single_seq extends uvm_sequence #(apb_tx);
        `uvm_object_utils(apb_single_seq)
        bit [11:0] addr;
        bit [31:0] data;
        bit write;
        bit [31:0] rdata;
        function new(string name="apb_single_seq"); super.new(name); endfunction
        task body();
            apb_tx tr=apb_tx::type_id::create("tr");
            start_item(tr);
            tr.addr=addr;
            tr.data=data;
            tr.write=write;
            finish_item(tr);
            rdata=tr.rdata;
        endtask
    endclass

    class apb_random_reg_seq extends uvm_sequence #(apb_tx);
        `uvm_object_utils(apb_random_reg_seq)
        int unsigned count=60;
        function new(string name="apb_random_reg_seq"); super.new(name); endfunction
        task body();
            apb_tx tr;
            repeat (count) begin
                tr=apb_tx::type_id::create("random_reg");
                start_item(tr);
                if (!tr.randomize() with {
                    addr inside {12'h001,12'h003,12'h004,12'h006,12'h007,12'h00B};
                }) `uvm_fatal("RAND_FAIL","Cannot randomize APB register transaction")
                finish_item(tr);
            end
        endtask
    endclass

    class apb_uart_base_test extends uvm_test;
        `uvm_component_utils(apb_uart_base_test)
        apb_uart_env e;
        function new(string name, uvm_component parent); super.new(name,parent); endfunction
        function void build_phase(uvm_phase phase);
            super.build_phase(phase);
            e=apb_uart_env::type_id::create("e",this);
        endfunction
        task write_reg(bit [11:0] addr, bit [31:0] data);
            apb_single_seq s=apb_single_seq::type_id::create("write_seq");
            s.addr=addr; s.data=data; s.write=1; s.start(e.seqr);
        endtask
        task read_reg(bit [11:0] addr, output bit [31:0] value);
            apb_single_seq s=apb_single_seq::type_id::create("read_seq");
            s.addr=addr; s.write=0; s.start(e.seqr);
            value=s.rdata;
        endtask
        task init_uart_8n1();
            // Divisor 0x01B1=433 (candidate); confirm true timing by waveform.
            write_reg(12'h003,32'h83); // DLAB=1, 8-bit
            write_reg(12'h000,32'hB1); // DLL=0xB1
            write_reg(12'h001,32'h01); // DLM=0x01
            write_reg(12'h003,32'h03); // DLAB=0, 8N1
            e.cfg.data_bits=8;
            e.cfg.parity_en=0;
            e.cfg.stop_bits=1;
            e.cfg.bit_cycles=434;
        endtask
    endclass

    class apb_reg_smoke_test extends apb_uart_base_test;
        `uvm_component_utils(apb_reg_smoke_test)
        function new(string name, uvm_component parent); super.new(name,parent); endfunction
        task run_phase(uvm_phase phase);
            bit [31:0] value;
            phase.raise_objection(this);
            wait(e.vif.RSTN);
            read_reg(12'h003,value);
            if (value !== 32'h0) `uvm_error("REG_SMOKE","LCR not zero after reset")
            read_reg(12'h002,value);
            if (value !== 32'hC1) `uvm_error("REG_SMOKE",`sformatf("IIR reset read expected C1, got %08h",value))
            init_uart_8n1();
            write_reg(12'h003,32'h83);
            read_reg(12'h000,value);
            if (value !== 32'hB1) `uvm_error("REG_SMOKE","DLL readback failed")
            read_reg(12'h001,value);
            if (value !== 32'h01) `uvm_error("REG_SMOKE","DLM readback failed")
            write_reg(12'h003,32'h03);
            read_reg(12'h003,value);
            if (value !== 32'h03) `uvm_error("REG_SMOKE","LCR readback failed")
            read_reg(12'h004,value);
            if (value !== 32'h0) `uvm_error("REG_SMOKE","Unimplemented register expected 0")
            phase.drop_objection(this);
        endtask
    endclass

    class uart_tx_8n1_test extends apb_uart_base_test;
        `uvm_component_utils(uart_tx_8n1_test)
        function new(string name, uvm_component parent); super.new(name,parent); endfunction
        task run_phase(uvm_phase phase);
            phase.raise_objection(this);
            wait(e.vif.RSTN);
            init_uart_8n1();
            write_reg(12'h000,32'h41); // 'A'
            repeat (12 * e.cfg.bit_cycles) @(posedge e.vif.CLK);
            if (e.sb.tx_checked != 1)
                `uvm_error("TX_MISSING",`sformatf("Expected 1 TX frame, saw %0d",e.sb.tx_checked))
            phase.drop_objection(this);
        endtask
    endclass

    class uart_rx_8n1_test extends apb_uart_base_test;
        `uvm_component_utils(uart_rx_8n1_test)
        function new(string name, uvm_component parent); super.new(name,parent); endfunction
        task run_phase(uvm_phase phase);
            bit [31:0] value;
            phase.raise_objection(this);
            wait(e.vif.RSTN);
            init_uart_8n1();
            e.rx_bfm.send_byte(8'h42);
            read_reg(12'h005,value);
            if (value[0] !== 1'b1) `uvm_error("RX_LSR","LSR[0] was not set")
            read_reg(12'h000,value);
            if (value[7:0] !== 8'h42) `uvm_error("RX_DATA",`sformatf("RBR=%02h expected 42",value[7:0]))
            read_reg(12'h005,value);
            if (value[0] !== 1'b0) `uvm_error("RX_LSR","LSR[0] remains set after pop")
            phase.drop_objection(this);
        endtask
    endclass

    class apb_random_regs_test extends apb_uart_base_test;
        `uvm_component_utils(apb_random_regs_test)
        function new(string name, uvm_component parent); super.new(name,parent); endfunction
        task run_phase(uvm_phase phase);
            apb_random_reg_seq r=apb_random_reg_seq::type_id::create("r");
            phase.raise_objection(this);
            wait(e.vif.RSTN);
            r.count=80;
            r.start(e.seqr); // constrained random legal APB only, no THR/RBR side effects
            phase.drop_objection(this);
        endtask
    endclass

    // The next two tests are deliberately XFAIL: a guide-compliance error is
    // expected on unmodified upstream RTL. Run separately from green smoke.
    class uart_rx_parity_gap_test extends apb_uart_base_test;
        `uvm_component_utils(uart_rx_parity_gap_test)
        function new(string name, uvm_component parent); super.new(name,parent); endfunction
        task run_phase(uvm_phase phase);
            bit [31:0] lsr, value;
            phase.raise_objection(this);
            wait(e.vif.RSTN);
            init_uart_8n1();
            write_reg(12'h003,32'h0B); // 8 bits + parity enabled
            e.cfg.parity_en=1;
            e.rx_bfm.send_byte(8'h41,1'b1); // intentionally wrong even parity
            read_reg(12'h005,lsr);
            read_reg(12'h000,value);
            if (lsr[2] === 1'b0)
                `uvm_error("KNOWN_GUIDE_GAP_DIF08","Expected RTL parity error gap: LSR[2] stays 0 (err_clr_i tied high)")
            else
                `uvm_error("DIF08_REVISIT","Observed PE=1; re-examine baseline / sampling")
            phase.drop_objection(this);
        endtask
    endclass

    class uart_irq_rda_gap_test extends apb_uart_base_test;
        `uvm_component_utils(uart_irq_rda_gap_test)
        function new(string name, uvm_component parent); super.new(name,parent); endfunction
        task run_phase(uvm_phase phase);
            bit [31:0] iir;
            phase.raise_objection(this);
            wait(e.vif.RSTN);
            write_reg(12'h001,32'h01); // IER[0]=1; TX FIFO empty / RX FIFO empty
            repeat (4) @(posedge e.vif.CLK);
            read_reg(12'h002,iir);
            if (iir[3:0] == 4'h8)
                `uvm_error("KNOWN_GUIDE_GAP_DIF07","RDA interrupt asserted while RX FIFO empty: RDA_i incorrectly uses LSR[5]")
            else
                `uvm_error("DIF07_REVISIT",`sformatf("Unexpected IIR=%02h, check waveform",iir[7:0]))
            phase.drop_objection(this);
        endtask
    endclass

    class apb_reg_alias_test extends apb_uart_base_test;
        `uvm_component_utils(apb_reg_alias_test)
        function new(string name, uvm_component parent); super.new(name,parent); endfunction
        task run_phase(uvm_phase phase);
            bit [31:0] value;
            phase.raise_objection(this);
            wait(e.vif.RSTN);
            write_reg(12'h003,32'h03);
            write_reg(12'h00B,32'h83); // same low 3 bits: aliases LCR
            read_reg(12'h003,value);
            if (value !== 32'h83) `uvm_error("APB_ALIAS","0x00B must alias 0x003")
            read_reg(12'h00B,value);
            if (value !== 32'h83) `uvm_error("APB_ALIAS","Read from high-bit alias failed")
            write_reg(12'h003,32'h03);
            read_reg(12'h00C,value); // low 3 bits = 4, unmapped
            if (value !== 32'h0) `uvm_error("APB_ALIAS","0x00C is not LCR")
            phase.drop_objection(this);
        endtask
    endclass

    class uart_rx_fifo_order_test extends apb_uart_base_test;
        `uvm_component_utils(uart_rx_fifo_order_test)
        function new(string name, uvm_component parent); super.new(name,parent); endfunction
        task run_phase(uvm_phase phase);
            bit [31:0] value;
            phase.raise_objection(this);
            wait(e.vif.RSTN);
            init_uart_8n1();
            e.rx_bfm.send_byte(8'h11);
            e.rx_bfm.send_byte(8'h22);
            e.rx_bfm.send_byte(8'h33);
            read_reg(12'h005,value);
            if (!value[0]) `uvm_error("FIFO_ORDER","LSR says empty after 3 RX bytes")
            read_reg(12'h000,value);
            if (value[7:0] !== 8'h11) `uvm_error("FIFO_ORDER","First byte incorrect")
            read_reg(12'h000,value);
            if (value[7:0] !== 8'h22) `uvm_error("FIFO_ORDER","Second byte incorrect")
            read_reg(12'h000,value);
            if (value[7:0] !== 8'h33) `uvm_error("FIFO_ORDER","Third byte incorrect")
            read_reg(12'h005,value);
            if (value[0]) `uvm_error("FIFO_ORDER","RX FIFO still nonempty")
            phase.drop_objection(this);
        endtask
    endclass

    class uart_rx_fifo_clear_test extends apb_uart_base_test;
        `uvm_component_utils(uart_rx_fifo_clear_test)
        function new(string name, uvm_component parent); super.new(name,parent); endfunction
        task run_phase(uvm_phase phase);
            bit [31:0] value;
            phase.raise_objection(this);
            wait(e.vif.RSTN);
            init_uart_8n1();
            e.rx_bfm.send_byte(8'h55);
            e.rx_bfm.send_byte(8'hAA);
            read_reg(12'h005,value);
            if (!value[0]) `uvm_error("FIFO_CLEAR","RX FIFO did not fill")
            write_reg(12'h002,32'h02); // FCR[1] clear RX, no FIFO-enable effect
            repeat (4) @(posedge e.vif.CLK);
            read_reg(12'h005,value);
            if (value[0]) `uvm_error("FIFO_CLEAR","LSR[0] not cleared after FCR[1]")
            phase.drop_objection(this);
        endtask
    endclass

    class uart_tx_mode_matrix_test extends apb_uart_base_test;
        `uvm_component_utils(uart_tx_mode_matrix_test)
        function new(string name, uvm_component parent); super.new(name,parent); endfunction
        task run_phase(uvm_phase phase);
            bit [7:0] lcr;
            int expected_count;
            phase.raise_objection(this);
            wait(e.vif.RSTN);
            init_uart_8n1();
            expected_count=0;
            for (int bits=5; bits<=8; bits++) begin
                for (int parity=0; parity<=1; parity++) begin
                    for (int stops=1; stops<=2; stops++) begin
                        lcr=(bits-5) | ((stops-1)<<2) | (parity<<3);
                        write_reg(12'h003,{24'b0,lcr});
                        e.cfg.data_bits=bits;
                        e.cfg.parity_en=parity;
                        e.cfg.stop_bits=stops;
                        write_reg(12'h000,32'hA5);
                        expected_count++;
                        repeat ((bits+parity+stops+4)*e.cfg.bit_cycles) @(posedge e.vif.CLK);
                        if (e.sb.tx_checked != expected_count)
                            `uvm_error("TX_MODE",`sformatf("mode bits=%0d parity=%0d stop=%0d: frames=%0d expected=%0d",bits,parity,stops,e.sb.tx_checked,expected_count))
                    end
                end
            end
            phase.drop_objection(this);
        endtask
    endclass

endpackage
