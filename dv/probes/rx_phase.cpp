#include "apb_bench.hpp"
#include <iostream>

// t=1 is the first rising CLK edge at which the external start level is low.
// Move one transition across the predicted input sampling edge. Observe only
// PRDATA, PREADY and PSLVERR to find which level the receiver actually used.
void rx_phase(Bench& b) {
    unsigned frames = 0, early_reads = 0;
    for (unsigned divisor : {432u, 433u}) {
        const unsigned period = divisor + 1;
        const unsigned first_sample = divisor / 2 + period + 1;
        const unsigned last_sample = first_sample + 7 * period;
        for (unsigned bit = 0; bit < 8; ++bit) {
            for (int shift : {-1, 0, 1}) {
                b.reset();
                b.configure_8n1(divisor);
                b.write(LCR, 0x0b);  // 8E1
                const unsigned cut = static_cast<unsigned>(int(first_sample + bit * period) + shift);
                const unsigned base = 0xa5u & ~(1u << bit);
                const unsigned expected = base | ((shift <= 0 ? 1u : 0u) << bit);
                unsigned parity = 0;
                for (unsigned i = 0; i < 8; ++i) parity ^= (expected >> i) & 1;
                const bool pop = shift > 0;
                // Three synchronizer clocks, then FIFO insertion, then registered DR.
                // The legal READ ACCESS observes values immediately before its edge.
                const unsigned access = last_sample + (shift < 0 ? 5 : 6);
                for (unsigned t = 1; t <= 12 * period; ++t) {
                    const unsigned field = (t - 1) / period;
                    bool level = true;
                    if (field == 0) level = false;
                    else if (field <= 8)
                        level = (field - 1 == bit) ? (t >= cut) : bool((base >> (field - 1)) & 1);
                    else if (field == 9) level = parity;
                    b.dut.rx_i = level;
                    if (t + 1 == access) {
                        b.dut.PSEL = 1;
                        b.dut.PWRITE = 0;
                        b.dut.PENABLE = 0;
                        b.dut.PADDR = pop ? RBR : LSR;
                    }
                    if (t == access) {
                        b.dut.PENABLE = 1;
                        b.dut.eval();
                        b.equal("early APB ready", b.dut.PREADY, 1);
                        b.equal("early APB error", b.dut.PSLVERR, 0);
                        if (pop) b.equal("RBR visible before external parity bit", b.dut.PRDATA, expected);
                        else b.equal("DR on selected edge", b.dut.PRDATA, shift < 0 ? 0x60 : 0x61);
                    }
                    b.tick();
                    if (t == access) b.idle_bus();
                }
                b.equal("LSR after complete frame", b.read(LSR), pop ? 0x60 : 0x61);
                if (pop) ++early_reads;
                else b.equal("swept sample captured at RBR", b.read(RBR), expected);
                b.equal("only one RX byte", b.read(LSR), 0x60);
                ++frames;
            }
        }
    }
    std::cout << "PASS rx-phase BAUD-03,RX-01,REG-04 div=432,433 data_bits=8 shifts=-1,0,+1"
              << " first_pin_sample=650,651 frames=" << frames << " pre_parity_rbr=" << early_reads << '\n';
}

void stretched_access(Bench& b) {
    constexpr unsigned period = 32;
    b.configure_8n1(period - 1);
    b.rx_byte(0x6d, period);
    b.rx_byte(0xb2, period);
    b.setup(false, RBR);
    b.dut.PENABLE = 1;
    for (unsigned expected : {0x6du, 0xb2u}) {
        b.dut.eval();
        b.equal("stretched RBR", b.dut.PRDATA, expected);
        b.tick();
    }
    b.idle_bus();
    b.tick(2);
    b.equal("stretched read drained twice", b.read(LSR), 0x60);

    const unsigned before = b.now();
    b.setup(true, THR, 0xa7);
    b.dut.PENABLE = 1;
    b.tick(2);
    b.idle_bus();
    b.tick(32 * period);
    const unsigned first = b.next_transition(before);
    const unsigned idle = b.frame(first, period, 0xa7);
    const unsigned second = b.next_transition(idle);
    const unsigned end = b.frame(second, period, 0xa7);
    b.level(end, b.now() - end + 1, 1);
    std::cout << "PASS held-access APB-01 protocol_violation read_twice=6d,b2 write_twice=a7,a7\n";
}
