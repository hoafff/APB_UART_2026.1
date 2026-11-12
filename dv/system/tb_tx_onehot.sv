`timescale 1ns/1ps
module tb_tx_onehot;
    localparam int BIT_NS=640; // D=2, 16 clocks/bit, 50MHz
    logic clk=0; always #10 clk=~clk;
    logic rst_n=0,sel=0,en=0,wr=0,rx=1,tx,ready,error,irq;
    logic [11:0] addr=0;
    logic [31:0] wd=0,rd;
    int checks,frames;
    apb_uart_sv dut(.CLK(clk),.RSTN(rst_n),.PADDR(addr),.PWDATA(wd),.PWRITE(wr),.PSEL(sel),.PENABLE(en),
        .PRDATA(rd),.PREADY(ready),.PSLVERR(error),.rx_i(rx),.tx_o(tx),.event_o(irq));
    task automatic check(input bit ok,input string why); checks++; if(!ok) $fatal(1,"ONEHOT_CHECK %s",why); endtask
    task automatic write_reg(input int a,input int value);
        @(negedge clk); sel=1; en=0; wr=1; addr=12'(a); wd=32'(value);
        @(negedge clk); en=1;
        @(posedge clk); check(ready && !error,"APB write accepted");
        @(negedge clk); sel=0; en=0; wr=0;
    endtask
    initial begin
        int mode;
        bit expected_parity;
        repeat(8) @(negedge clk); rst_n=1;
        for(int n=5;n<=8;n++) for(int p=0;p<3;p++) for(int stops=1;stops<=2;stops++) begin
            mode=n-5+(stops==2 ? 4:0)+(p!=0 ? 8:0)+(p==2 ? 16:0);
            write_reg(12,mode|128); write_reg(0,2); write_reg(4,0); write_reg(12,mode); write_reg(8,7);
            for(int hot=0;hot<8;hot++) begin
                write_reg(0,1<<hot); @(negedge tx); #(BIT_NS/2); check(!tx,"start");
                for(int b=0;b<n;b++) begin #(BIT_NS); check(tx==(b==hot),"single set bit and ignored high bits"); end
                if(p!=0) begin
                    expected_parity=(p==2) ? (hot<n):(hot>=n);
                    #(BIT_NS); check(tx==expected_parity,"one-hot parity counts only transmitted data");
                end
                repeat(stops) begin #(BIT_NS); check(tx,"stop"); end
                #(BIT_NS/2+40); check(tx,"idle"); frames++;
                $display("COV|tx.onehot.%0d.%0d.%0d.%0d|1",n,p,stops,hot);
            end
        end
        check(frames==192,"complete one-hot matrix");
        $display("SYS_TEST_COMPLETED|checks=%0d|frames=%0d",checks,frames); $finish;
    end
    initial begin #10_000_000; $fatal(1,"ONEHOT_WATCHDOG"); end
endmodule
