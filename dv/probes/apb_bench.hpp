#pragma once

#include "Vprobe_uart.h"
#include <cstdint>
#include <sstream>
#include <stdexcept>
#include <vector>

enum Register : unsigned { RBR = 0, THR = 0, DLL = 0, IER = 1, DLM = 1, IIR = 2, FCR = 2, LCR = 3, LSR = 5 };

// Each sample is tx_o just after a rising edge. APB samples PRDATA before that
// edge so popping RBR cannot substitute the next head for the completed read.
class Bench {
    VerilatedContext& context;
    const unsigned budget;
    std::vector<uint8_t> tx;

public:
    Vprobe_uart dut;
    unsigned last_rx_offer = 0, last_tx_load = 0;

    Bench(VerilatedContext& ctx, unsigned max_cycles)
        : context(ctx), budget(max_cycles), dut(&ctx) {
        dut.CLK = 0;
        idle_bus();
        dut.rx_i = 1;
        dut.RSTN = 1;
        dut.eval();
        tx.push_back(dut.tx_o);
        reset();
    }
    ~Bench() { dut.final(); }
    unsigned now() const { return static_cast<unsigned>(tx.size() - 1); }

    void equal(const char* what, unsigned got, unsigned want) const {
        if (got != want) {
            std::ostringstream msg;
            msg << what << " at clock " << now() << ": got " << got << ", expected " << want;
            throw std::runtime_error(msg.str());
        }
    }
    void tick(unsigned count = 1) {
        if (count > budget - now()) throw std::runtime_error("simulation clock budget exceeded");
        dut.eval(); // Settle low-phase input changes before the sampling edge.
        for (unsigned i = 0; i < count; ++i) {
            if (dut.align_rx_offer) last_rx_offer = now() + 1;
            if (dut.align_tx_load) last_tx_load = now() + 1;
            context.timeInc(1);
            dut.CLK = 1;
            dut.eval();
            tx.push_back(dut.tx_o);
            context.timeInc(1);
            dut.CLK = 0;
            dut.eval();
        }
    }
    void until(unsigned cycle) {
        if (cycle < now()) throw std::logic_error("missed scheduled clock");
        tick(cycle - now());
    }
    void idle_bus() {
        dut.PSEL = 0;
        dut.PENABLE = 0;
        dut.PWRITE = 0;
        dut.PADDR = 0;
        dut.PWDATA = 0;
    }
    void release_reset() {
        idle_bus();
        dut.rx_i = 1;
        tick(3);
        dut.RSTN = 1;
        tick(3);
    }
    void reset() {
        dut.RSTN = 0;
        release_reset();
    }
    void setup(bool write, unsigned addr, unsigned data = 0) {
        dut.PSEL = 1;
        dut.PENABLE = 0;
        dut.PWRITE = write;
        dut.PADDR = addr;
        dut.PWDATA = data;
        tick();
    }
    unsigned complete() {
        dut.PENABLE = 1;
        dut.eval();
        equal("PREADY at ACCESS", dut.PREADY, 1);
        equal("PSLVERR at ACCESS", dut.PSLVERR, 0);
        const unsigned value = dut.PRDATA;
        tick();
        idle_bus();
        return value;
    }
    void write(unsigned addr, unsigned data) { setup(true, addr, data); complete(); }
    unsigned read(unsigned addr) { setup(false, addr); return complete(); }
    void configure_8n1(unsigned divisor) {
        write(LCR, 0x83);
        write(DLL, divisor & 0xff);
        write(DLM, divisor >> 8);
        equal("DLL readback", read(DLL), divisor & 0xff);
        equal("DLM readback", read(DLM), divisor >> 8);
        write(LCR, 0x03);
    }
    void drive_rx(unsigned level, unsigned clocks) {
        dut.rx_i = level;
        tick(clocks);
    }
    void rx_byte(uint8_t byte, unsigned period) {
        drive_rx(0, period);
        for (unsigned bit = 0; bit < 8; ++bit) drive_rx((byte >> bit) & 1, period);
        drive_rx(1, 2 * period); // stop and one idle bit
    }
    unsigned first_tx(uint8_t byte) {
        const unsigned idle = now();
        equal("TX before THR", dut.tx_o, 1);
        write(THR, byte);
        for (unsigned i = 0; i < 8 && dut.tx_o; ++i) tick();
        equal("start after THR", dut.tx_o, 0);
        return next_transition(idle);
    }
    unsigned next_transition(unsigned previous) const {
        for (unsigned i = previous + 1; i <= now(); ++i)
            if (tx[i] != tx[previous]) return i;
        throw std::runtime_error("missing TX transition in recorded window");
    }
    void level(unsigned first, unsigned count, unsigned want) const {
        if (first + count > tx.size()) throw std::logic_error("TX observation window incomplete");
        for (unsigned i = first; i < first + count; ++i) {
            if (tx[i] != want) {
                std::ostringstream msg;
                msg << "tx_o at clock " << i << ": got " << unsigned(tx[i]) << ", expected " << want;
                throw std::runtime_error(msg.str());
            }
        }
    }
    // 8N1 pin contract, measured from the observed start edge. Return the
    // first idle clock after the stop bit; a queued frame can start one clock later.
    unsigned frame(unsigned first, unsigned period, uint8_t byte) const {
        level(first, period + 1, 0);
        unsigned at = first + period + 1;
        for (unsigned bit = 0; bit < 8; ++bit, at += period)
            level(at, period, (byte >> bit) & 1);
        level(at, period, 1);
        return at + period;
    }
};
