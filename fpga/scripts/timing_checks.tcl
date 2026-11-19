# Quartus 25.1std / EP4CE115F29C7 timing criteria, expressed in plain Tcl.
proc pulp_require_corners {names} {
    set expected {7_slow_1200mv_85c 7_slow_1200mv_0c MIN_fast_1200mv_0c}
    if {[lsort $names] ne [lsort $expected]} {
        error "Expected operating conditions $expected, got $names"
    }
}

proc pulp_valid_metric {count slack} {
    if {![string is integer -strict $count] || $count < 1 || ![string is double -strict $slack]} {
        return 0
    }
    if {[catch {expr {double($slack) >= 0.0 && double($slack) < Inf}} valid]} {
        return 0
    }
    return $valid
}

proc pulp_require_clean_feedback {summary_rows} {
    foreach kind {loops latches} {
        set matches [lsearch -all -inline -exact -index 0 $summary_rows $kind]
        if {[llength $matches] != 1 || [lindex $matches 0 1] ne "0"} {
            error "check_timing $kind expected one row with zero issues, got $matches"
        }
    }
}
