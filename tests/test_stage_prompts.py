import glob
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def stage_context():
    return {
        "global_summary": "狼队夜间频繁试探，女巫未动药",
        "round_summaries": "R1: 1号发言犀利; R2: 3号自曝猎人",
        "recent_transcript": "1号：我站2号; 2号：票给4号",
        "round": 2,
        "stage": "DAY_TALK",
        "speaker_order": "[1, 2, 3, 4]",
        "turn_index": 1,
        "total_speakers": 4,
        "is_first_in_round": True,
        "alive_map": "{1: True, 2: True, 3: False, 4: True}",
        "time_left": "02:00",
        "dialect_hint": "东北腔",
        "persona": "谨慎的分析师",
        "killed_list": "座位4",
        "heal_left": 1,
        "poison_left": 0,
        "alive_targets": "[1, 2, 4]",
        "result": "wolves_win",
        "final_transcript_digest": "夜晚刀口多次转换，白天投票摇摆",
        "your_notes_tail": "坚持盯住2号站姿",
        "wolf_mates": "[5, 6]",
        "private_role": "预言家",
        "recent_notes": "- 2号语气紧张\n- 4号前后矛盾",
        "is_alive": True,
    }


def test_stage_prompts_render_without_errors(stage_context):
    prompt_paths = sorted(Path("prompts").glob("stage_*.md"))
    assert prompt_paths, "No stage prompt templates found"

    for path in prompt_paths:
        template = path.read_text(encoding="utf-8")
        try:
            template.format(**stage_context)
        except KeyError as exc:  # pragma: no cover - failure path
            pytest.fail(f"Missing key {exc} for template {path.name}")
        except ValueError as exc:  # pragma: no cover - failure path
            pytest.fail(f"Formatting error for template {path.name}: {exc}")
