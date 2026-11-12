`timescale 1ns/1ps
package apb_uart_uvm_pkg;
    import uvm_pkg::*;
    `include "uvm_macros.svh"
    `uvm_analysis_imp_decl(_apb)
    `uvm_analysis_imp_decl(_tx_start)
    `uvm_analysis_imp_decl(_tx)
    `uvm_analysis_imp_decl(_rx_start)
    `uvm_analysis_imp_decl(_rx)
    `include "uart_types.svh"
    `include "apb_agent.svh"
    `include "uart_agents.svh"
    `include "uart_scoreboard.svh"
    `include "uart_tests.svh"
endpackage
