`timescale 1ns/1ps
package pulp_uart_pkg;
    import uvm_pkg::*;
    `include "uvm_macros.svh"
    `uvm_analysis_imp_decl(_bus)
    `uvm_analysis_imp_decl(_wire)
    `include "apb_agent.svh"
    `include "serial_agent.svh"
    `include "scoreboard.svh"
    `include "tests.svh"
endpackage
