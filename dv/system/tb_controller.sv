`timescale 1ns/1ps
module tb_controller;
    logic clk=0; always #10 clk=~clk;
    logic rst_n=0,send=0,ready=1,inject_error=0,space_available=1;
    logic [17:0] sw=0;
    logic [11:0] addr;
    logic [31:0] wdata,rdata;
    logic wr,sel,en,error,irq,done,fault;
    logic [7:0] last_rx;
    logic [4:0] status;
    int rx_count,rx_index,checks,ticks,last_poll,checked_polls;
    bit check_spacing;
    byte sent[$];
    assign error=sel && en && inject_error;
    assign irq=rx_count>0;
    always_comb begin
        rdata=0;
        if(addr==20) rdata=(space_available ? 'h20:0)|(rx_count>0 ? 1:0);
        if(addr==0) rdata='he0+rx_index;
    end
    de2_uart_controller #(.POLL_CYCLES(20)) dut(.clk(clk),.rst_n(rst_n),.send_i(send),.sw_i(sw),
        .paddr(addr),.pwdata(wdata),.pwrite(wr),.psel(sel),.penable(en),.prdata(rdata),
        .pready(ready),.pslverr(error),.irq_i(irq),.init_done_o(done),.fault_o(fault),.rx_byte_o(last_rx),.status_o(status));
    task automatic check(input bit ok,input string why); checks++; if(!ok) $fatal(1,"CONTROLLER_CHECK %s",why); endtask
    task automatic cycles(input int n); repeat(n) @(negedge clk); endtask
    task automatic boot();
        rst_n=0; send=0; sw=0; ready=1; inject_error=0; space_available=1; rx_count=0; rx_index=0; sent.delete();
        cycles(4); rst_n=1; cycles(24); check(done && !fault,"controller init");
    endtask
    task automatic press(input byte value);
        @(negedge clk); sw[7:0]=value; send=1; @(negedge clk); send=0;
    endtask
    always @(posedge clk) begin
        ticks++;
        if(check_spacing && sel && en && ready && !wr && addr==20) begin
            if(checked_polls!=0) check(ticks-last_poll>=20 && ticks-last_poll<=23,"hold IRQ obeys poll interval");
            last_poll=ticks; checked_polls++;
        end
    end
    always @(posedge clk) if(rst_n && sel && en && ready && !error && done) begin
        if(wr && addr==0) sent.push_back(wdata[7:0]);
        if(!wr && addr==0 && rx_count>0) begin rx_count<=rx_count-1; rx_index<=rx_index+1; end
    end
    initial begin
        byte value;
        // Explicit injected error at init, not a natural response of the good UART.
        cycles(4); rst_n=1; wait(sel && !en); @(negedge clk); inject_error=1;
        cycles(4); check(fault && !done && !sel,"init APB error enters FAULT");
        cycles(20); check(!sel,"FAULT issues no further transfer");
        $display("SYS_COV|fault_init_stub|1");
        boot(); sw[16]=1; rx_count=1; checked_polls=0; check_spacing=1; cycles(120); check_spacing=0;
        check(checked_polls>=3 && rx_count==1,"hold RX: periodic status polling but no RBR pop");
        sw[16]=0; cycles(20); check(rx_count==0,"release hold resumes RX service");
        $display("SYS_COV|hold_irq_poll_spacing|1");
        boot(); ready=0; press('ha1); press('ha2); cycles(10);
        check(fault && done,"manual overflow indicates fault but keeps service enabled");
        ready=1; cycles(60); check(sent.size()==1,"overflow retains only original request");
        value=sent.pop_front(); check(value=='ha1,"manual slot not overwritten");
        $display("SYS_COV|manual_overflow_preserves_byte|1");
        boot(); press('ha3);
        wait(sel && en && wr && addr==0);
        @(negedge clk); sw[7:0]='ha4; send=1;
        @(negedge clk); send=0; cycles(60);
        check(sent.size()==2 && !fault,"consume and new request same edge");
        value=sent.pop_front(); check(value=='ha3,"old byte first"); value=sent.pop_front(); check(value=='ha4,"new byte kept");
        $display("SYS_COV|manual_consume_and_new|1");
        boot(); sw[17]=1; space_available=0; rx_count=3; press('hb0); cycles(70);
        check(rx_count==2 && dut.echo_valid,"echo slot reserves one byte and stops RBR when full");
        space_available=1; wait(sent.size()==1); press('hb1); cycles(160);
        check(sent.size()==5 && rx_count==0,"all manual/echo requests serviced");
        value=sent.pop_front(); check(value=='hb0,"manual first when both pending");
        value=sent.pop_front(); check(value=='he0,"echo gets next opportunity");
        value=sent.pop_front(); check(value=='hb1,"manual gets next opportunity");
        value=sent.pop_front(); check(value=='he1,"second echo byte");
        value=sent.pop_front(); check(value=='he2,"third echo byte");
        $display("SYS_COV|echo_backpressure_fairness|1");
        boot(); press('h5a); wait(sel && !en && wr && addr==0); @(negedge clk); inject_error=1;
        cycles(5); check(fault && !done && !sel,"runtime APB fault stops master");
        check(dut.manual_valid && dut.manual_data=='h5a,"fault must not consume pending byte");
        check(sent.size()==0,"errored THR is not successful transmission");
        $display("SYS_COV|fault_runtime_preserves_pending|1");
        $display("SYS_TEST_COMPLETED|checks=%0d",checks); $finish;
    end
    initial begin #1_000_000; $fatal(1,"CONTROLLER_WATCHDOG"); end
endmodule
