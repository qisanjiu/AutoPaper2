from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import yaml

_project_root = Path(__file__).parent.parent.resolve()
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from scripts.resource_planner import allocate_tasks, build_plan


class TestResourcePlannerPool(unittest.TestCase):
    def test_build_plan_merges_local_and_manual_ssh_pool(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            (project / "config").mkdir(parents=True)
            (project / "config" / "execution_env.yaml").write_text(
                "execution:\n"
                "  mode: local\n"
                "  sandbox:\n"
                "    resource_limits:\n"
                "      max_cpu_cores: 8\n"
                "      max_gpu_count: all_visible\n"
                "  resource_optimization:\n"
                "    enabled: true\n"
                "    resource_pool:\n"
                "      enabled: true\n"
                "      include_local: true\n"
                "      resources:\n"
                "        - resource_id: ssh:lab-a\n"
                "          kind: ssh\n"
                "          server_id: lab-a\n"
                "          lease_id: lease-a\n"
                "          workspace_path: ~/AutoPaper2/projects/demo\n"
                "          gpu_count: 1\n"
                "          gpu_ids: [0]\n"
                "          cpu_cores: 16\n"
                "          tags: [gpu, cuda]\n",
                encoding="utf-8",
            )

            plan = build_plan(project)

            pool = plan["resource_pool"]
            self.assertTrue(pool["enabled"])
            ids = {resource["resource_id"] for resource in pool["resources"]}
            self.assertIn("local", ids)
            self.assertIn("ssh:lab-a", ids)

    def test_allocate_tasks_spreads_independent_tasks_across_slots(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            (project / "experiments" / "configs").mkdir(parents=True)
            plan = {
                "schema_version": 1,
                "project_root": str(project),
                "resource_pool": {
                    "enabled": True,
                    "resources": [
                        {
                            "resource_id": "local",
                            "kind": "local",
                            "cpu_cores": 16,
                            "gpu_count": 2,
                            "gpu_ids": ["0", "1"],
                            "tags": ["local", "gpu"],
                        },
                        {
                            "resource_id": "ssh:lab-a",
                            "kind": "ssh",
                            "server_id": "lab-a",
                            "lease_id": "lease-a",
                            "workspace_path": "~/AutoPaper2/projects/demo",
                            "cpu_cores": 16,
                            "gpu_count": 1,
                            "gpu_ids": ["0"],
                            "tags": ["gpu", "cuda"],
                            "sync_required": True,
                        },
                    ],
                },
            }
            tasks_path = project / "experiments" / "configs" / "m3_task_queue.yaml"
            tasks_path.write_text(
                yaml.safe_dump(
                    {
                        "tasks": [
                            {
                                "task_id": "run_a",
                                "stage": "M3S04",
                                "command": "python train.py --run a",
                                "resource_requirements": {"min_gpu_count": 1},
                            },
                            {
                                "task_id": "run_b",
                                "stage": "M3S04",
                                "command": "python train.py --run b",
                                "resource_requirements": {"min_gpu_count": 1},
                            },
                            {
                                "task_id": "run_c",
                                "stage": "M3S04",
                                "command": "python train.py --run c",
                                "resource_requirements": {"min_gpu_count": 1},
                            },
                        ]
                    },
                    sort_keys=False,
                ),
                encoding="utf-8",
            )

            allocation = allocate_tasks(project, plan, tasks_path, stage="M3S04")

            self.assertFalse(allocation["blocked_tasks"])
            self.assertEqual(len(allocation["assignments"]), 3)
            first_wave = next(wave for wave in allocation["waves"] if wave["wave"] == 0)
            self.assertGreaterEqual(len(first_wave["parallel_assignments"]), 2)
            self.assertTrue(
                all("resource_monitor" in assignment for assignment in allocation["assignments"])
            )


if __name__ == "__main__":
    unittest.main()
