"""轻量规则驱动的 LLM 会话实现，便于命令行演示。"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass, field
from typing import Dict, List

from .models import PlayerState


TARGET_PATTERN = re.compile(r"座位(\d)")


@dataclass
class RuleBasedSession:
    """基于提示词的简易自动回复会话。"""

    player: PlayerState
    rng: random.Random
    last_digest: Dict[str, List[str]] = field(default_factory=dict)
    last_notes: List[str] = field(default_factory=list)
    action_memory: Dict[str, object] = field(default_factory=dict)

    def interact(self, stage_name: str, metadata: Dict[str, object], expect_response: bool) -> Optional[str]:
        if not expect_response:
            self._observe(stage_name, metadata)
            return None
        if stage_name == "stage_life_check":
            return self._life_check(metadata)
        if stage_name == "stage_opening":
            return self._opening_line(metadata)
        if stage_name == "stage_night_wolves":
            return self._night_wolves(metadata)
        if stage_name == "stage_night_witch":
            return self._night_witch(metadata)
        if stage_name == "stage_day_talk":
            return self._day_talk(metadata)
        if stage_name == "stage_vote":
            return self._vote(metadata)
        if stage_name == "stage_write_notes":
            return self._write_notes(metadata)
        if stage_name == "stage_hunter_trigger":
            return self._hunter_trigger(metadata)
        if stage_name.startswith("stage_postgame"):
            return self._postgame(stage_name, metadata)
        return "[SKIP]"

    # -- observe ----------------------------------------------------------------
    def _observe(self, stage_name: str, metadata: Dict[str, object]) -> None:
        if stage_name == "stage_chronicle_digest":
            self.last_digest = metadata
        elif stage_name == "stage_your_notes":
            self.last_notes = metadata.get("recent_notes", [])  # type: ignore[arg-type]
        elif stage_name == "stage_context":
            self.action_memory["context"] = metadata

    # -- handlers ----------------------------------------------------------------
    def _life_check(self, metadata: Dict[str, object]) -> str:
        is_alive = metadata.get("is_alive", True)
        return "[SKIP]" if not is_alive else "收到，继续行动。"

    def _opening_line(self, metadata: Dict[str, object]) -> str:
        persona = metadata.get("persona", "冷静的玩家")
        dialect = metadata.get("dialect_hint", "普通话")
        return f"大家好，我是{persona}，带着{dialect}味儿跟大家好好聊聊。"

    def _night_wolves(self, metadata: Dict[str, object]) -> str:
        alive_targets: List[int] = metadata.get("alive_targets", [])  # type: ignore[assignment]
        choices = [sid for sid in alive_targets if sid != self.player.seat_id]
        if not choices:
            target = self.player.seat_id
        else:
            target = self.rng.choice(choices)
        message = f"今晚想压制{target}号的节奏，理由是他昨天带票太凶。\n【击杀】座位{target}"
        alternate = [sid for sid in choices if sid != target]
        if alternate:
            backup = self.rng.choice(alternate)
            message += f"\n【备选】座位{backup}"
        return message

    def _night_witch(self, metadata: Dict[str, object]) -> str:
        killed_list: List[int] = metadata.get("killed_list", [])  # type: ignore[assignment]
        heal_left = metadata.get("heal_left", 0)
        poison_left = metadata.get("poison_left", 0)
        if killed_list and heal_left:
            target = killed_list[0]
            return f"【救人】座位{target}\n理由：救回关键发言位。"
        if poison_left:
            candidates = metadata.get("alive_targets", []) or metadata.get("alive_map", {})
            if isinstance(candidates, dict):
                candidates = [sid for sid, alive in candidates.items() if alive and sid != self.player.seat_id]
            if candidates:
                target = self.rng.choice(candidates)
                return f"【下毒】座位{target}\n理由：白天言行最狼。"
        return "【空过】\n理由：暂时不动。"

    def _day_talk(self, metadata: Dict[str, object]) -> str:
        alive_map: Dict[int, bool] = metadata.get("alive_map", {})  # type: ignore[assignment]
        suspects = [sid for sid, alive in alive_map.items() if alive and sid != self.player.seat_id]
        if not suspects:
            suspects = [sid for sid in alive_map.keys() if sid != self.player.seat_id]
        target = self.rng.choice(suspects) if suspects else self.player.seat_id
        ally_candidates = [sid for sid in alive_map if sid != target and sid != self.player.seat_id]
        ally = self.rng.choice(ally_candidates) if ally_candidates else self.player.seat_id
        summary = "；".join(self.last_digest.get("global_summary", [])[:2]) if self.last_digest else "信息有限"
        transcript = self.last_digest.get("recent_transcript", []) if self.last_digest else []
        quote = transcript[0] if transcript else "昨晚没有新的增量。"
        turn_index = metadata.get("turn_index")
        total = metadata.get("total_speakers")
        first = metadata.get("is_first_in_round", False)
        intro = (
            f"今天第{turn_index}/{total}位，我仍然保{ally}号，觉得{target}号最危险。"
            if not first
            else f"今天我先发言，先定调：保{ally}号，主推{target}号。"
        )
        reason = f"纪要提到：{summary}，尤其是{quote}这点让我更警觉。"
        wrap = f"暂定先给{target}号压力，后续看信息再调。【票】座位{target}"
        return "\n".join([intro, reason, wrap])

    def _vote(self, metadata: Dict[str, object]) -> str:
        alive_map: Dict[int, bool] = metadata.get("alive_map", {})  # type: ignore[assignment]
        suspects = [sid for sid, alive in alive_map.items() if alive and sid != self.player.seat_id]
        if not suspects:
            suspects = [sid for sid in alive_map.keys() if sid != self.player.seat_id]
        target = self.rng.choice(suspects) if suspects else self.player.seat_id
        self.action_memory["vote_target"] = target
        return f"【投票】座位{target}"

    def _write_notes(self, metadata: Dict[str, object]) -> str:
        vote_target = self.action_memory.get("vote_target", self.player.seat_id)
        lines = [
            f"- 投{vote_target}号保持节奏",
            "- 关注狼坑是否自爆",
            "- 如果晚上平安考虑换票"
        ]
        return "\n".join(lines)

    def _hunter_trigger(self, metadata: Dict[str, object]) -> str:
        alive_map: Dict[int, bool] = metadata.get("alive_map", {})  # type: ignore[assignment]
        suspects = [sid for sid, alive in alive_map.items() if alive]
        if suspects:
            target = self.rng.choice(suspects)
            return f"【开枪】座位{target}\n理由：死前再清一狼。"
        return "【不开枪】\n理由：无合适目标。"

    def _postgame(self, stage_name: str, metadata: Dict[str, object]) -> str:
        if stage_name == "stage_postgame_roundup":
            return "这局节奏起伏挺大，回头还得总结配合。"
        if stage_name == "stage_postgame_roast":
            return "下次说话别再绕弯，直接点更刺激。"
        return "辛苦啦，这局收获很多。"


@dataclass
class RuleBasedLLMClient:
    rng: random.Random

    def create_session(self, player: PlayerState) -> RuleBasedSession:
        return RuleBasedSession(player=player, rng=self.rng)


