from tsc_cycle.constraint_lint import Violation, is_trivial, validate


def _input(phases):
    return {"prediction": {"phase_waits": [
        {"phase_id": pid, "min_green": mn, "max_green": mx,
         "pred_wait": 1.0, "pred_saturation": 0.05, "capacity": 30}
        for pid, mn, mx in phases
    ]}}


def test_valid_output():
    inp = _input([(1, 50, 80), (2, 20, 45)])
    out = {"1": 60, "2": 30}
    res = validate(inp, out)
    assert res.ok
    assert res.violations == []


def test_below_min():
    inp = _input([(1, 50, 80)])
    res = validate(inp, {"1": 40})
    assert not res.ok
    assert res.violations[0]["kind"] == Violation.BELOW_MIN.value


def test_above_max():
    inp = _input([(1, 50, 80)])
    res = validate(inp, {"1": 100})
    assert not res.ok
    assert res.violations[0]["kind"] == Violation.ABOVE_MAX.value


def test_not_integer():
    inp = _input([(1, 50, 80)])
    res = validate(inp, {"1": 60.5})
    assert not res.ok
    assert res.violations[0]["kind"] == Violation.NOT_INTEGER.value


def test_float_integer_accepted():
    inp = _input([(1, 50, 80)])
    res = validate(inp, {"1": 60.0})
    assert res.ok


def test_phase_mismatch_extra():
    inp = _input([(1, 50, 80)])
    res = validate(inp, {"1": 60, "2": 30})
    assert not res.ok
    assert res.violations[0]["kind"] == Violation.PHASE_MISMATCH.value


def test_phase_mismatch_missing():
    inp = _input([(1, 50, 80), (2, 20, 45)])
    res = validate(inp, {"1": 60})
    assert not res.ok
    assert res.violations[0]["kind"] == Violation.PHASE_MISMATCH.value


def test_phase_order_violation():
    inp = _input([(1, 50, 80), (2, 20, 45)])
    out = {"2": 30, "1": 60}  # wrong order
    res = validate(inp, out)
    assert not res.ok
    assert any(v["kind"] == Violation.PHASE_ORDER.value for v in res.violations)


def test_not_dict():
    inp = _input([(1, 50, 80)])
    res = validate(inp, [60])
    assert not res.ok
    assert res.violations[0]["kind"] == Violation.NOT_DICT.value


def test_bool_rejected_as_int():
    inp = _input([(1, 50, 80)])
    res = validate(inp, {"1": True})
    assert not res.ok
    assert res.violations[0]["kind"] == Violation.NOT_INTEGER.value


def test_is_trivial():
    assert is_trivial(_input([(1, 50, 50), (2, 30, 30)]))
    assert not is_trivial(_input([(1, 50, 80)]))
