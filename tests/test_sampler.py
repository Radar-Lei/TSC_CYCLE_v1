"""分层抽样器单元测试"""

import json
import random
import pytest

from src.glm5.sampler import (
    StratifiedSampler,
    SamplingStats,
    _saturation_bucket,
    sample_training_data,
)


def _make_sample(tl_id: str, saturations: list[float]) -> dict:
    """生成模拟训练样本 dict"""
    return {
        "prompt": f"test prompt for {tl_id}",
        "prediction": {
            "as_of": "2026-01-01 08:00:00",
            "phase_waits": [
                {
                    "phase_id": i,
                    "pred_saturation": sat,
                    "min_green": 5,
                    "max_green": 60,
                    "capacity": 30,
                }
                for i, sat in enumerate(saturations)
            ],
        },
        "state_file": f"outputs/states/test/{tl_id}.xml",
        "metadata": {
            "tl_id": tl_id,
            "sim_time": 100.0,
            "date": "2026-01-01",
            "cycle_count": 1,
        },
    }


@pytest.fixture
def mock_data() -> list[dict]:
    """生成 200 条模拟数据: 5 个 tl_id, 3 个饱和度桶, 分布不均匀"""
    rng = random.Random(123)
    data = []
    tl_ids = ["tl_A", "tl_B", "tl_C", "tl_D", "tl_E"]
    # 不均匀分布: low 多, high 少
    bucket_configs = {
        "low": (0.0, 0.29, 100),   # 100 条 low
        "med": (0.3, 0.69, 70),    # 70 条 med
        "high": (0.7, 1.0, 30),    # 30 条 high
    }
    for bucket_name, (lo, hi, count) in bucket_configs.items():
        for _ in range(count):
            tl_id = rng.choice(tl_ids)
            # 生成 3 个相位的饱和度, 均在桶内
            sats = [rng.uniform(lo, hi) for _ in range(3)]
            data.append(_make_sample(tl_id, sats))
    rng.shuffle(data)
    return data


class TestSaturationBucket:
    """饱和度分桶函数测试"""

    def test_low_bucket(self):
        sample = _make_sample("tl_A", [0.1, 0.2, 0.15])
        assert _saturation_bucket(sample) == "low"

    def test_med_bucket(self):
        sample = _make_sample("tl_A", [0.4, 0.5, 0.6])
        assert _saturation_bucket(sample) == "med"

    def test_high_bucket(self):
        sample = _make_sample("tl_A", [0.8, 0.9, 0.75])
        assert _saturation_bucket(sample) == "high"

    def test_boundary_low_med(self):
        """avg < 0.3 -> low"""
        sample = _make_sample("tl_A", [0.29, 0.29, 0.29])
        assert _saturation_bucket(sample) == "low"

    def test_boundary_med_high(self):
        """avg >= 0.7 -> high"""
        sample = _make_sample("tl_A", [0.71, 0.71, 0.71])
        assert _saturation_bucket(sample) == "high"


class TestStratifiedSampler:
    """分层抽样器测试"""

    def test_sample_count(self, mock_data):
        """抽样 50 条, 结果数量为 50"""
        sampler = StratifiedSampler(seed=42)
        sampled, stats = sampler.sample(mock_data, n=50)
        assert len(sampled) == 50

    def test_all_tl_ids_covered(self, mock_data):
        """抽样结果覆盖所有 5 个 tl_id"""
        sampler = StratifiedSampler(seed=42)
        sampled, stats = sampler.sample(mock_data, n=50)
        tl_ids = {s["metadata"]["tl_id"] for s in sampled}
        assert tl_ids == {"tl_A", "tl_B", "tl_C", "tl_D", "tl_E"}

    def test_all_buckets_covered(self, mock_data):
        """抽样结果中高/中/低饱和度桶均有样本"""
        sampler = StratifiedSampler(seed=42)
        sampled, stats = sampler.sample(mock_data, n=50)
        buckets = {_saturation_bucket(s) for s in sampled}
        assert buckets == {"low", "med", "high"}

    def test_reproducible_with_seed(self, mock_data):
        """固定 seed=42 时两次抽样结果完全相同"""
        sampler1 = StratifiedSampler(seed=42)
        sampled1, _ = sampler1.sample(mock_data, n=50)

        sampler2 = StratifiedSampler(seed=42)
        sampled2, _ = sampler2.sample(mock_data, n=50)

        # 按 prompt 排序后比较
        key = lambda x: x["prompt"] + x["metadata"]["tl_id"]
        assert sorted(sampled1, key=key) == sorted(sampled2, key=key)

    def test_stats_correct(self, mock_data):
        """SamplingStats 中数据与实际一致"""
        sampler = StratifiedSampler(seed=42)
        sampled, stats = sampler.sample(mock_data, n=50)

        assert stats.total_source == len(mock_data)
        assert stats.total_sampled == 50

        # bucket_counts 合计等于总采样数
        assert sum(stats.bucket_counts.values()) == 50

        # tl_id_counts 合计等于总采样数
        assert sum(stats.tl_id_counts.values()) == 50

        # 每个桶都有计数
        for bucket in ["low", "med", "high"]:
            assert stats.bucket_counts.get(bucket, 0) > 0


class TestSampleTrainingData:
    """便捷函数测试"""

    def test_writes_jsonl(self, mock_data, tmp_path):
        """验证 output jsonl 文件正确写入"""
        input_path = tmp_path / "input.jsonl"
        output_path = tmp_path / "output.jsonl"

        # 写入测试数据
        with open(input_path, "w") as f:
            for item in mock_data:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")

        sampled, stats = sample_training_data(
            input_path=str(input_path),
            n=30,
            output_path=str(output_path),
            seed=42,
        )

        assert len(sampled) == 30
        assert output_path.exists()

        # 验证 jsonl 行数
        lines = output_path.read_text().strip().split("\n")
        assert len(lines) == 30

        # 验证每行都是合法 JSON
        for line in lines:
            parsed = json.loads(line)
            assert "metadata" in parsed
            assert "tl_id" in parsed["metadata"]
