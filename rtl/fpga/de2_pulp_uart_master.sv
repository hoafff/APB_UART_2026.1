// Single APB master for the pulpinov1 byte-offset register interface.
module de2_pulp_uart_master (
    input  logic        clk,
    input  logic        rst_n,
    input  logic        key_press,
    input  logic [7:0]  key_byte,
    input  logic        even_select,
    input  logic        hold_rx,
    input  logic        echo_enable,
    output logic [11:0] paddr,
    output logic [31:0] pwdata,
    output logic        pwrite,
    output logic        psel,
    output logic        penable,
    input  logic [31:0] prdata,
    input  logic        pready,
    input  logic        pslverr,
    output logic        init_done,
    output logic        fault,
    output logic        even_mode,
    output logic [7:0]  last_rx,
    output logic [7:0]  last_lsr
);
    // The PULP counters compare for equality with DIVISOR, then restart at 0.
    localparam logic [15:0] DIVISOR = 16'd433;
    localparam int unsigned POLL_CYCLES = 5000;  // 100 us while idle
    localparam int unsigned POLL_BITS = $clog2(POLL_CYCLES);
    typedef enum logic [3:0] {
        Boot, OpenDivisor, WriteDll, WriteDlm, SetFormat, ClearFifos, SetIer,
        Idle, ReadStatus, ReadByte, WriteByte, Halt
    } state_t;
    state_t state;
    logic access_phase;
    logic [1:0] boot_wait;
    logic [POLL_BITS-1:0] poll_count;
    logic key_pending, echo_pending, echo_this_read, tx_is_echo, last_tx_echo;
    logic [7:0] queued_key, queued_echo, tx_byte;

    always_comb begin
        psel = 1'b1;
        pwrite = 1'b1;
        paddr = 12'h000;
        pwdata = 32'b0;
        case (state)
            OpenDivisor: begin paddr = 12'h003; pwdata = 32'h83; end
            WriteDll:    begin paddr = 12'h000; pwdata[7:0] = DIVISOR[7:0]; end
            WriteDlm:    begin paddr = 12'h001; pwdata[7:0] = DIVISOR[15:8]; end
            SetFormat:   begin paddr = 12'h003; pwdata = even_mode ? 32'h0b : 32'h03; end
            ClearFifos:  begin paddr = 12'h002; pwdata = 32'h07; end
            SetIer:      begin paddr = 12'h001; pwdata = 32'h05; end
            ReadStatus:  begin paddr = 12'h005; pwrite = 1'b0; end
            ReadByte:    begin paddr = 12'h000; pwrite = 1'b0; end
            WriteByte:   begin paddr = 12'h000; pwdata[7:0] = tx_byte; end
            default:     begin psel = 1'b0; pwrite = 1'b0; end
        endcase
        penable = psel && access_phase;
    end

    wire complete = psel && penable && pready;
    wire consume_key = complete && !pslverr && state == WriteByte && !tx_is_echo;
    wire choose_echo = echo_pending && (!key_pending || !last_tx_echo);

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= Boot;
            access_phase <= 1'b0;
            boot_wait <= '0;
            poll_count <= '0;
            init_done <= 1'b0;
            fault <= 1'b0;
            even_mode <= 1'b0;
            last_rx <= '0;
            last_lsr <= '0;
            key_pending <= 1'b0;
            echo_pending <= 1'b0;
            echo_this_read <= 1'b0;
            tx_is_echo <= 1'b0;
            last_tx_echo <= 1'b1;
            queued_key <= '0;
            queued_echo <= '0;
            tx_byte <= '0;
        end else begin
            if (psel && !penable)
                access_phase <= 1'b1;
            if (complete) begin
                access_phase <= 1'b0;
                if (pslverr) begin
                    init_done <= 1'b0;
                    fault <= 1'b1;
                    state <= Halt;
                end else begin
                    case (state)
                        OpenDivisor: state <= WriteDll;
                        WriteDll:    state <= WriteDlm;
                        WriteDlm:    state <= SetFormat;
                        SetFormat:   state <= ClearFifos;
                        ClearFifos:  state <= SetIer;
                        SetIer: begin
                            init_done <= 1'b1;
                            state <= ReadStatus;
                        end
                        ReadStatus: begin
                            last_lsr <= prdata[7:0];
                            poll_count <= '0;
                            // [5] means TX FIFO empty, including while the shifter is busy.
                            if (prdata[5] && (key_pending || echo_pending)) begin
                                tx_byte <= choose_echo ? queued_echo : queued_key;
                                tx_is_echo <= choose_echo;
                                state <= WriteByte;
                            end else if (prdata[0] && !hold_rx && (!echo_enable || !echo_pending)) begin
                                // Reserve an echo slot when committing this RBR transaction.
                                echo_this_read <= echo_enable;
                                state <= ReadByte;
                            end else begin
                                state <= Idle;
                            end
                        end
                        ReadByte: begin
                            last_rx <= prdata[7:0];
                            if (echo_this_read) begin
                                queued_echo <= prdata[7:0];
                                echo_pending <= 1'b1;
                            end
                            // Re-poll immediately to drain a burst faster than the idle timer.
                            state <= ReadStatus;
                        end
                        WriteByte: begin
                            if (tx_is_echo)
                                echo_pending <= 1'b0;
                            else
                                key_pending <= 1'b0;
                            last_tx_echo <= tx_is_echo;
                            state <= ReadStatus;
                        end
                        default: state <= Halt;
                    endcase
                end
            end else if (state == Boot) begin
                // Allow two switch-synchronizer stages to fill after reset release.
                if (boot_wait == 2'd2) begin
                    even_mode <= even_select;
                    state <= OpenDivisor;
                end else begin
                    boot_wait <= boot_wait + 1'b1;
                end
            end else if (state == Idle) begin
                if (key_pending || echo_pending || poll_count == POLL_BITS'(POLL_CYCLES - 1))
                    state <= ReadStatus;
                else
                    poll_count <= poll_count + 1'b1;
            end

            // A new press on the edge that consumes the old byte reuses the slot.
            if (key_press && init_done && !(complete && pslverr)) begin
                if (!key_pending || consume_key) begin
                    queued_key <= key_byte;
                    key_pending <= 1'b1;
                end else begin
                    fault <= 1'b1;  // keep the older request, report the dropped press
                end
            end
        end
    end
endmodule
