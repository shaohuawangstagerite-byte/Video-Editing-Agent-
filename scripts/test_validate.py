import contextlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import validate


class ValidateTests(unittest.TestCase):
    def setUp(self):
        output_dir = Path(__file__).resolve().parents[1] / "outputs"
        temporary = tempfile.TemporaryDirectory(prefix="验证 ", dir=output_dir)
        self.folder = Path(temporary.name)
        self.assertTrue(self.folder.resolve().is_relative_to(output_dir.resolve()))
        self.addCleanup(temporary.cleanup)
        self.media = self.folder / "成片 sample.mp4"
        self.media.write_bytes(b"sample")
        self.empty = self.folder / "empty.mp4"
        self.empty.touch()
        self.metadata = {"streams": [{"codec_type": "video"}, {"codec_type": "audio"}],
                         "format": {"duration": "10"}}

    def check(self, status, *fragments, args=None, stdout=None, stderr="", probe_code=0, found=True):
        args = [str(self.media), "--expected-duration", "10"] if args is None else args
        result = subprocess.CompletedProcess("ffprobe", probe_code,
            json.dumps(self.metadata) if stdout is None else stdout, stderr)
        captured = io.StringIO()
        with (patch.object(validate.shutil, "which", return_value="ffprobe" if found else None),
              patch.object(validate.subprocess, "run", return_value=result),
              contextlib.redirect_stdout(captured), contextlib.redirect_stderr(captured)):
            try:
                code = validate.main(args)
            except SystemExit as error:
                code = error.code
        output = captured.getvalue()
        self.assertEqual(code, status, output)
        self.assertIn("PASS" if status == 0 else "FAIL [", output)
        if status == 1:
            self.assertIn(f"路径={args[0]}", output)
        for fragment in fragments:
            self.assertIn(fragment, output)

    def test_valid_and_file_failures(self):
        self.check(0)
        for path in (self.folder / "missing.mp4", self.folder, self.empty):
            with self.subTest(path=path):
                self.check(1, "[文件]", args=[str(path), "--expected-duration", "10"])

    def test_arguments_and_dependency(self):
        base = [str(self.media), "--expected-duration"]
        cases = [[], ["", "--expected-duration", "10"], [str(self.media)], base, base + ["10", "--unknown"],
                 base + ["10", "--expected-duration", "10"]]
        cases += [base + [value] for value in ("", "bad", "NaN", "Infinity", "0", "-1")]
        for args in cases:
            with self.subTest(args=args):
                self.check(2, "[参数]", args=args)
        self.check(2, "[依赖]", "ffprobe", found=False)

    def test_probe_and_metadata_failures(self):
        self.check(1, "[ffprobe]", "7", "probe-specific-error", probe_code=7,
                   stderr="probe-specific-error")
        self.check(1, "[元数据]", "line 1", "column", stdout="{")
        for payload in ([], dict(self.metadata, streams={}), dict(self.metadata, format=[])):
            with self.subTest(payload=payload):
                self.check(1, "[元数据]", stdout=json.dumps(payload))
        for streams, reason in (([], "[视频轨]"), ([{"codec_type": "audio"}], "[视频轨]"),
                                ([{"codec_type": "video"}], "[音频轨]")):
            self.metadata["streams"] = streams
            self.check(1, reason)

    def test_invalid_duration(self):
        for value in (None, "N/A", "bad", "NaN", "Infinity", "0", "-1"):
            with self.subTest(duration=value):
                self.metadata["format"] = {} if value is None else {"duration": value}
                self.check(1, "[时长]")

    def test_exact_duration_boundaries(self):
        for actual, expected, status in (("10", "9.5", 0), ("10", "10.5", 0),
                ("10", "9.499999", 1), ("10", "10.500001", 1), ("1.1", "0.6", 0), ("0.6", "1.1", 0)):
            with self.subTest(expected=expected):
                self.metadata["format"]["duration"] = actual
                fragments = ("[时长误差]", "预期=", "实际=", "误差=", "允许=0.5") if status else ()
                self.check(status, *fragments, args=[str(self.media), "--expected-duration", expected])


if __name__ == "__main__":
    unittest.main()
