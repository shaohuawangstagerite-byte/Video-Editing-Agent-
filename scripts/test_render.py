import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import render

class RenderPlanTests(unittest.TestCase):
    def setUp(self):
        outputs = Path(__file__).resolve().parents[1] / "outputs"
        temporary = tempfile.TemporaryDirectory(prefix="render-test-", dir=outputs)
        self.root = Path(temporary.name).resolve()
        self.assertTrue(self.root.is_relative_to(outputs.resolve()))
        self.addCleanup(temporary.cleanup)
        for directory in ("inputs", "outputs"):
            (self.root / directory).mkdir()
        (self.root / "inputs/source.mp4").write_bytes(b"original")
        (self.root / "outputs/font.ttc").write_bytes(b"font")
        self.path = self.root / "outputs/plan.json"
        self.plan = {"input": "inputs/source.mp4", "output": "outputs/result.mp4",
                     "font": "outputs/font.ttc", "segments": [
            {"start": start, "end": end, "speed": speed, "title": "成果展示", "label": "stage"}
            for start, end, speed in [(119, 122, 1), (16, 34, 3), (34, 78, 8), (78, 107, 1), (114, 122.5, 1)]]}
        metadata = {"streams": [{"codec_type": "video", "avg_frame_rate": "10/1",
                                 "width": 1736, "height": 1080}, {"codec_type": "audio"}], "format": {"duration": "126.6"}}
        for patcher in (patch.object(render, "ROOT", self.root),
                        patch.object(render, "probe", return_value=metadata)):
            patcher.start()
            self.addCleanup(patcher.stop)

    def load(self, segment=None, **changes):
        payload = dict(self.plan, **changes)
        if segment is not None:
            payload["segments"] = [dict(self.plan["segments"][0], **segment)]
        self.path.write_text(json.dumps(payload), encoding="utf-8")
        return render.load_plan(self.path)

    def test_confirmed_plan_duration_paths_and_titles(self):
        result = self.load()
        self.assertAlmostEqual(result["expected_duration"], 52.0)
        for key in ("input", "output", "font"):
            self.assertEqual(result[key], self.root / self.plan[key])
        self.assertEqual([s["title"] for s in result["segments"]], ["成果展示"] * 5)
        self.assertEqual((self.root / "inputs/source.mp4").read_bytes(), b"original")

    def test_invalid_segments(self):
        cases = [{"speed": x} for x in (0, 0.5, 17, float("nan"), float("inf"))]
        cases += [{"start": -1}, {"end": 127}, {"start": 123}, {"end": 119},
                  {"start": float("nan")}, {"end": float("inf")}, {"title": ""}]
        for segment in cases:
            with self.subTest(segment=segment), self.assertRaises(ValueError):
                self.load(segment)

    def test_existing_or_unconfined_output(self):
        (self.root / "outputs/result.mp4").write_bytes(b"keep")
        for output in ("outputs/result.mp4", "inputs/other.mp4", "../escape.mp4"):
            with self.subTest(output=output), self.assertRaises(ValueError):
                self.load(output=output)
        self.assertEqual((self.root / "outputs/result.mp4").read_bytes(), b"keep")
if __name__ == "__main__":
    unittest.main()
