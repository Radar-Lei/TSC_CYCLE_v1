import argparse
import datetime as dt
from decimal import Decimal, ROUND_DOWN
import json
import math
import random
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from xml.sax.saxutils import escape


@dataclass(frozen=True)
class TemplateVehicle:
    depart: float
    base_attrs: Dict[str, str]
    children_xml: str


def _local_tag(tag: str) -> str:
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def _parse_float(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _load_profile(path: Optional[str]) -> Optional[List[float]]:
    if not path:
        return None
    profile_path = Path(path)
    data = json.loads(profile_path.read_text(encoding="utf-8"))
    if not isinstance(data, list) or len(data) != 24:
        raise ValueError(f"profile 必须是长度为 24 的数组：{profile_path}")
    result: List[float] = []
    for i, v in enumerate(data):
        if not isinstance(v, (int, float)):
            raise ValueError(f"profile[{i}] 不是数字：{v!r}")
        if v < 0:
            raise ValueError(f"profile[{i}] 不能为负：{v!r}")
        result.append(float(v))
    return result


def parse_template_rou(input_path: str) -> Tuple[Dict[str, str], List[str], List[TemplateVehicle], float]:
    tree = ET.parse(input_path)
    root = tree.getroot()
    if _local_tag(root.tag) != "routes":
        raise ValueError(f"根节点不是 <routes>：{root.tag}")

    static_children_xml: List[str] = []
    template_vehicles: List[TemplateVehicle] = []
    max_depart = 0.0

    for child in list(root):
        tag = _local_tag(child.tag)
        if tag == "vehicle":
            depart = _parse_float(child.attrib.get("depart"))
            if depart is None:
                continue
            max_depart = max(max_depart, depart)
            base_attrs = dict(child.attrib)
            base_attrs.pop("id", None)
            base_attrs.pop("depart", None)

            fragments: List[str] = []
            for sub in list(child):
                fragments.append(ET.tostring(sub, encoding="unicode"))
            template_vehicles.append(
                TemplateVehicle(depart=depart, base_attrs=base_attrs, children_xml="".join(fragments))
            )
        else:
            static_children_xml.append(ET.tostring(child, encoding="unicode"))

    if not template_vehicles:
        raise ValueError("未在输入 .rou.xml 中解析到可用的 <vehicle depart=\"...\">")

    template_span = max_depart if max_depart > 0 else 3600.0
    return dict(root.attrib), static_children_xml, template_vehicles, template_span


def default_weekday_profile() -> List[float]:
    return [
        0.05, 0.04, 0.03, 0.03, 0.04, 0.08,  # 0-5
        0.50, 1.40, 1.60, 1.10, 0.95, 0.90,  # 6-11
        0.85, 0.90, 0.95, 1.05, 1.40, 1.70,  # 12-17
        1.30, 0.90, 0.70, 0.40, 0.20, 0.10,  # 18-23
    ]


def default_weekend_profile() -> List[float]:
    return [
        0.06, 0.05, 0.04, 0.04, 0.05, 0.06,  # 0-5
        0.10, 0.20, 0.45, 0.70, 0.95, 1.05,  # 6-11
        1.10, 1.05, 1.00, 0.95, 0.95, 0.90,  # 12-17
        0.85, 0.80, 0.65, 0.45, 0.25, 0.12,  # 18-23
    ]


def _day_factor(rng: random.Random, sigma: float = 0.12) -> float:
    mu = -(sigma * sigma) / 2.0
    return rng.lognormvariate(mu, sigma)


def _indent_fragment(fragment: str, indent: str) -> str:
    lines = fragment.splitlines()
    if not lines:
        return ""
    return "\n".join(indent + line if line.strip() else line for line in lines) + "\n"


def _build_root_open_tag(root_attrib: Dict[str, str]) -> str:
    tmp = ET.Element("routes", attrib=root_attrib)
    s = ET.tostring(tmp, encoding="unicode")
    if not s.endswith("/>"):
        raise RuntimeError("无法生成 <routes ...> 开始标签")
    return s[:-2] + ">"


def _format_depart_2dp(depart: float) -> str:
    d = Decimal(str(max(0.0, float(depart))))
    return format(d.quantize(Decimal("0.01"), rounding=ROUND_DOWN), "f")


def _vehicle_open_tag(vid: str, depart: float, base_attrs: Dict[str, str]) -> str:
    parts = [f'    <vehicle id="{escape(vid)}" depart="{_format_depart_2dp(depart)}"']
    for k, v in base_attrs.items():
        parts.append(f' {k}="{escape(v)}"')
    return "".join(parts) + ">"


def validate_rou(
    *,
    rou_path: str,
    hour_seconds: int,
    expect_hours: Optional[int] = None,
    quiet: bool = False,
) -> Dict[str, object]:
    path = Path(rou_path)
    prev_depart: Optional[float] = None
    prev_seq: Optional[int] = None
    vehicle_count = 0
    hourly_counts: Dict[int, int] = {}

    context = ET.iterparse(path, events=("start",))
    _, root = next(context)
    if _local_tag(root.tag) != "routes":
        raise ValueError(f"输出文件根节点不是 <routes>：{root.tag}")

    for event, elem in context:
        if event != "start":
            continue
        if _local_tag(elem.tag) != "vehicle":
            continue

        depart = _parse_float(elem.attrib.get("depart"))
        if depart is None:
            continue

        if prev_depart is not None and depart + 1e-9 < prev_depart:
            raise ValueError(f"depart 非单调：{depart} < {prev_depart}")
        prev_depart = depart

        vid = elem.attrib.get("id", "")
        seq = None
        if vid.startswith("gen_"):
            try:
                seq = int(vid.rsplit("_", 1)[1])
            except Exception:
                seq = None
        if seq is not None:
            if prev_seq is not None and seq <= prev_seq:
                raise ValueError(f"vehicle id 序号非递增：{seq} <= {prev_seq}")
            prev_seq = seq

        h = int(depart // float(hour_seconds))
        hourly_counts[h] = hourly_counts.get(h, 0) + 1
        vehicle_count += 1
        if vehicle_count % 200000 == 0 and not quiet:
            print(f"[validate] parsed_vehicles={vehicle_count}")

    if expect_hours is not None:
        present_hours = {k for k, v in hourly_counts.items() if v > 0}
        if present_hours and (max(present_hours) + 1 > expect_hours):
            raise ValueError(f"hour index 超出预期：max_hour={max(present_hours)} expect_hours={expect_hours}")

    return {
        "vehicles": vehicle_count,
        "hourly_counts": hourly_counts,
    }


def generate_month(
    *,
    input_path: str,
    output_path: str,
    start_date: dt.date,
    days: int,
    seed: int,
    hour_seconds: int,
    weekday_profile: List[float],
    weekend_profile: List[float],
    jitter_seconds: float,
    verbose: bool,
    validate_output: bool,
) -> Dict[str, object]:
    root_attrib, static_children_xml, template_vehicles, template_span = parse_template_rou(input_path)

    rng = random.Random(seed)
    scale = float(hour_seconds) / float(template_span)
    template_events: List[Tuple[float, TemplateVehicle]] = []
    for tv in template_vehicles:
        t = max(0.0, tv.depart) * scale
        if t >= hour_seconds:
            t = math.nextafter(float(hour_seconds), 0.0)
        template_events.append((t, tv))

    daily_factors: Dict[dt.date, float] = {}
    for i in range(days):
        d = start_date + dt.timedelta(days=i)
        daily_factors[d] = _day_factor(rng)

    total_generated = 0
    hourly_counts: List[int] = [0] * (days * 24)

    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with out_path.open("w", encoding="utf-8", newline="\n") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write(_build_root_open_tag(root_attrib) + "\n")
        for frag in static_children_xml:
            f.write(_indent_fragment(frag, "    "))

        vehicle_seq = 0
        total_seconds = float(days * 24 * hour_seconds)
        for day_index in range(days):
            current_date = start_date + dt.timedelta(days=day_index)
            is_weekend = current_date.weekday() >= 5
            profile = weekend_profile if is_weekend else weekday_profile
            day_mul = daily_factors[current_date]

            for hour in range(24):
                hour_start = (day_index * 24 + hour) * hour_seconds
                hour_mul = profile[hour] * day_mul

                n_full = int(math.floor(hour_mul))
                frac = hour_mul - float(n_full)
                shift_frac = rng.uniform(0.0, float(hour_seconds))

                hour_events: List[Tuple[float, TemplateVehicle]] = []
                for r in range(n_full):
                    shift = rng.uniform(0.0, float(hour_seconds))
                    for t, tv in template_events:
                        depart = (t + shift) % float(hour_seconds)
                        depart += rng.uniform(-jitter_seconds, jitter_seconds)
                        if depart < 0.0:
                            depart = 0.0
                        if depart >= float(hour_seconds):
                            depart = math.nextafter(float(hour_seconds), 0.0)
                        hour_events.append((float(hour_start) + depart, tv))

                if frac > 1e-9:
                    for t, tv in template_events:
                        if rng.random() < frac:
                            depart = (t + shift_frac) % float(hour_seconds)
                            depart += rng.uniform(-jitter_seconds, jitter_seconds)
                            if depart < 0.0:
                                depart = 0.0
                            if depart >= float(hour_seconds):
                                depart = math.nextafter(float(hour_seconds), 0.0)
                            hour_events.append((float(hour_start) + depart, tv))

                hour_events.sort(key=lambda x: x[0])
                hourly_counts[day_index * 24 + hour] = len(hour_events)
                total_generated += len(hour_events)

                for depart_abs, tv in hour_events:
                    vehicle_seq += 1
                    vid = f"gen_{current_date.isoformat()}_{hour:02d}_{vehicle_seq:08d}"
                    if depart_abs >= total_seconds:
                        depart_abs = math.nextafter(total_seconds, 0.0)
                    f.write(_vehicle_open_tag(vid, depart_abs, tv.base_attrs) + "\n")
                    if tv.children_xml.strip():
                        f.write(_indent_fragment(tv.children_xml, "        "))
                    f.write("    </vehicle>\n")

        f.write("</routes>\n")

    if verbose:
        print(f"input={input_path}")
        print(f"output={str(out_path)}")
        print(f"days={days} start_date={start_date.isoformat()} hour_seconds={hour_seconds}")
        print(f"template_vehicles={len(template_vehicles)} template_span={template_span:.2f}s scale={scale:.6f}")
        print(f"generated_vehicles={total_generated}")
        print("hourly_counts_first_48h=" + ",".join(str(x) for x in hourly_counts[:48]))

        totals_by_day = []
        for i in range(days):
            totals_by_day.append(sum(hourly_counts[i * 24 : (i + 1) * 24]))
        print(f"daily_total_min={min(totals_by_day)} max={max(totals_by_day)} avg={sum(totals_by_day)/len(totals_by_day):.1f}")

    validation: Optional[Dict[str, object]] = None
    if validate_output:
        validation = validate_rou(
            rou_path=str(out_path),
            hour_seconds=hour_seconds,
            expect_hours=days * 24,
            quiet=not verbose,
        )
        if verbose:
            print(f"validate_ok vehicles={validation['vehicles']}")

    return {
        "input": input_path,
        "output": str(out_path),
        "days": days,
        "start_date": start_date.isoformat(),
        "hour_seconds": hour_seconds,
        "template_vehicles": len(template_vehicles),
        "template_span": template_span,
        "generated_vehicles": total_generated,
        "hourly_counts": hourly_counts,
        "validation": validation,
    }


def generate_daily_files(
    *,
    input_path: str,
    output_dir: str,
    start_date: dt.date,
    days: int,
    seed: int,
    hour_seconds: int,
    weekday_profile: List[float],
    weekend_profile: List[float],
    jitter_seconds: float,
    verbose: bool,
    validate_output: bool,
) -> Dict[str, object]:
    root_attrib, static_children_xml, template_vehicles, template_span = parse_template_rou(input_path)

    rng = random.Random(seed)
    scale = float(hour_seconds) / float(template_span)
    template_events: List[Tuple[float, TemplateVehicle]] = []
    for tv in template_vehicles:
        t = max(0.0, tv.depart) * scale
        if t >= hour_seconds:
            t = math.nextafter(float(hour_seconds), 0.0)
        template_events.append((t, tv))

    daily_factors: Dict[dt.date, float] = {}
    for i in range(days):
        d = start_date + dt.timedelta(days=i)
        daily_factors[d] = _day_factor(rng)

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    outputs: List[str] = []
    total_generated = 0
    totals_by_day: List[int] = []
    validations: Dict[str, Dict[str, object]] = {}

    for day_index in range(days):
        current_date = start_date + dt.timedelta(days=day_index)
        is_weekend = current_date.weekday() >= 5
        profile = weekend_profile if is_weekend else weekday_profile
        day_mul = daily_factors[current_date]

        output_path = out_dir / f"{Path(input_path).stem}_{current_date.isoformat()}.rou.xml"
        outputs.append(str(output_path))

        daily_total = 0
        hourly_counts: List[int] = [0] * 24

        with output_path.open("w", encoding="utf-8", newline="\n") as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
            f.write(_build_root_open_tag(root_attrib) + "\n")
            for frag in static_children_xml:
                f.write(_indent_fragment(frag, "    "))

            vehicle_seq = 0
            day_seconds = float(24 * hour_seconds)
            for hour in range(24):
                hour_start = hour * hour_seconds
                hour_mul = profile[hour] * day_mul

                n_full = int(math.floor(hour_mul))
                frac = hour_mul - float(n_full)
                shift_frac = rng.uniform(0.0, float(hour_seconds))

                hour_events: List[Tuple[float, TemplateVehicle]] = []
                for r in range(n_full):
                    shift = rng.uniform(0.0, float(hour_seconds))
                    for t, tv in template_events:
                        depart = (t + shift) % float(hour_seconds)
                        depart += rng.uniform(-jitter_seconds, jitter_seconds)
                        if depart < 0.0:
                            depart = 0.0
                        if depart >= float(hour_seconds):
                            depart = math.nextafter(float(hour_seconds), 0.0)
                        hour_events.append((float(hour_start) + depart, tv))

                if frac > 1e-9:
                    for t, tv in template_events:
                        if rng.random() < frac:
                            depart = (t + shift_frac) % float(hour_seconds)
                            depart += rng.uniform(-jitter_seconds, jitter_seconds)
                            if depart < 0.0:
                                depart = 0.0
                            if depart >= float(hour_seconds):
                                depart = math.nextafter(float(hour_seconds), 0.0)
                            hour_events.append((float(hour_start) + depart, tv))

                hour_events.sort(key=lambda x: x[0])
                hourly_counts[hour] = len(hour_events)
                daily_total += len(hour_events)
                total_generated += len(hour_events)

                for depart_abs, tv in hour_events:
                    vehicle_seq += 1
                    vid = f"gen_{current_date.isoformat()}_{hour:02d}_{vehicle_seq:08d}"
                    if depart_abs >= day_seconds:
                        depart_abs = math.nextafter(day_seconds, 0.0)
                    f.write(_vehicle_open_tag(vid, depart_abs, tv.base_attrs) + "\n")
                    if tv.children_xml.strip():
                        f.write(_indent_fragment(tv.children_xml, "        "))
                    f.write("    </vehicle>\n")

            f.write("</routes>\n")

        totals_by_day.append(daily_total)

        validation: Optional[Dict[str, object]] = None
        if validate_output:
            validation = validate_rou(
                rou_path=str(output_path),
                hour_seconds=hour_seconds,
                expect_hours=24,
                quiet=not verbose,
            )
            validations[current_date.isoformat()] = validation

        if verbose:
            print(f"[day] date={current_date.isoformat()} output={output_path.name} vehicles={daily_total}")
            print("      hourly_counts=" + ",".join(str(x) for x in hourly_counts))

    if verbose:
        print(f"input={input_path}")
        print(f"output_dir={str(out_dir)}")
        print(f"days={days} start_date={start_date.isoformat()} hour_seconds={hour_seconds}")
        print(f"template_vehicles={len(template_vehicles)} template_span={template_span:.2f}s scale={scale:.6f}")
        print(f"generated_vehicles={total_generated}")
        print(
            f"daily_total_min={min(totals_by_day)} max={max(totals_by_day)} avg={sum(totals_by_day)/len(totals_by_day):.1f}"
        )

    return {
        "input": input_path,
        "output_dir": str(out_dir),
        "outputs": outputs,
        "days": days,
        "start_date": start_date.isoformat(),
        "hour_seconds": hour_seconds,
        "template_vehicles": len(template_vehicles),
        "template_span": template_span,
        "generated_vehicles": total_generated,
        "totals_by_day": totals_by_day,
        "validations": validations if validate_output else None,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="将一个小时级别的 SUMO .rou.xml 扩展为一个月尺度（含早晚高峰/周末差异），或按天拆分输出。"
    )
    p.add_argument("--input", required=True, help="输入 .rou.xml 路径")
    p.add_argument("--output", default=None, help="输出 .rou.xml 路径（默认在同目录生成 *_month.rou.xml）")
    p.add_argument("--split-by-day", action="store_true", help="按天拆分输出（每天一个 .rou.xml）")
    p.add_argument(
        "--output-dir",
        default=None,
        help="按天输出目录（开启 --split-by-day 时生效，默认在同目录生成 <stem>_daily/）",
    )
    p.add_argument("--start-date", default="2026-01-01", help="起始日期 YYYY-MM-DD（默认 2026-01-01）")
    p.add_argument("--days", type=int, default=30, help="生成天数（默认 30）")
    p.add_argument("--seed", type=int, default=42, help="随机种子（默认 42）")
    p.add_argument("--hour-seconds", type=int, default=3600, help="每小时秒数（默认 3600）")
    p.add_argument("--jitter-seconds", type=float, default=2.0, help="发车时间扰动（秒，默认 2.0）")
    p.add_argument("--weekday-profile", default=None, help="工作日 24 小时倍数 profile（JSON 数组文件）")
    p.add_argument("--weekend-profile", default=None, help="周末 24 小时倍数 profile（JSON 数组文件）")
    p.add_argument("--validate", action="store_true", help="生成后对输出文件做 XML/单调性校验（较耗时）")
    p.add_argument("--quiet", action="store_true", help="不输出统计摘要")
    return p


def main(argv: List[str]) -> int:
    args = build_arg_parser().parse_args(argv)

    input_path = str(Path(args.input))
    ip = Path(input_path)
    output_path = args.output
    if not output_path:
        output_path = str(ip.with_name(ip.stem + "_month.rou.xml"))

    start_date = dt.date.fromisoformat(args.start_date)
    days = int(args.days)
    if days <= 0:
        raise ValueError("--days 必须为正整数")

    weekday_profile = _load_profile(args.weekday_profile) or default_weekday_profile()
    weekend_profile = _load_profile(args.weekend_profile) or default_weekend_profile()

    if bool(args.split_by_day):
        output_dir = args.output_dir
        if not output_dir:
            output_dir = str(ip.parent / f"{ip.stem}_daily")
        generate_daily_files(
            input_path=input_path,
            output_dir=output_dir,
            start_date=start_date,
            days=days,
            seed=int(args.seed),
            hour_seconds=int(args.hour_seconds),
            weekday_profile=weekday_profile,
            weekend_profile=weekend_profile,
            jitter_seconds=float(args.jitter_seconds),
            verbose=not bool(args.quiet),
            validate_output=bool(args.validate),
        )
    else:
        generate_month(
            input_path=input_path,
            output_path=output_path,
            start_date=start_date,
            days=days,
            seed=int(args.seed),
            hour_seconds=int(args.hour_seconds),
            weekday_profile=weekday_profile,
            weekend_profile=weekend_profile,
            jitter_seconds=float(args.jitter_seconds),
            verbose=not bool(args.quiet),
            validate_output=bool(args.validate),
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
