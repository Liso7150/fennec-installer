import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = (ROOT / "android" / "termux-setup.sh").read_text(encoding="utf-8")


class TermuxWizardTests(unittest.TestCase):
    """The phone wizard is a shell script, so its contract is pinned as text.

    Nothing on this machine can run Termux, which makes the script the one wizard whose
    claims about ports, binaries and the engine's model shape could silently drift from
    the rest of the suite.
    """

    def start_script(self):
        """The open-fennec.sh body the wizard writes, with the heredoc escapes undone."""
        body = re.search(r"cat > \"\$ROOT/open-fennec\.sh\" <<EOF\n(.*?)\nEOF", SCRIPT, re.S)
        self.assertIsNotNone(body, "the wizard no longer writes open-fennec.sh")
        return body.group(1).replace('\\"', '"').replace("\\$", "$")

    def test_the_core_is_the_front_door_and_rust_is_optional_auxiliary(self):
        start = self.start_script()
        self.assertIn('CORE_AGENT="$PREFIX/bin/fennec-agent"', start)
        self.assertIn('"$CORE_AGENT" serve --host 127.0.0.1 --port 8787 &', start)
        self.assertIn('RUST_AGENT="$ROOT/suite/fennec-coding-agent/target/release/fennec-agent"', start)
        self.assertIn('if [ -x "$RUST_AGENT" ]; then', start)
        self.assertIn('FENNEC_AGENT_ADDR=127.0.0.1:8788 "$RUST_AGENT" &', start)
        self.assertIn('termux-open-url "http://127.0.0.1:8787/"', start)
        self.assertIn('http://127.0.0.1:8787/api/capabilities', start)
        self.assertIn('X-Fennec-Client: 1', start)
        self.assertNotIn("$PORT", start)
        self.assertNotIn("for candidate", start)
        self.assertNotIn("/api/health", start)
        self.assertNotIn("npm", SCRIPT)

    def test_the_capability_gate_requires_every_supervised_feature(self):
        start = self.start_script()
        checker = re.search(r"python -c '([^']+)'", start, re.S)
        self.assertIsNotNone(checker, "the readiness gate no longer validates capabilities JSON")
        required = {"supervised-agent", "tool-execution", "per-call-approvals", "agent-polling"}

        def check(payload):
            return subprocess.run([sys.executable, "-c", checker.group(1)],
                                  input=payload, capture_output=True, text=True)

        self.assertEqual(check(json.dumps({"features": sorted(required)})).returncode, 0)
        for missing in sorted(required):
            with self.subTest(missing=missing):
                features = sorted(required - {missing})
                self.assertNotEqual(check(json.dumps({"features": features})).returncode, 0)
        for malformed in ("not json", "[]", '{"features": null}',
                          '{"features": "supervised-agent"}'):
            with self.subTest(malformed=malformed):
                self.assertNotEqual(check(malformed).returncode, 0)
        self.assertIn("refusing a chat-only fallback", start)

    def test_cleanup_tracks_each_same_named_agent_by_its_own_pid(self):
        start = self.start_script()
        for pid in ("CORE_AGENT_PID", "RUST_AGENT_PID", "ENGINE_PID"):
            with self.subTest(pid=pid):
                self.assertIn(f'kill "${pid}"', start)
                self.assertIn(f'wait "${pid}"', start)
        self.assertNotIn('kill "$AGENT_PID"', start)
        self.assertNotIn("pkill", start.lower())
        self.assertNotIn("pgrep", start.lower())

    def test_the_engine_is_served_directly_on_loopback_8184(self):
        start = self.start_script()
        self.assertIn('"$ENGINE" serve --auto-tier --model "$FENNEC_MODEL"', start)
        self.assertIn("--host 127.0.0.1 --port 8184", start)
        self.assertIn('ENGINE="$ROOT/engine/target/release/fennec"', start)

    def test_the_serve_guard_demands_the_shape_the_engine_actually_reads(self):
        # fennec serve mmaps config.json + *.safetensors and converts nothing, so a packed
        # int4 directory passes `-d` and then answers in fluent nonsense. The guard checks
        # the file the engine needs and the message names the component that converts.
        start = self.start_script()
        self.assertIn('-f "$FENNEC_MODEL/config.json"', start)
        self.assertIn("config.json and *.safetensors", start)
        self.assertIn("fennec-convert", start)

    def test_no_other_engine_or_deleted_lane_is_named(self):
        for stale in ("colibri", "coli", "jev", "Ollama", "ollama"):
            with self.subTest(stale=stale):
                self.assertNotIn(stale, SCRIPT.lower())

    def test_the_script_is_posix_shell_and_leaves_everything_under_the_root(self):
        self.assertTrue(SCRIPT.startswith("#!/data/data/com.termux/files/usr/bin/bash"))
        self.assertIn('ROOT="${FENNEC_ROOT:-$HOME/Fennec}"', SCRIPT)
        self.assertIn("install.py --install --features mobile", SCRIPT)


if __name__ == "__main__":
    unittest.main()
