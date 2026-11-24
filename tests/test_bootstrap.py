import builtins
import contextlib
import io
import os
import runpy
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import bootstrap  # noqa: E402
import install  # noqa: E402


class SetupHomeTests(unittest.TestCase):
    def env_without_override(self):
        return {k: v for k, v in os.environ.items() if k != "FENNEC_SETUP_HOME"}

    def test_environment_override(self):
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.dict(os.environ, {"FENNEC_SETUP_HOME": directory}):
                self.assertEqual(bootstrap.default_setup_home(), Path(directory).resolve())

    def test_suite_sibling_is_the_hub(self):
        with mock.patch.dict(os.environ, self.env_without_override(), clear=True):
            home = bootstrap.default_setup_home()
            self.assertEqual(home.name, "fennec-environment-setup")
            self.assertEqual(home.parent, ROOT.parent)
            self.assertTrue((home / "fennec_setup" / "provision.py").is_file())

    def test_standalone_layout_without_a_sibling(self):
        with mock.patch.dict(os.environ, self.env_without_override(), clear=True), \
                mock.patch.object(Path, "is_file", return_value=False):
            self.assertEqual(bootstrap.default_setup_home(),
                             Path.home() / "Fennec-Environment-Setup")

    def clone(self, home, name):
        provision = home / name / "fennec_setup" / "provision.py"
        provision.parent.mkdir(parents=True)
        provision.write_text("# hub\n", encoding="utf-8")
        return home / name

    def hub(self, home):
        with mock.patch.dict(os.environ, self.env_without_override(), clear=True):
            return bootstrap.default_setup_home(home=home, here=home / "nowhere")

    def test_a_lowercase_home_clone_is_used_before_the_capitalized_default(self):
        # Linux and macOS compare names case-sensitively: probing only the capitalized
        # spelling would clone a second hub beside the existing one.
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            clone = self.clone(home, "fennec-environment-setup")
            self.assertEqual(self.hub(home), clone)

    def test_a_capitalized_home_clone_is_always_found(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            clone = self.clone(home, "Fennec-Environment-Setup")
            self.assertEqual(self.hub(home), clone)

    def test_a_bare_name_is_not_a_hub(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            (home / "fennec-environment-setup").mkdir()
            self.assertEqual(self.hub(home), home / "Fennec-Environment-Setup")

    def test_the_suite_sibling_beats_a_home_clone(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            suite = base / "suite"
            clone = self.clone(suite, "fennec-environment-setup")
            self.clone(base / "home", "fennec-environment-setup")
            with mock.patch.dict(os.environ, self.env_without_override(), clear=True):
                home = bootstrap.default_setup_home(home=base / "home", here=suite)
            self.assertEqual(home, clone)


class DriveDestinationTests(unittest.TestCase):
    def test_a_letter_resolves_to_the_default_folder_on_that_drive(self):
        for value in ("E", "e", "E:", "E:/", "E:\\"):
            with self.subTest(value=value):
                with mock.patch.object(bootstrap, "validate_destination",
                                       side_effect=lambda raw, **_: raw) as checked:
                    self.assertEqual(bootstrap.drive_destination(value), "E:/Fennec")
                self.assertEqual(checked.call_args.args[0], "E:/Fennec")

    def test_a_folder_path_is_passed_through(self):
        with mock.patch.object(bootstrap, "validate_destination",
                               side_effect=lambda raw, **_: raw):
            self.assertEqual(bootstrap.drive_destination("E:/Apps/Fennec"), "E:/Apps/Fennec")

    def off_windows(self):
        # Patching os.name on the real module makes pathlib refuse to build a Path.
        return mock.patch.object(bootstrap, "os",
                                 types.SimpleNamespace(name="posix", path=os.path,
                                                       access=os.access, environ=os.environ,
                                                       W_OK=os.W_OK))

    def test_a_drive_letter_is_refused_off_windows(self):
        # Without the guard "E" became "/E/Fennec", and the install landed at the root.
        with self.off_windows():
            with self.assertRaises(ValueError) as caught:
                bootstrap.drive_destination("E")
        message = str(caught.exception)
        self.assertIn("Windows drive letter", message)
        self.assertIn("~/Fennec", message)
        self.assertIn("/mnt/e/Fennec", message)

    def test_a_folder_path_still_works_off_windows(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.off_windows():
                chosen = bootstrap.drive_destination(Path(directory) / "Fennec")
            self.assertEqual(chosen, (Path(directory) / "Fennec").resolve())

    def test_empty_input_is_refused(self):
        for value in ("", "   ", "//"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    bootstrap.drive_destination(value)


class OutletFlagTests(unittest.TestCase):
    # Mirrors fennec-environment-setup's fennec_setup.config.KEYS (golden there is
    # KeysTests.test_shared_key_set). plan_from_args reads overrides as
    # getattr(args, key, None) for every key, so a key without a flag here is quietly
    # unsettable from the installer instead of an error.
    SHARED_KEYS = {"engine_root", "suite_root", "models_root", "cache_root", "python",
                   "model", "engine_url", "web_root", "workspace", "backend", "ctx",
                   "policy", "openbot_url", "web_python"}

    def test_outlet_overrides_reach_the_hub_as_keys(self):
        args = bootstrap.parser().parse_args([
            "--plan", "--features", "browser-outlets",
            "--openbot-url", "http://127.0.0.1:3001",
            "--web-python", "~/browsenv/python"])
        self.assertEqual(args.openbot_url, "http://127.0.0.1:3001")
        self.assertEqual(args.web_python, "~/browsenv/python")

    def test_the_deleted_lane_has_no_flags_left_to_mistake_for_live(self):
        # argparse maps an unknown --x to AttributeError-free SystemExit(2), so refusing
        # is what proves the installer cannot offer a setting the core no longer reads.
        for flag in ("--jev-root", "~/my-jev", "--web-engine", "fennec"):
            with self.subTest(flag=flag):
                with self.assertRaises(SystemExit) as caught:
                    with contextlib.redirect_stderr(io.StringIO()):
                        bootstrap.parser().parse_args(["--plan", "--all", flag])
                self.assertEqual(caught.exception.code, 2)

    def test_every_shared_key_can_be_pinned_from_the_command_line(self):
        args = bootstrap.parser().parse_args(["--plan", "--all"])
        self.assertEqual(sorted(key for key in self.SHARED_KEYS if not hasattr(args, key)), [])

    def test_version_is_1_0_0(self):
        self.assertEqual(bootstrap.VERSION, "1.0.0")


class RecommendedModelFlagTests(unittest.TestCase):
    def fake_hub(self):
        plan = object()
        package = types.ModuleType("fennec_setup")
        package.__path__ = []
        package.load_manifest = mock.Mock(return_value={
            "repos": [], "features": {"inference": {"description": "run the engine"}}})
        config = types.ModuleType("fennec_setup.config")
        config.KEYS = ()
        provision = types.ModuleType("fennec_setup.provision")
        provision.selected_features = mock.Mock(return_value=["inference"])
        provision.plan_from_args = mock.Mock(return_value=plan)
        provision.print_plan = mock.Mock()
        provision.execute_plan = mock.Mock()
        provision.update_installed = mock.Mock()
        return {"fennec_setup": package, "fennec_setup.config": config,
                "fennec_setup.provision": provision}, package, provision, plan

    def invoke(self, argv, *, plan_error=None):
        modules, package, provision, plan = self.fake_hub()
        if plan_error:
            provision.plan_from_args.side_effect = plan_error
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.dict(sys.modules, modules), \
                mock.patch.object(bootstrap, "bootstrap_setup", return_value=package), \
                mock.patch.object(bootstrap, "choose_destination", return_value=None), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = bootstrap.main([*argv, "--setup-home", str(ROOT / "unused-setup")])
        return code, out.getvalue(), err.getvalue(), provision, plan

    def test_download_model_is_an_explicit_opt_in(self):
        self.assertFalse(bootstrap.parser().parse_args(["--plan", "--all"]).download_model)
        args = bootstrap.parser().parse_args(["--plan", "--all", "--download-model"])
        self.assertTrue(args.download_model)

    def test_interactive_install_offers_the_recommended_model_only_with_core(self):
        fetch = types.ModuleType("fennec_setup.fetch")
        fetch.repos_for_features = lambda manifest, features: (
            [{"concept": "core"}] if "core" in features else [])
        with mock.patch.dict(sys.modules, {"fennec_setup.fetch": fetch}):
            self.assertTrue(bootstrap.offer_recommended_model(
                ["core"], {}, ask=lambda _: "y", echo=lambda _: None))
            self.assertFalse(bootstrap.offer_recommended_model(
                ["installer"], {}, ask=lambda _: "y", echo=lambda _: None))
            self.assertFalse(bootstrap.offer_recommended_model(
                ["core"], {}, interactive=False, ask=lambda _: "y", echo=lambda _: None))

    def test_download_model_and_explicit_model_reach_the_hub(self):
        code, _, err, provision, _ = self.invoke([
            "--plan", "--features", "inference", "--download-model", "--model", "custom-model"])
        self.assertEqual(code, 0, err)
        passed = provision.plan_from_args.call_args.args[1]
        self.assertTrue(passed.download_model)
        self.assertEqual(passed.model, "custom-model")

    def test_plan_and_fetch_only_never_execute_install_actions(self):
        for mode in ("--plan", "--fetch-only"):
            with self.subTest(mode=mode):
                argv = [mode, "--features", "inference", "--download-model"]
                if mode == "--fetch-only":
                    argv.append("--yes")
                code, _, err, provision, plan = self.invoke(argv)
                self.assertEqual(code, 0, err)
                self.assertTrue(provision.plan_from_args.call_args.args[1].download_model)
                if mode == "--plan":
                    provision.execute_plan.assert_not_called()
                else:
                    provision.execute_plan.assert_called_once_with(plan, install=False)

    def test_hub_model_conflict_is_reported_without_execution(self):
        code, _, err, provision, _ = self.invoke([
            "--plan", "--features", "inference", "--download-model", "--model", "other-model"],
            plan_error=ValueError("--model and --download-model select different models"))
        self.assertEqual(code, 1)
        self.assertIn("--model and --download-model select different models", err)
        provision.execute_plan.assert_not_called()


class DestinationTests(unittest.TestCase):
    def test_layout_covers_engine_suite_models_cache_setup(self):
        root = Path(tempfile.gettempdir()) / "fennec-layout"
        parts = bootstrap.layout(root)
        self.assertEqual(list(parts), ["engine", "suite", "models", "cache", "setup"])
        self.assertEqual(parts["setup"], root / "setup")

    def test_explicit_root_is_normalized(self):
        with tempfile.TemporaryDirectory() as directory:
            chosen = bootstrap.choose_destination(str(Path(directory) / "nested" / "root"))
            self.assertEqual(chosen, (Path(directory) / "nested" / "root").resolve())

    def test_a_file_is_not_a_destination(self):
        with tempfile.NamedTemporaryFile() as handle:
            with self.assertRaises(ValueError) as caught:
                bootstrap.choose_destination(handle.name)
            self.assertIn("is a file", str(caught.exception))

    def test_drive_root_is_refused(self):
        root = Path(tempfile.gettempdir()).anchor
        with self.assertRaises(ValueError) as caught:
            bootstrap.choose_destination(root)
        self.assertIn("not a drive", str(caught.exception))

    def test_noninteractive_run_keeps_defaults(self):
        self.assertIsNone(bootstrap.choose_destination(None, interactive=False))
        self.assertIsNone(bootstrap.choose_destination(None, assume_yes=True, interactive=True))

    def test_interactive_default_and_confirmation(self):
        with tempfile.TemporaryDirectory() as home:
            answers = iter(["", ""])
            echoed = []
            chosen = bootstrap.choose_destination(
                None, interactive=True, home=home, ask=lambda prompt: next(answers),
                echo=echoed.append)
            self.assertEqual(chosen, (Path(home) / "Fennec").resolve())
            output = "\n".join(echoed)
            self.assertIn("engine", output)
            self.assertIn("stays on this device", output)

    def test_interactive_reprompts_after_invalid_path(self):
        with tempfile.TemporaryDirectory() as home, tempfile.NamedTemporaryFile() as handle:
            destination = Path(home) / "chosen"
            answers = iter([handle.name, str(destination), ""])
            chosen = bootstrap.choose_destination(
                None, interactive=True, home=home, ask=lambda prompt: next(answers),
                echo=lambda *_: None)
            self.assertEqual(chosen, destination.resolve())

    def test_interactive_declined_destination_reprompts(self):
        with tempfile.TemporaryDirectory() as home:
            first = Path(home) / "first"
            second = Path(home) / "second"
            answers = iter([str(first), "n", str(second), "y"])
            chosen = bootstrap.choose_destination(
                None, interactive=True, home=home, ask=lambda prompt: next(answers),
                echo=lambda *_: None)
            self.assertEqual(chosen, second.resolve())


@unittest.skipUnless(shutil.which("git"), "git is required for checkout guards")
class BootstrapGuardTests(unittest.TestCase):
    def test_foreign_origin_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            subprocess.run(["git", "init", "-q", str(home)], check=True)
            subprocess.run(["git", "-C", str(home), "remote", "add", "origin",
                            "https://github.com/evil/fennec-environment-setup.git"], check=True)
            with self.assertRaises(RuntimeError) as caught:
                bootstrap.bootstrap_setup(home, allow_fetch=False)
            self.assertIn("Foreign setup origin", str(caught.exception))

    def test_unknown_non_git_source_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            (home / "notes.txt").write_text("user data", encoding="utf-8")
            with self.assertRaises(RuntimeError) as caught:
                bootstrap.bootstrap_setup(home, allow_fetch=False)
            self.assertIn("Unknown setup source", str(caught.exception))

    def test_read_only_plan_never_clones(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory) / "setup"
            with self.assertRaises(RuntimeError) as caught:
                bootstrap.bootstrap_setup(home, allow_fetch=False)
            self.assertIn("no clone was attempted", str(caught.exception))
            self.assertFalse(home.exists())


class FeatureSelectionTests(unittest.TestCase):
    def cs(self):
        class FakeSetup:
            @staticmethod
            def load_manifest():
                return {"repos": [], "features": {
                    "inference": {"description": "run the engine"},
                    "installer": {"description": "download the bootstrap"},
                }}
        return FakeSetup()

    def test_noninteractive_requires_selection(self):
        with mock.patch.object(sys.stdin, "isatty", return_value=False):
            with self.assertRaises(ValueError):
                bootstrap.choose_features(self.cs(), None, False)

    def test_yes_never_selects_everything(self):
        with mock.patch.object(sys.stdin, "isatty", return_value=False):
            with self.assertRaises(ValueError):
                bootstrap.choose_features(self.cs(), None, True)

    def test_invalid_selection_rejected(self):
        with mock.patch.object(sys.stdin, "isatty", return_value=True), \
                mock.patch.object(builtins, "input", return_value="99"):
            with self.assertRaises(ValueError):
                bootstrap.choose_features(self.cs(), None, False)

    def test_all_selection(self):
        package = types.ModuleType("fennec_setup")
        package.__path__ = []
        provision = types.ModuleType("fennec_setup.provision")
        provision.selected_features = lambda manifest, features, all_features: list(manifest["features"])
        with mock.patch.dict(sys.modules, {"fennec_setup": package,
                                           "fennec_setup.provision": provision}):
            selected = bootstrap.choose_features(self.cs(), None, True, all_features=True)
        self.assertEqual(selected, ["inference", "installer"])


class BootstrapEntryTests(unittest.TestCase):
    def test_direct_execution_reaches_the_cli(self):
        with mock.patch.object(sys, "argv", ["bootstrap.py", "--help"]), \
                contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit) as caught:
                runpy.run_path(str(ROOT / "bootstrap.py"), run_name="__main__")
        self.assertEqual(caught.exception.code, 0)


class InstallEntryTests(unittest.TestCase):
    def test_implicit_mode_downloads_sources_only(self):
        with mock.patch.object(install, "main", return_value=0) as called:
            self.assertEqual(install.run(["--features", "inference"]), 0)
        self.assertIn("--fetch-only", called.call_args.args[0])

    def test_update_maps_to_fetch_mode(self):
        with mock.patch.object(install, "main", return_value=0) as called:
            self.assertEqual(install.run(["--update", "--yes"]), 0)
        self.assertIn("--fetch-only", called.call_args.args[0])
        self.assertIn("--update", called.call_args.args[0])

    def test_explicit_modes_are_not_rewritten(self):
        for argv in (["--plan"], ["--dry-run"], ["--install"], ["--fetch-only"],
                     ["--build", "--all"], ["--help"]):
            with self.subTest(argv=argv), \
                    mock.patch.object(install, "main", return_value=0) as called:
                install.run(argv)
            self.assertEqual(called.call_args.args[0], argv)

    def test_exit_code_propagates(self):
        with mock.patch.object(install, "main", return_value=1):
            self.assertEqual(install.run(["--install", "--features", "inference"]), 1)


if __name__ == "__main__":
    unittest.main()
