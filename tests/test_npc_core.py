from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
NPC_ROOT = ROOT / "npc"
sys.path.insert(0, str(NPC_ROOT))

from vibechat_npc import config  # noqa: E402
from vibechat_npc.budget import (  # noqa: E402
    GroupReplyCoordinator,
    SlidingWindowRateLimiter,
)
from vibechat_npc.content import content_to_text  # noqa: E402
from vibechat_npc.roster import build_persona_rows  # noqa: E402


class PersonaConfigTests(unittest.TestCase):
    def test_default_roster_works_without_generated_json(self) -> None:
        """新克隆无需先生成被忽略的 JSON 文件。"""
        with tempfile.TemporaryDirectory() as directory:
            missing_default = Path(directory) / "personas.json"
            with (
                patch.dict(os.environ, {}, clear=True),
                patch.object(config, "DEFAULT_PERSONAS", missing_default),
            ):
                personas = config.load_personas()

        self.assertEqual(len(personas), 79)
        self.assertEqual(len({persona.id for persona in personas}), 79)
        self.assertEqual(len({persona.username for persona in personas}), 79)
        self.assertEqual(personas[0].username, "alice")
        self.assertEqual(personas[0].display_name, "三月七")

    def test_explicit_persona_file_is_respected(self) -> None:
        """显式配置文件仍可覆盖内置花名册。"""
        payload = {
            "npcs": [
                {
                    "id": "local",
                    "username": "local_user",
                    "password": "local_password",
                    "display_name": "本地角色",
                    "system": "保持简短。",
                }
            ]
        }
        with tempfile.TemporaryDirectory() as directory:
            persona_path = Path(directory) / "custom-personas.json"
            persona_path.write_text(
                json.dumps(payload, ensure_ascii=False),
                encoding="utf-8",
            )
            personas = config.load_personas(persona_path)

        self.assertEqual(len(personas), 1)
        self.assertEqual(personas[0].display_name, "本地角色")

    def test_missing_explicit_persona_file_has_clear_error(self) -> None:
        """部署配置写错时不得悄悄使用默认人物。"""
        with tempfile.TemporaryDirectory() as directory:
            missing_path = Path(directory) / "missing.json"
            with self.assertRaisesRegex(SystemExit, "人物配置文件不存在"):
                config.load_personas(missing_path)

    def test_roster_rows_are_unique(self) -> None:
        rows = build_persona_rows()

        self.assertEqual(len(rows), 79)
        self.assertEqual(len({row["id"] for row in rows}), len(rows))
        self.assertEqual(len({row["username"] for row in rows}), len(rows))
        self.assertTrue(all(row["system"].strip() for row in rows))


class ContentTests(unittest.TestCase):
    def test_content_variants_are_normalized(self) -> None:
        self.assertEqual(content_to_text(None), "")
        self.assertEqual(content_to_text("消息"), "消息")
        self.assertEqual(content_to_text({"txt": "Drafty 正文"}), "Drafty 正文")
        self.assertEqual(content_to_text({"content": {"txt": "嵌套正文"}}), "嵌套正文")
        self.assertEqual(content_to_text(["第一段", None, {"txt": "第二段"}]), "第一段 第二段")
        self.assertEqual(content_to_text({"txt": "   ", "content": "回退正文"}), "回退正文")


class BudgetTests(unittest.IsolatedAsyncioTestCase):
    async def test_rate_limiter_stops_at_rpm_limit(self) -> None:
        limiter = SlidingWindowRateLimiter(rpm=2)

        self.assertTrue(await limiter.try_acquire())
        self.assertTrue(await limiter.try_acquire())
        self.assertFalse(await limiter.try_acquire())
        self.assertEqual(limiter.snapshot(), (2, 2))

    async def test_group_claims_deduplicate_and_honor_limits(self) -> None:
        coordinator = GroupReplyCoordinator(max_replies_per_msg=2)
        claim = {
            "topic": "grp-demo",
            "seq": 7,
            "text": "大家好",
            "mentioned": False,
        }

        self.assertTrue(await coordinator.try_claim(persona_id="one", **claim))
        self.assertFalse(await coordinator.try_claim(persona_id="one", **claim))
        self.assertTrue(await coordinator.try_claim(persona_id="two", **claim))
        self.assertFalse(await coordinator.try_claim(persona_id="three", **claim))
        self.assertTrue(
            await coordinator.try_claim(
                persona_id="three",
                **{**claim, "mentioned": True},
            )
        )
        self.assertFalse(
            await coordinator.try_claim(
                persona_id="four",
                **{**claim, "mentioned": True},
            )
        )


if __name__ == "__main__":
    unittest.main()
