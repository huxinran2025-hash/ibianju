"""狼人杀命令行入口。"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path
from typing import List

from .gm import GameMaster
from .llm import RuleBasedLLMClient
from .models import GameConfig, Role, SeatConfig
from .prompts import PromptRepository


DEFAULT_PERSONAS: List[str] = [
    "冷静解说",
    "毒舌辩手",
    "元气主播",
    "沉稳分析师",
    "阴郁诗人",
    "老练船长",
]

DEFAULT_DIALECTS: List[str] = [
    "普通话",
    "东北口味",
    "川渝味",
    "粤语腔",
    "苏州软语",
    "台味",
]


def build_default_config() -> GameConfig:
    seating_plan = [
        SeatConfig(seat_id=1, role=Role.WOLF, persona=DEFAULT_PERSONAS[0], dialect=DEFAULT_DIALECTS[0]),
        SeatConfig(seat_id=2, role=Role.WOLF, persona=DEFAULT_PERSONAS[1], dialect=DEFAULT_DIALECTS[1]),
        SeatConfig(seat_id=3, role=Role.WITCH, persona=DEFAULT_PERSONAS[2], dialect=DEFAULT_DIALECTS[2]),
        SeatConfig(seat_id=4, role=Role.HUNTER, persona=DEFAULT_PERSONAS[3], dialect=DEFAULT_DIALECTS[3]),
        SeatConfig(seat_id=5, role=Role.VILLAGER, persona=DEFAULT_PERSONAS[4], dialect=DEFAULT_DIALECTS[4]),
        SeatConfig(seat_id=6, role=Role.VILLAGER, persona=DEFAULT_PERSONAS[5], dialect=DEFAULT_DIALECTS[5]),
    ]
    return GameConfig(seating_plan=seating_plan)


def _ensure_prompts_dir(path: Path) -> Path:
    if not path.exists() or not path.is_dir():
        raise FileNotFoundError(f"未找到 prompts 目录：{path}")
    return path


def run_cli(argv: List[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="命令行狼人杀 GM 演示")
    parser.add_argument("--seed", type=int, default=None, help="随机种子，复现演示用")
    parser.add_argument(
        "--prompts",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "prompts",
        help="提示词目录路径",
    )
    args = parser.parse_args(argv)

    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except ValueError:
            pass

    rng = random.Random(args.seed)
    prompt_dir = _ensure_prompts_dir(args.prompts.resolve())
    prompt_repo = PromptRepository(base_dir=prompt_dir)

    config = build_default_config()
    llm_client = RuleBasedLLMClient(rng=rng)
    gm = GameMaster(config=config, prompt_repo=prompt_repo, llm_client=llm_client, rng=rng)
    gm.setup()
    gm.run_game()


__all__ = ["run_cli", "build_default_config"]

