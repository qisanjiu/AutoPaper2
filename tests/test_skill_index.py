from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.skill_index import build_index


class TestSkillIndex(unittest.TestCase):
    def test_build_index_tolerates_non_strict_argument_hint_frontmatter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill_dir = root / "skills" / "DemoSkill"
            mirror_dir = root / ".claude" / "skills" / "DemoSkill"
            skill_dir.mkdir(parents=True)
            mirror_dir.mkdir(parents=True)
            text = (
                "---\n"
                "name: DemoSkill\n"
                "description: >\n"
                "  Demo description.\n"
                "argument-hint: [项目路径] [可选：stage]\n"
                "skill_role: utility\n"
                "---\n"
                "# Demo\n"
            )
            (skill_dir / "SKILL.md").write_text(text, encoding="utf-8")
            (mirror_dir / "SKILL.md").write_text(text, encoding="utf-8")

            index = build_index(root)

            self.assertEqual(index["skills"][0]["name"], "DemoSkill")
            self.assertEqual(index["skills"][0]["path"], "skills/DemoSkill/SKILL.md")
            self.assertEqual(index["skills"][0]["skill_role"], "utility")
            self.assertIn("项目路径", index["skills"][0]["argument_hint"])


if __name__ == "__main__":
    unittest.main()
