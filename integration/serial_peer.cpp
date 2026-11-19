// PC-side serial peer for the board top. Only the external DE2-115 pins are driven.
#include "VBoard.h"
#include <cstdint>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

constexpr uint64_t clock_hz = 50000000;
constexpr uint64_t baud = 115200;

class SerialPeer {
    VBoard board;
    char parity;
    uint64_t cycle = 0, start = 0, bit_remainder = 0;
    bool receiving = false, previous = true;
    unsigned slot = 0, value = 0, ones = 0;
    std::vector<unsigned> received;

    void sample_tx() {
        const bool tx = board.GPIO_UART_TX;
        if (!receiving && previous && !tx) {
            receiving = true;
            start = cycle;
            slot = value = ones = 0;
        }
        previous = tx;
        // Sample at the middle of each external PC bit, independent of the DUT divisor.
        const auto center = ((2 * slot + 1) * clock_hz + baud) / (2 * baud);
        if (!receiving || cycle - start != center) return;
        if (slot == 0) {
            if (tx) throw std::runtime_error("invalid start");
        } else if (slot <= 8) {
            if (tx) value |= 1u << (slot - 1);
            ones += tx;
        } else if (slot == 9 && parity != 'N') {
            if (tx != ((ones % 2) ^ (parity == 'O')))
                throw std::runtime_error("wrong wire parity");
        } else {
            if (!tx) throw std::runtime_error("invalid stop");
            received.push_back(value);
            receiving = false;
        }
        ++slot;
    }

    void ticks(uint64_t count) {
        for (uint64_t i = 0; i < count; ++i) {
            board.CLOCK_50 = 0;
            board.eval();
            board.CLOCK_50 = 1;
            board.eval();
            ++cycle;
            sample_tx();
        }
    }

    void send_bit(bool bit) {
        board.GPIO_UART_RX = bit;
        bit_remainder += clock_hz;
        ticks(bit_remainder / baud);
        bit_remainder %= baud;
    }

public:
    explicit SerialPeer(char mode) : parity(mode) {
        if (mode != 'N' && mode != 'E' && mode != 'O')
            throw std::runtime_error("use N, E or O");
        board.GPIO_UART_RX = 1;
        board.KEY = 2;  // KEY0 reset asserted, KEY1 released.
        board.SW = (1u << 17) | ((mode != 'N') << 14) | ((mode == 'E') << 15);
        ticks(40);
        board.KEY = 3;
        ticks(25000);
        if (!(board.LEDG & 1)) throw std::runtime_error("board init LED stayed low");
    }

    void write_wire(unsigned byte) {
        send_bit(false);
        unsigned ones_in_byte = 0;
        for (unsigned i = 0; i != 8; ++i) {
            const bool bit = (byte >> i) & 1u;
            send_bit(bit);
            ones_in_byte += bit;
        }
        if (parity != 'N') send_bit((ones_in_byte % 2) ^ (parity == 'O'));
        send_bit(true);
    }

    void key(unsigned byte) {
        board.SW = (board.SW & ~255u) | byte;
        ticks(50010);
        board.KEY = 1;
        ticks(550000);
        board.KEY = 3;
        ticks(550000);
    }

    void set_echo(bool enabled) {
        const unsigned mask = 1u << 17;
        board.SW = (board.SW & ~mask) | (enabled ? mask : 0u);
        ticks(16);
    }

    void finish_transaction(size_t length) {
        board.GPIO_UART_RX = 1;
        ticks(20000 + 6000 * length);
        std::ostringstream line;
        line << "RX " << std::hex << std::setfill('0');
        for (auto byte : received) line << std::setw(2) << byte;
        std::cout << line.str() << std::endl;
        received.clear();
    }
};

int main(int argc, char** argv) {
    try {
        if (argc != 2 || std::string(argv[1]).size() != 1)
            throw std::runtime_error("expected parity mode");
        SerialPeer peer(argv[1][0]);
        std::cout << "READY" << std::endl;
        std::string line;
        while (std::getline(std::cin, line)) {
            std::istringstream input(line);
            std::string command, hex;
            input >> command >> hex;
            if (command == "echo" && (hex == "0" || hex == "1")) {
                peer.set_echo(hex == "1");
                std::cout << "OK" << std::endl;
                continue;
            }
            if ((command != "wire" && command != "key") || hex.empty() ||
                hex.size() % 2 || hex.find_first_not_of("0123456789abcdefABCDEF") != std::string::npos ||
                (command == "key" && hex.size() != 2))
                throw std::runtime_error("expected wire HEX or key BYTE");
            for (size_t offset = 0; offset < hex.size(); offset += 2) {
                auto byte = std::stoul(hex.substr(offset, 2), nullptr, 16);
                if (command == "key") peer.key(byte);
                else peer.write_wire(byte);
            }
            peer.finish_transaction(hex.size() / 2);
        }
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << std::endl;
        return 1;
    }
}
