"""Render a reviewed sequence of source intervals, speeds and stage titles."""
import json
import math
import shutil
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def probe(path):
    result = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format",
                             "-of", "json", str(path)], capture_output=True, check=True,
                            encoding="utf-8", errors="replace")
    return json.loads(result.stdout)


def load_plan(path):
    plan = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    for key in ("input", "output", "font"):
        plan[key] = (ROOT / plan[key]).resolve()
    if not plan["input"].is_relative_to(ROOT / "inputs") or not plan["input"].is_file():
        raise ValueError("输入必须是 inputs/ 内的文件")
    if not plan["output"].is_relative_to(ROOT / "outputs") or plan["output"].suffix != ".mp4":
        raise ValueError("输出必须是 outputs/ 内的 MP4 文件")
    if plan["output"].exists():
        raise ValueError("输出已存在，请递增版本号，不得覆盖")
    if not plan["font"].is_file():
        raise ValueError("标题字体文件不存在")
    info = probe(plan["input"])
    video = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
    if not video or not any(s["codec_type"] == "audio" for s in info["streams"]):
        raise ValueError("输入必须同时包含视频轨和音频轨")
    duration = float(info["format"]["duration"])
    fps = Fraction(video["avg_frame_rate"])
    if not math.isfinite(duration) or duration <= 0 or fps <= 0:
        raise ValueError("源视频的时长或帧率无效")
    if not isinstance(plan["segments"], list) or not plan["segments"]:
        raise ValueError("segments 必须是非空数组")
    durations = []
    for segment in plan["segments"]:
        start, end, speed = (float(segment[k]) for k in ("start", "end", "speed"))
        if not all(math.isfinite(v) for v in (start, end, speed)):
            raise ValueError("片段时间与速度必须为有限数值")
        if not 0 <= start < end <= duration or not 1 <= speed <= 16:
            raise ValueError("片段必须处于源视频范围内，且速度须在 1 到 16 倍之间")
        if not isinstance(segment["title"], str) or not 0 < len(segment["title"].strip()) <= 32:
            raise ValueError("阶段标题须为 1 到 32 个字符")
        if not isinstance(segment["label"], str) or not 0 < len(segment["label"].strip()) <= 16:
            raise ValueError("阶段标签须为 1 到 16 个字符")
        segment.update(start=start, end=end, speed=speed)
        durations.append((end - start) / speed)
    plan.update(fps=str(fps), expected_duration=math.fsum(durations))
    return plan


def render(plan):
    target = plan["output"]
    work = target.parent / "tmp" / target.stem
    work.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(plan["font"], work / "font.ttc")
    parts = []
    for index, segment in enumerate(plan["segments"], 1):
        length = segment["end"] - segment["start"]
        duration = length / segment["speed"]
        (work / "title.utf8").write_text(segment["title"], encoding="utf-8")
        (work / "label.utf8").write_text(segment["label"], encoding="utf-8")
        video = (
            f"setpts=(PTS-STARTPTS)/{segment['speed']},fps={plan['fps']},"
            "drawbox=x=0:y=0:w=iw:h=90:color=0x101820@0.9:t=fill,"
            "drawbox=x=0:y=86:w=iw:h=4:color=0x38bdf8:t=fill,"
            "drawtext=fontfile=font.ttc:textfile=title.utf8:expansion=none:"
            "fontsize=40:fontcolor=white:x=32:y=24,"
            "drawtext=fontfile=font.ttc:textfile=label.utf8:expansion=none:"
            "fontsize=24:fontcolor=0x7dd3fc:x=w-tw-32:y=32"
        )
        speed, tempo = segment["speed"], []
        while speed > 2:
            tempo.append("atempo=2")
            speed /= 2
        audio = ",".join(["asetpts=PTS-STARTPTS", *tempo, f"atempo={speed}",
                          "apad", f"atrim=duration={duration}"])
        part = f"part-{index:02}.mkv"
        print(f"渲染 {index}/{len(plan['segments'])}: {segment['title']} ({duration:g} 秒)", flush=True)
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-n",
                        "-ss", str(segment["start"]), "-t", str(length), "-i", str(plan["input"]),
                        "-map", "0:v:0", "-map", "0:a:0", "-vf", video, "-af", audio,
                        "-t", str(duration), "-c:v", "libx264", "-crf", "23", "-preset", "medium",
                        "-pix_fmt", "yuv420p", "-c:a", "pcm_s16le", part], cwd=work, check=True)
        parts.append(f"file '{part}'")
    (work / "concat.ffconcat").write_text("\n".join(parts) + "\n", encoding="utf-8")
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-n", "-f", "concat",
                    "-safe", "0", "-i", "concat.ffconcat", "-c:v", "copy", "-c:a", "aac",
                    "-b:a", "192k", "-movflags", "+faststart", str(target)], cwd=work, check=True)
    print(f"已渲染: {target}\n计划时长={plan['expected_duration']:g} 秒；下一步运行 validate.sh")


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2:
            raise ValueError("用法: python scripts/render.py <剪辑计划.json>")
        for dependency in ("ffmpeg", "ffprobe"):
            if not shutil.which(dependency):
                raise ValueError(f"缺少依赖: {dependency}")
        render(load_plan(sys.argv[1]))
    except (OSError, ValueError, KeyError, TypeError, ZeroDivisionError, subprocess.CalledProcessError) as error:
        print(f"渲染失败: {error}\n{getattr(error, 'stderr', '') or ''}", file=sys.stderr)
        sys.exit(1)
