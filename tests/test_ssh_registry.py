from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import yaml

from scripts.env_probe import _merge_existing_manual_config, generate_execution_env_yaml
from spiral.ssh_registry import (
    _parse_probe_stdout,
    allocate_server,
    apply_lease_to_project,
    init_registry,
    load_leases,
    load_registry,
    release_lease,
    upsert_server,
    validate_project_lease,
)


class TestSSHRegistry(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "config").mkdir()
        (self.root / "state").mkdir()
        self.project = self.root / "projects" / "demo-20260530-120000"
        (self.project / "config").mkdir(parents=True)
        (self.project / "state").mkdir()
        (self.project / "config" / "execution_env.yaml").write_text(
            "execution:\n"
            "  mode: local\n"
            "  sandbox:\n"
            "    enabled: true\n"
            "    mode: conda\n"
            "  ssh:\n"
            "    host: ''\n"
            "    user: ''\n"
            "    port: 22\n"
            "    sync:\n"
            "      method: rsync\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_allocate_apply_validate_release(self) -> None:
        init_registry(self.root)
        upsert_server(
            {
                "server_id": "lab-a",
                "host": "gpu-a.example.test",
                "user": "researcher",
                "identity_file": "~/.ssh/id_ed25519",
                "framework_root": "~/AutoPaper2",
                "tags": ["gpu", "cuda"],
                "priority": 10,
                "max_concurrent_projects": 1,
                "capabilities": {"gpu_count": 4, "vram_gb": 24},
            },
            self.root,
        )

        lease = allocate_server(
            self.root,
            self.project,
            server_id="auto",
            min_gpu_count=1,
            tags=["gpu"],
            lease_hours=12,
        )
        self.assertEqual(lease["server_id"], "lab-a")

        config_path = apply_lease_to_project(self.root, self.project, lease["lease_id"])
        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        self.assertEqual(config["execution"]["mode"], "ssh")
        self.assertEqual(config["execution"]["server_id"], "lab-a")
        self.assertEqual(config["execution"]["lease_id"], lease["lease_id"])
        self.assertEqual(config["execution"]["sandbox"]["mode"], "ssh_remote")
        self.assertEqual(config["execution"]["ssh"]["password"], "")
        self.assertTrue((self.project / "state" / "ssh_allocation.yaml").exists())

        ok, message = validate_project_lease(self.root, self.project)
        self.assertTrue(ok, message)

        release_lease(lease["lease_id"], self.root)
        ok, message = validate_project_lease(self.root, self.project)
        self.assertFalse(ok)
        self.assertIn("released", message)

    def test_concurrency_limit_blocks_second_allocation(self) -> None:
        init_registry(self.root)
        upsert_server(
            {
                "server_id": "solo",
                "host": "solo.example.test",
                "user": "researcher",
                "max_concurrent_projects": 1,
                "capabilities": {"gpu_count": 1, "vram_gb": 12},
            },
            self.root,
        )
        allocate_server(self.root, self.project, server_id="solo")
        other_project = self.root / "projects" / "other-20260530-120001"
        other_project.mkdir(parents=True)
        with self.assertRaises(Exception):
            allocate_server(self.root, other_project, server_id="solo")

    def test_env_probe_defaults_local_and_preserves_managed_ssh(self) -> None:
        report = {
            "python": {"version": "3.11.9", "executable": "/usr/bin/python3"},
            "gpu": {"available": False, "cuda_version": None, "devices": []},
            "env_managers": {
                "conda": {"available": True, "version": "conda 24"},
                "uv": {"available": False},
                "docker": {"available": False},
                "venv": {"available": True},
            },
            "cpu": {"cores": 8, "model": "Test CPU"},
            "os": {"system": "Linux", "release": "test", "machine": "x86_64"},
            "ml_frameworks": {"torch": {}, "tensorflow": {}},
            "ssh": {"available": True, "key_files": ["/home/test/.ssh/id_ed25519"]},
        }
        generated = generate_execution_env_yaml(report, "demo")
        data = yaml.safe_load(generated)
        self.assertEqual(data["execution"]["mode"], "local")
        self.assertNotEqual(data["execution"]["sandbox"]["mode"], "ssh_remote")

        existing = {
            "execution": {
                "mode": "ssh",
                "server_id": "lab-a",
                "lease_id": "lease-1",
                "ssh": {
                    "server_id": "lab-a",
                    "lease_id": "lease-1",
                    "host": "gpu-a.example.test",
                    "user": "researcher",
                    "workspace_path": "~/AutoPaper2/projects/demo",
                },
            }
        }
        merged = yaml.safe_load(_merge_existing_manual_config(generated, existing))
        self.assertEqual(merged["execution"]["mode"], "ssh")
        self.assertEqual(merged["execution"]["server_id"], "lab-a")
        self.assertEqual(merged["execution"]["ssh"]["lease_id"], "lease-1")
        self.assertEqual(merged["execution"]["sandbox"]["mode"], "ssh_remote")

    def test_parse_probe_stdout_collects_gpu_and_datasets(self) -> None:
        parsed = _parse_probe_stdout(
            "__AP2_HOSTNAME__\n"
            "gpu01\n"
            "__AP2_UNAME__\n"
            "Linux 6.1 x86_64\n"
            "__AP2_PYTHON__\n"
            "Python 3.11.9\n"
            "__AP2_CONDA__\n"
            "conda 24.1\n"
            "__AP2_GPU__\n"
            "0, NVIDIA RTX 4090, 24564, 550.54\n"
            "1, NVIDIA RTX 4090, 24564, 550.54\n"
            "__AP2_DATASETS__\n"
            "imagenet\n"
            "coco\n",
            dataset_path="~/AutoPaper2/data/datasets",
        )

        self.assertEqual(parsed["remote"]["hostname"], "gpu01")
        self.assertEqual(parsed["capabilities"]["gpu_count"], 2)
        self.assertEqual(parsed["capabilities"]["gpus"][0]["name"], "NVIDIA RTX 4090")
        self.assertGreater(parsed["capabilities"]["max_vram_gb"], 20)
        self.assertEqual(parsed["dataset_cache"]["datasets"], ["imagenet", "coco"])


if __name__ == "__main__":
    unittest.main()
