"""Validate output media against the project's technical acceptance rules."""
import json
import shutil
import subprocess
import sys
from decimal import Decimal, DecimalException
from pathlib import Path


def positive_seconds(value):
    number = Decimal(str(value))
    if not number.is_finite() or number <= 0:
        raise ValueError("时长必须为有限正数")
    return number


def main(argv):
    target = argv[0] if argv else "<未提供>"

    def fail(check, reason, code=1):
        print(f"FAIL [{check}] 路径={target}: {reason}", file=sys.stderr)
        raise SystemExit(code)

    if len(argv) != 3 or not target or argv[1] != "--expected-duration":
        fail("参数", "用法: bash scripts/validate.sh <输出路径> --expected-duration <秒>", 2)
    try:
        expected = positive_seconds(argv[2])
    except (DecimalException, ValueError) as exc:
        fail("参数", f"--expected-duration={argv[2]!r} 必须为有限正数（秒）: {exc}", 2)
    probe = shutil.which("ffprobe")
    if not probe:
        fail("依赖", "缺少 ffprobe，请将其加入 PATH", 2)
    path = Path(target).absolute()
    try:
        if not path.exists():
            fail("文件", "路径不存在，预期为非空普通文件")
        if not path.is_file():
            fail("文件", "路径不是普通文件")
        if path.stat().st_size == 0:
            fail("文件", "实际大小=0 字节，预期大小>0 字节")
    except (OSError, ValueError) as exc:
        fail("文件", f"无法读取文件: {exc}")
    try:
        result = subprocess.run(
            [probe, "-v", "error", "-show_entries", "stream=codec_type:format=duration",
             "-of", "json", str(path)], capture_output=True, encoding="utf-8", errors="replace",
        )
    except OSError as exc:
        fail("依赖", f"无法启动 ffprobe: {exc}", 2)
    if result.returncode != 0:
        fail("ffprobe", f"退出码={result.returncode}: {result.stderr.strip() or '无 stderr'}")
    try:
        metadata = json.loads(result.stdout)
        if not isinstance(metadata, dict):
            raise ValueError("元数据顶层必须为 JSON 对象")
        streams, container = metadata.get("streams", []), metadata.get("format", {})
        if not isinstance(streams, list) or not all(isinstance(s, dict) for s in streams):
            raise ValueError("streams 必须为流对象数组")
        if not isinstance(container, dict):
            raise ValueError("format 必须为对象")
    except (ValueError, TypeError) as exc:
        fail("元数据", f"无法解析 ffprobe 元数据: {exc}")
    types = [stream.get("codec_type") for stream in streams]
    for kind, label in (("video", "视频轨"), ("audio", "音频轨")):
        if kind not in types:
            fail(label, f"预期至少一条 {kind} 流，实际轨道类型={types}")
    raw_duration = container.get("duration")
    try:
        actual = positive_seconds(raw_duration)
    except (DecimalException, ValueError) as exc:
        fail("时长", f"format.duration={raw_duration!r} 必须为有限正数（秒）: {exc}")
    try:
        difference = abs(actual - expected)
    except DecimalException as exc:
        fail("时长误差", f"无法计算误差，预期={expected}，实际={actual}: {exc}")
    detail = f"预期={expected} 秒，实际={actual} 秒，误差={difference} 秒，允许=0.5 秒"
    if difference > Decimal("0.5"):
        fail("时长误差", detail)
    print(f"PASS 路径={target}: 文件非空、可解析、音视频轨齐全；{detail}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
