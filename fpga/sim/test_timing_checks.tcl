# Run with standalone tclsh. Inputs below are synthetic validation fixtures.
source [file join [file dirname [info script]] .. scripts timing_checks.tcl]
set corners {MIN_fast_1200mv_0c 7_slow_1200mv_0c 7_slow_1200mv_85c}
pulp_require_corners $corners
set cases 1
foreach wrong [list {} [lrange $corners 0 0] [lrange $corners 0 1] [concat $corners extra] \
                    [lreplace $corners 2 2 7_slow_1200mv_0c] [lreplace $corners 0 0 wrong_fast]] {
    if {![catch {pulp_require_corners $wrong}]} { error "Accepted invalid corner list $wrong" }
    incr cases
}
foreach {count slack expected} {
    1 0 1         20 2.375 1       1 1e-3 1       1 -0.001 0
    1 NaN 0       1 Inf 0          1 +Inf 0       1 -Inf 0
    1 1e9999 0    1 invalid 0      1 {} 0         0 1.75 0
    invalid 2 0
} {
    if {[pulp_valid_metric $count $slack] != $expected} { error "Metric fixture ($count,$slack)" }
    incr cases
}
puts "TIMING POLICY PASS cases=$cases (Tcl fixtures for corner sets, path counts and finite slack)"
