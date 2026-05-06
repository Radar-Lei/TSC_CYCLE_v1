from tsc_cycle.hashing import canonical_json, prompt_hash, sample_id, sha256_hex


def test_canonical_json_stable_ordering():
    a = {"b": 2, "a": 1, "nested": {"y": 1, "x": 0}}
    b = {"a": 1, "b": 2, "nested": {"x": 0, "y": 1}}
    assert canonical_json(a) == canonical_json(b)


def test_canonical_json_no_whitespace_unicode():
    s = canonical_json({"k": "中文"})
    assert " " not in s
    assert "中文" in s  # ensure_ascii=False


def test_sample_id_deterministic():
    obj = {"prediction": {"as_of": "2026-04-27", "phase_waits": [{"phase_id": 1}]}}
    assert sample_id(obj) == sample_id(obj)
    assert len(sample_id(obj)) == 64


def test_sample_id_changes_with_input():
    a = {"x": 1}
    b = {"x": 2}
    assert sample_id(a) != sample_id(b)


def test_prompt_hash_includes_model_and_effort():
    p = "hello"
    assert prompt_hash(p, "gpt-5.5", "high") != prompt_hash(p, "gpt-5.5", "low")
    assert prompt_hash(p, "gpt-5.5", "high") != prompt_hash(p, "gpt-5", "high")
    assert prompt_hash(p, "gpt-5.5", "high") == prompt_hash(p, "gpt-5.5", "high")


def test_sha256_hex_known_value():
    # Known SHA-256 vector
    assert sha256_hex("") == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
