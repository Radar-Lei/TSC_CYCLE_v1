from tsc_cycle.v3_gates.memory_budget_v3 import default_seqs, select_max_seq


def test_default_seqs_are_required_measured_candidates():
    assert default_seqs() == [1536, 2048, 2560, 3072, 4096]


def test_select_max_seq_chooses_largest_success_below_strict_threshold():
    results = [
        {"seq": 1536, "status": "ok", "peak_reserved_gb": 60.0},
        {"seq": 2048, "status": "ok", "peak_reserved_gb": 70.0},
        {"seq": 2560, "status": "ok", "peak_reserved_gb": 80.0},
        {"seq": 3072, "status": "ok", "peak_reserved_gb": 84.9},
        {"seq": 4096, "status": "ok", "peak_reserved_gb": 90.0},
    ]

    assert select_max_seq(results) == 3072


def test_select_max_seq_returns_none_when_all_fail_or_hit_threshold():
    results = [
        {"seq": 1536, "status": "oom", "peak_reserved_gb": None},
        {"seq": 2048, "status": "error", "peak_reserved_gb": None},
        {"seq": 2560, "status": "ok", "peak_reserved_gb": 85.0},
        {"seq": 3072, "status": "ok", "peak_reserved_gb": 90.0},
        {"seq": 4096, "status": "ok", "peak_reserved_gb": 100.0},
    ]

    assert select_max_seq(results) is None


def test_select_max_seq_accepts_ok_boolean_for_artifact_compatibility():
    results = [
        {"seq": 1536, "ok": True, "peak_reserved_gb": 84.9},
        {"seq": 2048, "ok": False, "peak_reserved_gb": 10.0},
        {"seq": 2560, "ok": True, "peak_reserved_gb": 90.0},
    ]

    assert select_max_seq(results) == 1536
