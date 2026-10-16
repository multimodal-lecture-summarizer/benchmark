"""Portable entry-point integrity and fail-closed extraction contracts."""
import ast
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import warnings
from zipfile import ZipFile

from experiments.scripts.build_spotting_colab_notebook import build
from experiments.scripts.spotting_colab_bundle import verify
from experiments.scripts.spotting_colab_notebook import export_evidence, render_figures


class PortableNotebookTests(unittest.TestCase):
    def test_v2_imports_replay_gate_and_checks_it_before_test(self):
        path = Path(__file__).resolve().parents[1]/'experiments/notebooks/iiit-cvid-spotting-colab-t4-v2.ipynb'
        notebook = json.loads(path.read_text(encoding='utf-8'))
        cells = {c.get('id'): ''.join(c['source']) for c in notebook['cells']}
        source = '\n'.join(cells.values())
        self.assertIn('import table, status_rows, require_preflights, require_train_replays', source)
        self.assertIn("cli('verify'", cells['cvid-t4-v2-07'])
        run = cells['cvid-t4-v2-09']
        self.assertLess(run.index('require_train_replays('), run.index("cli('run')"))

    def make_archive(self, path, name="experiments/scripts/runner.py", content=b"print('x')", **kw):
        entry = dict(path=name, sha256=hashlib.sha256(content).hexdigest(), bytes=len(content))
        with ZipFile(path, "w") as archive:
            archive.writestr(name, content)
            archive.writestr("bundle-manifest.json", json.dumps({"files": [entry]}))
            if kw.get("extra"):
                archive.writestr("unexpected.py", "print('bad')")
        return entry

    def test_bundle_membership_rejects_unbound_code(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bundle.zip"
            self.make_archive(path, extra=True)
            with self.assertRaisesRegex(ValueError, "membership"):
                verify(path)

    def test_bundle_rejects_path_escape(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bundle.zip"
            self.make_archive(path, name="../runner.py")
            with self.assertRaisesRegex(ValueError, "unsafe"):
                verify(path)

    def test_bundle_rejects_duplicate_members(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bundle.zip"
            self.make_archive(path)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                with ZipFile(path, "a") as archive:
                    archive.writestr("experiments/scripts/runner.py", "changed")
            with self.assertRaisesRegex(ValueError, "duplicate"):
                verify(path)

    def test_notebook_bound_to_real_bundle_and_nested_download_code_parses(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "notebook.ipynb"
            digest = "1234567890abcdef" * 4
            build({"sha256": digest}, output)
            notebook = json.loads(output.read_text(encoding="utf-8"))
            source = "\n".join("".join(c["source"]) for c in notebook["cells"])
            self.assertIn(digest, source)
            self.assertIn("--source-zip", source)
            self.assertNotIn("git clone", source)
            for item in notebook["cells"]:
                if item["cell_type"] != "code":
                    continue
                self.assertIsNone(item["execution_count"])
                self.assertEqual(item["outputs"], [])
                tree = ast.parse("".join(item["source"]))
                for node in ast.walk(tree):
                    if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "download_script" for t in node.targets):
                        ast.parse(ast.literal_eval(node.value))

    def test_partial_evidence_export_cannot_claim_completed_comparison(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "output"
            root.mkdir()
            (root / "failed-preflight.json").write_text('{"status":"failed"}')
            receipt = export_evidence(root)
            self.assertFalse(receipt["completed_comparison"])
            with ZipFile(receipt["path"]) as archive:
                self.assertIn("failed-preflight.json", archive.namelist())
                self.assertIn("export-manifest.json", archive.namelist())
            with self.assertRaises(ValueError):
                export_evidence(root, root / "recursive.zip")

    def test_figures_seal_export_hashes_and_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixtures = {
                "metrics.csv": "candidate_id,variant,metric,hmean,precision,recall,failed_frames\nfixture,primary,spotting,1,1,1,0\nfixture,primary,detection,1,1,1,0\n",
                "group-metrics.csv": "candidate_id,variant,metric,group_type,group,hmean\nfixture,primary,spotting,course,fixturecourse,1\n",
                "bootstrap.csv": "candidate_id,variant,group_key,low,high,delta\nfixture,primary,course,-0.1,0.1,0\n",
            }
            artifacts = {}
            for name, text in fixtures.items():
                path = root / name
                path.write_text(text, encoding="utf-8")
                artifacts[name] = {"path": name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            (root / "analysis-summary.json").write_text(json.dumps({"candidate_order": ["fixture"], "artifacts": artifacts}))
            receipt = render_figures(root)
            self.assertEqual(len(receipt["artifacts"]), 6)
            self.assertEqual(render_figures(root), receipt)
            (root / "metrics.csv").write_text("changed")
            with self.assertRaisesRegex(ValueError, "analysis export changed"):
                render_figures(root)


if __name__ == "__main__":
    unittest.main()
