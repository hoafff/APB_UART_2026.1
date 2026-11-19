#include "apb_bench.hpp"
#include <iostream>
#include <string>

void apb_fifo_collision(Bench&);
void apb_fifo_clear(Bench&);
void missing_rx_clear_control(Bench&);
void rx_phase(Bench&);
void stretched_access(Bench&);

static void midframe_reset(Bench& b) {
    const unsigned old_period = 0x010f + 1, new_period = 32;
    b.configure_8n1(old_period - 1);
    b.write(IER, 2);
    b.rx_byte(0x63, old_period);
    b.equal("unread RX before reset", b.read(LSR), 0x61);
    b.equal("armed IER", b.read(IER), 2);
    const unsigned first = b.first_tx(0x00);
    b.write(THR, 0xda);
    b.write(THR, 0xe5);
    b.drive_rx(0, old_period);          // Another start, one full data bit and half the next.
    b.drive_rx(1, old_period);
    b.drive_rx(0, old_period / 2);
    b.equal("DR=1 THRE=TEMT=0 before reset", b.read(LSR), 0x01);
    b.equal("IRQ before reset", b.dut.event_o, 1);
    b.setup(true, THR, 0x74);
    b.dut.PENABLE = 1;
    b.dut.eval();                       // Abort this ACCESS before its first rising edge.
    b.level(first, b.now() - first + 1, 0);
    const unsigned interrupted = b.now();
    b.dut.RSTN = 0;
    b.dut.rx_i = 1;
    b.dut.eval();
    b.equal("asynchronous TX idle", b.dut.tx_o, 1);
    b.equal("asynchronous IRQ clear", b.dut.event_o, 0);
    b.tick();                           // ACCESS still present at this reset edge.
    b.release_reset();                  // Remove ACCESS before release, keep RX high.
    b.equal("reset LCR", b.read(LCR), 0);
    b.equal("reset IER", b.read(IER), 0);
    b.equal("reset LSR", b.read(LSR), 0x60);
    b.equal("reset IIR", b.read(IIR), 0xc1);
    b.write(LCR, 0x80);
    b.equal("reset DLL", b.read(DLL), 0);
    b.equal("reset DLM", b.read(DLM), 0);
    b.tick(12 * old_period);
    b.equal("no stale RX completion", b.read(LSR), 0x60);
    b.configure_8n1(new_period - 1);
    b.level(interrupted + 1, b.now() - interrupted, 1);
    const unsigned fresh = b.first_tx(0xa9);
    b.rx_byte(0xb6, new_period);
    b.equal("recovery RX ready", b.read(LSR), 0x61);
    b.equal("recovery RBR", b.read(RBR), 0xb6);
    b.tick(2 * 10 * new_period);
    b.equal("recovery queues empty", b.read(LSR), 0x60);
    const unsigned end = b.frame(fresh, new_period, 0xa9);
    b.level(end, b.now() - end + 1, 1);
    std::cout << "PASS midframe-reset REG-02 tx_clocks_before_reset=" << interrupted - first
              << " pre_lsr=01 async_tx=1 async_irq=0 reset_lsr=60 reset_iir=c1"
                 " lcr/ier/dll/dlm=00 tx_recovery=a9 rx_recovery=b6\n";
}

static void baud_endpoint(Bench& b, unsigned divisor, const std::string& name) {
    const unsigned period = divisor + 1;
    b.configure_8n1(divisor);
    const unsigned first = b.first_tx(0x55);
    b.write(THR, 0xa6);
    b.until(first + 2 * (10 * period + 2) + 8);
    unsigned edge = b.next_transition(first);       // Start to bit 0.
    const unsigned start_width = edge - first;
    b.equal("start clocks", start_width, period + 1);
    unsigned data_width = 0;
    for (unsigned i = 0; i < 8; ++i) {            // Bit 0..7 to the next transition.
        const unsigned next = b.next_transition(edge);
        data_width = next - edge;
        b.equal("data clocks", data_width, period);
        edge = next;
    }
    const unsigned second = b.next_transition(edge);
    b.equal("stop + idle clocks", second - edge, period + 1);
    const unsigned idle = b.frame(first, period, 0x55);
    b.level(idle, 1, 1);
    const unsigned end = b.frame(second, period, 0xa6);
    b.level(end, b.now() - end + 1, 1);
    b.equal("TX fully drained", b.read(LSR), 0x60);
    std::cout << "PASS " << name << " BAUD-01 div=" << divisor
              << " start_clocks=" << start_width << " data_clocks=" << data_width
              << " data_intervals=8 stop_plus_idle=" << second - edge
              << " start_spacing=" << second - first << " frames=55,a6\n";
}

// A legal two-clock APB LSR read at every opportunity in the observation window.
static unsigned poll_lsr(Bench& b, unsigned clocks, bool require_empty) {
    b.equal("whole APB reads in interval", clocks % 2, 0);
    for (unsigned i = 0; i < clocks; i += 2) {
        const unsigned lsr = b.read(LSR);
        b.equal("LSR FE/BI", lsr & 0x18, 0);
        b.equal("line-status event", b.dut.event_o, 0);
        if (require_empty) b.equal("unexpected extra RX byte", lsr & 1, 0);
    }
    return clocks / 2;
}

static void malformed_rx(Bench& b, bool sustained_low) {
    const unsigned period = 434;
    b.configure_8n1(period - 1);
    b.write(IER, 4);
    b.equal("RX initially empty", b.read(LSR), 0x60);
    const unsigned start = b.now();
    b.dut.rx_i = 0;
    unsigned polls = 0;
    unsigned low_clocks = 4;
    if (sustained_low) {
        polls += poll_lsr(b, 12 * period, false);
    } else {
        polls += poll_lsr(b, low_clocks, true);
        b.dut.rx_i = 1;
        polls += poll_lsr(b, 12 * period, false);
    }
    const unsigned lsr = b.read(LSR);
    b.equal("malformed data present", lsr, 0x61);
    const unsigned byte = b.read(RBR);
    b.equal("malformed RBR byte", byte, sustained_low ? 0x00 : 0xff);
    b.equal("single malformed byte", b.read(LSR), 0x60);
    polls += poll_lsr(b, 12 * period, true); // Keep the original line level after draining.
    if (sustained_low) low_clocks = b.now() - start;
    b.dut.rx_i = 1;
    polls += poll_lsr(b, 2 * period, true);
    b.equal("line-status IIR", b.read(IIR), 0xc1);
    b.rx_byte(0x69, period);
    b.equal("next valid RX ready", b.read(LSR), 0x61);
    b.equal("next valid RBR", b.read(RBR), 0x69);
    b.equal("no additional byte", b.read(LSR), 0x60);
    std::cout << "PASS " << (sustained_low ? "rx-break" : "rx-glitch")
              << " RX-02,RX-03 div=433 low_clocks=" << low_clocks
              << " rbr=" << (sustained_low ? "00" : "ff") << " head_lsr=61 fe_bi=0"
              << " lsr_polls=" << polls << " recovery=69\n";
}

int main(int argc, char** argv) {
    if (argc != 2) return 2;
    const std::string name = argv[1];
    try {
        VerilatedContext context;
        context.threads(1);
        unsigned budget = 48000;
        if (name == "baud-max") budget = 1320000;
        if (name == "rx-phase") budget = 300000;
        Bench b(context, budget);
        if (name == "apb-collisions") apb_fifo_collision(b);
        else if (name == "fcr-clear") apb_fifo_clear(b);
        else if (name == "missing-clear-control") missing_rx_clear_control(b);
        else if (name == "midframe-reset") midframe_reset(b);
        else if (name == "baud-min") baud_endpoint(b, 0, name);
        else if (name == "baud-max") baud_endpoint(b, 65535, name);
        else if (name == "rx-glitch" || name == "rx-break") malformed_rx(b, name == "rx-break");
        else if (name == "rx-phase") rx_phase(b);
        else if (name == "held-access") stretched_access(b);
        else throw std::invalid_argument("unknown probe");
    } catch (const std::exception& e) {
        std::cerr << "FAIL " << name << ": " << e.what() << '\n';
        return 1;
    }
}
