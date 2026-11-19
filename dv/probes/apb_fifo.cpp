#include "apb_bench.hpp"
#include <algorithm>
#include <iostream>

namespace {
constexpr unsigned Period = 32, FrameSpacing = 10 * Period + 2;
constexpr uint8_t RxByte = 0xa6;

// Send the start and first seven data bits. Bit 7 and stop are both high,
// leaving the APB driver free to schedule transactions across byte arrival.
unsigned rx_prefix(Bench& b) {
    static_assert(RxByte & 0x80);
    const unsigned origin = b.now();
    b.drive_rx(0, Period);
    for (unsigned bit = 0; bit < 7; ++bit) b.drive_rx((RxByte >> bit) & 1, Period);
    b.dut.rx_i = 1;
    return origin;
}

// Two independent frames with legal, nondestructive LSR reads on opposite
// phases locate the first ACCESS edge that sees DR. Per REG-04, LSR captures
// the pre-edge nonempty state; the APB read samples before the ACCESS edge.
// Thus first readable DR is two rising edges after insertion. Only the timing
// anchor comes from calibration. Each RBR survivor and its value are prescribed.
unsigned arrival_offset(Bench& b) {
    unsigned first_dr[2]{};
    for (unsigned phase = 0; phase < 2; ++phase) {
        b.reset();
        b.configure_8n1(Period - 1);
        b.equal("calibration starts empty", b.read(LSR), 0x60);
        const unsigned start = rx_prefix(b);
        b.tick(phase);
        while (b.now() - start < 10 * Period) {
            if (b.read(LSR) & 1) {
                first_dr[phase] = b.now() - start;
                break;
            }
        }
        if (!first_dr[phase]) throw std::runtime_error("no DR in RX calibration window");
        b.equal("calibration RBR", b.read(RBR), RxByte);
    }
    const auto first = std::minmax(first_dr[0], first_dr[1]);
    b.equal("adjacent DR sample phases", first.second - first.first, 1);
    const unsigned insertion = first.first - 2;
    std::cout << "CHECK rx-alignment period=" << Period << " first_dr_access_offsets="
              << first.first << "," << first.second << " insertion_offset=" << insertion << "\n";
    return insertion;
}

void rx_rbr_collision(Bench& b, unsigned insertion, int skew) {
    b.reset();
    b.configure_8n1(Period - 1);
    b.equal("empty before overlapping RBR", b.read(LSR), 0x60);
    const unsigned start = rx_prefix(b);
    const unsigned access = start + insertion + skew;
    b.until(access - 2);
    const unsigned overlap = b.read(RBR);
    b.equal("RBR ACCESS clock", b.now(), access);
    b.until(start + 11 * Period);
    b.equal("alignment: RX offer edge", b.last_rx_offer, start + insertion);
    if (skew == 1) {
        b.equal("RBR one edge after arrival", overlap, RxByte);
    } else {
        // The return value of a read from an empty FIFO does not denote a byte.
        b.equal("arrival survived overlapping read", b.read(LSR), 0x61);
        b.equal("retained RBR", b.read(RBR), RxByte);
    }
    b.equal("exactly one received byte", b.read(LSR), 0x60);
    std::cout << "CHECK empty-rbr access_minus_arrival=" << skew
              << " a6_returned_by=" << (skew == 1 ? "overlapping_read" : "subsequent_read") << "\n";
}

void tx_thr_collision(Bench& b, unsigned skew) {
    b.reset();
    b.configure_8n1(Period - 1);
    const unsigned first = b.first_tx(0xb5);
    for (unsigned i = 0; i < 16; ++i) b.write(THR, 0x20 + i);
    b.equal("TX pending and shift register busy", b.read(LSR), 0);
    const unsigned dequeue = first + FrameSpacing;
    b.until(dequeue + skew - 2);
    b.write(THR, 0xd7);
    b.equal("THR ACCESS clock", b.now(), dequeue + skew);
    b.equal("alignment: TX dequeue edge", b.last_tx_load, dequeue);
    const unsigned frames = 17 + skew; // d7 accepted only one clock after dequeue.
    b.until(first + (frames + 1) * FrameSpacing);
    unsigned start = first;
    for (unsigned i = 0; i < frames; ++i) {
        const uint8_t byte = i == 0 ? 0xb5 : (i == 17 ? 0xd7 : 0x20 + i - 1);
        const unsigned idle = b.frame(start, Period, byte);
        b.level(idle, 1, 1);
        start = idle + 1;
    }
    b.level(start, b.now() - start + 1, 1);
    b.equal("TX empty after collision stream", b.read(LSR), 0x60);
    std::cout << "CHECK full-thr access_minus_dequeue=" << skew
              << " ready=1 error=0 tx_order=b5,20..2f" << (skew ? ",d7" : "")
              << " frames=" << frames << "\n";
}

void rx_clear(Bench& b, unsigned insertion, unsigned gap, uint8_t command = 0x02) {
    b.reset();
    b.configure_8n1(Period - 1);
    b.rx_byte(0x35, Period);
    b.equal("old RX entry pending", b.read(LSR), 0x61);
    const unsigned start = rx_prefix(b);
    const unsigned write = start + insertion - gap;
    b.until(write - 2);
    b.write(FCR, command);                    // WRITE ACCESS at k.
    b.equal("RX clear ACCESS clock", b.now(), write);
    b.equal("DR sampled on ACCESS k+2", b.read(LSR), 0x61);
    b.until(start + 11 * Period);
    b.equal("alignment: RX offer relative to FCR", b.last_rx_offer, write + gap);
    if (gap == 2) {
        b.equal("byte arriving after clear is valid", b.read(LSR), 0x61);
        b.equal("only post-clear arrival survived", b.read(RBR), RxByte);
    }
    b.equal("old RX and colliding entries gone", b.read(LSR), 0x60);
    b.rx_byte(0x71, Period);
    b.equal("fresh RX valid after clear", b.read(LSR), 0x61);
    b.equal("fresh RX read after clear", b.read(RBR), 0x71);
    b.equal("no stale RX replay", b.read(LSR), 0x60);
    std::cout << "CHECK rx-fcr arrival_minus_write=" << gap
              << " lsr_at_k+2=61 retained=" << (gap == 2 ? "a6" : "empty") << " refill=71\n";
}

void tx_clear(Bench& b, unsigned gap) {
    b.reset();
    b.configure_8n1(Period - 1);
    const unsigned first = b.first_tx(0x55);
    b.write(THR, 0x39);
    b.write(THR, 0xde);
    b.write(THR, 0x8c);
    b.equal("queued TX before FCR", b.read(LSR), 0);
    const unsigned dequeue = first + FrameSpacing;
    b.until(dequeue - gap - 2);
    b.write(FCR, 0x04);
    b.equal("TX clear ACCESS clock", b.now(), dequeue - gap);
    b.until(first + 4 * FrameSpacing);
    unsigned idle = b.frame(first, Period, 0x55);
    if (gap <= 1) {
        b.level(idle, 1, 1);
        idle = b.frame(dequeue, Period, 0x39);  // The shifter captured the old head.
    }
    b.level(idle, b.now() - idle + 1, 1);
    b.equal("cleared TX tail", b.read(LSR), 0x60);
    const unsigned fresh = b.first_tx(0x93);
    b.tick(2 * FrameSpacing);
    idle = b.frame(fresh, Period, 0x93);
    b.level(idle, b.now() - idle + 1, 1);
    std::cout << "CHECK tx-fcr scheduled_dequeue_minus_write=" << gap
              << " tx_order=" << (gap <= 1 ? "55,39" : "55") << " refill=93\n";
}
} // namespace

void apb_fifo_collision(Bench& b) {
    const unsigned insertion = arrival_offset(b);
    for (int skew : {-1, 0, 1}) rx_rbr_collision(b, insertion, skew);
    for (unsigned skew : {0u, 1u}) tx_thr_collision(b, skew);
    std::cout << "PASS apb-collisions FIFO-02 rx_phases=3 tx_phases=2\n";
}

void apb_fifo_clear(Bench& b) {
    const unsigned insertion = arrival_offset(b);
    for (unsigned gap : {0u, 1u, 2u}) rx_clear(b, insertion, gap);
    for (unsigned gap : {0u, 1u, 2u}) tx_clear(b, gap);
    std::cout << "PASS fcr-clear FIFO-03 rx_phases=3 tx_phases=3\n";
}

void missing_rx_clear_control(Bench& b) {
    // Same RX stimulus and edge, but the bus master omits the FCR clear bit.
    // The normal k+1 survivor check must see DR still asserted and fail.
    const unsigned insertion = arrival_offset(b);
    rx_clear(b, insertion, 1, 0x00);
}
