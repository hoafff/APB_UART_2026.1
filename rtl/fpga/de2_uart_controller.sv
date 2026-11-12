module de2_uart_controller #(parameter int POLL_CYCLES=5000) (
    input logic clk,rst_n,send_i,
    input logic [17:0] sw_i,
    output logic [11:0] paddr,
    output logic [31:0] pwdata,
    output logic pwrite,psel,penable,
    input logic [31:0] prdata,
    input logic pready,pslverr,irq_i,
    output logic init_done_o,fault_o,
    output logic [7:0] rx_byte_o,
    output logic [4:0] status_o
);
    typedef enum logic [3:0] {RESET,LCR1,DLL,DLM,LCR0,FCR,IER,IDLE,LSR,DECIDE,RBR,CHOOSE_TX,THR,FAULT} state_t;
    state_t state;
    logic phase_q;
    logic [2:0] init_wait;
    logic [7:0] init_lcr,lsr_q,manual_data,echo_data,thr_data;
    logic manual_valid,echo_valid,echo_this_read,thr_is_echo,last_echo;
    logic [31:0] poll_q;
    logic access,apb_fault,consume_manual;
    assign access=psel && penable && pready;
    assign apb_fault=access && pslverr;
    assign consume_manual=access && !pslverr && state==THR && !thr_is_echo;
    always_comb begin
        paddr=0; pwdata=0; pwrite=0; psel=0; penable=0;
        case(state)
            LCR1: begin psel=1; pwrite=1; paddr=12; pwdata='h83; end
            DLL:  begin psel=1; pwrite=1; paddr=0;  pwdata=27; end
            DLM:  begin psel=1; pwrite=1; paddr=4;  pwdata=0; end
            LCR0: begin psel=1; pwrite=1; paddr=12; pwdata={24'b0,init_lcr}; end
            FCR:  begin psel=1; pwrite=1; paddr=8;  pwdata=7; end
            IER:  begin psel=1; pwrite=1; paddr=4;  pwdata=5; end
            LSR:  begin psel=1; paddr=20; end
            RBR:  begin psel=1; paddr=0; end
            THR:  begin psel=1; pwrite=1; paddr=0; pwdata={24'b0,thr_data}; end
            default: ;
        endcase
        penable=psel && phase_q;
    end
    always_ff @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin
            state<=RESET; phase_q<=0; init_wait<=0; init_lcr<=3; lsr_q<=0;
            init_done_o<=0; fault_o<=0; rx_byte_o<=0; status_o<=0; poll_q<=0;
            manual_valid<=0; echo_valid<=0; manual_data<=0; echo_data<=0;
            echo_this_read<=0; thr_data<=0; thr_is_echo<=0; last_echo<=1;
        end else begin
            if(poll_q<POLL_CYCLES) poll_q<=poll_q+1'b1;
            if(psel && !phase_q) phase_q<=1;
            if(access) begin
                phase_q<=0;
                if(pslverr) begin state<=FAULT; fault_o<=1; init_done_o<=0; end
                else case(state)
                    LCR1: state<=DLL;
                    DLL: state<=DLM;
                    DLM: state<=LCR0;
                    LCR0: state<=FCR;
                    FCR: state<=IER;
                    IER: begin state<=IDLE; init_done_o<=1; poll_q<=0; end
                    LSR: begin
                        lsr_q<=prdata[7:0]; status_o[0]<=prdata[0];
                        status_o[4:1]<=status_o[4:1]|prdata[4:1];
                        poll_q<=0; state<=DECIDE;
                    end
                    RBR: begin
                        rx_byte_o<=prdata[7:0];
                        if(echo_this_read) begin echo_data<=prdata[7:0]; echo_valid<=1; end
                        state<=CHOOSE_TX;
                    end
                    THR: begin
                        if(thr_is_echo) echo_valid<=0; else manual_valid<=0;
                        last_echo<=thr_is_echo; state<=IDLE;
                    end
                    default: ;
                endcase
            end else if(!psel) case(state)
                RESET: begin
                    if(init_wait==3) begin
                        init_lcr<=8'h03|(sw_i[14] ? (sw_i[15] ? 8'h18:8'h08):8'h00);
                        state<=LCR1;
                    end else init_wait<=init_wait+1'b1;
                end
                IDLE: if(poll_q>=POLL_CYCLES-1 || manual_valid || echo_valid || (irq_i && !sw_i[16])) state<=LSR;
                DECIDE: begin
                    if(lsr_q[0] && !sw_i[16] && (!sw_i[17] || !echo_valid)) begin
                        // Capture mode and reserve the slot when entering SETUP.
                        echo_this_read<=sw_i[17]; state<=RBR;
                    end else state<=CHOOSE_TX;
                end
                CHOOSE_TX: begin
                    if(lsr_q[5] && (manual_valid || echo_valid)) begin
                        if(echo_valid && (!manual_valid || !last_echo)) begin thr_data<=echo_data; thr_is_echo<=1; end
                        else begin thr_data<=manual_data; thr_is_echo<=0; end
                        state<=THR;
                    end else state<=IDLE;
                end
                default: ;
            endcase
            // New manual request wins clearing an older consumed request.
            if(send_i && init_done_o && state!=FAULT && !apb_fault) begin
                if(!manual_valid || consume_manual) begin manual_valid<=1; manual_data<=sw_i[7:0]; end
                else fault_o<=1;
            end
        end
    end
endmodule
