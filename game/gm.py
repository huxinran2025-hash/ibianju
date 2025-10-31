"""游戏主持人（GM）状态机实现。"""

from __future__ import annotations

import random
import re
from collections import Counter
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

from .chronicle import Chronicle
from .llm import RuleBasedLLMClient, RuleBasedSession
from .models import GameConfig, NightOutcome, PlayerState, Role, SeatConfig, VoteRecord
from .prompts import PromptRepository


DIRECTIVE_PATTERN = re.compile(r"【(?P<action>[^】]+)】座位(?P<seat>\d)")


@dataclass
class StageResult:
    seat: int
    stage: str
    prompt_text: str
    response: Optional[str]


class GameMaster:
    """根据 docs/gm_state_machine.md 构建的命令行 GM。"""

    def __init__(
        self,
        config: GameConfig,
        prompt_repo: PromptRepository,
        llm_client: RuleBasedLLMClient,
        rng: Optional[random.Random] = None,
    ) -> None:
        self.config = config
        self.prompt_repo = prompt_repo
        self.llm_client = llm_client
        self.rng = rng or random.Random()

        self.players: Dict[int, PlayerState] = {}
        self.sessions: Dict[int, RuleBasedSession] = {}
        self.chronicle = Chronicle(seats=config.seat_ids)
        self.round_no = 1
        self._night_outcome: Optional[NightOutcome] = None
        self._day_spoken: Dict[int, bool] = {}
        self._vote_record: Optional[VoteRecord] = None
        self._log: List[StageResult] = []
        self._result: str = "ongoing"

        self._initialise_players(config.seating_plan)

    # ------------------------------------------------------------------ setup --
    def _initialise_players(self, seating_plan: List[SeatConfig]) -> None:
        seats = [seat.seat_id for seat in seating_plan]
        wolf_ids = [seat.seat_id for seat in seating_plan if seat.role == Role.WOLF]
        for seat in seating_plan:
            player = PlayerState(
                seat_id=seat.seat_id,
                role=seat.role,
                persona=seat.persona,
                dialect=seat.dialect,
            )
            player.ensure_trust_initialised(seats)
            if seat.role == Role.WOLF:
                player.role_private = {
                    "is_wolf": True,
                    "wolf_mates": [wid for wid in wolf_ids if wid != seat.seat_id],
                }
            elif seat.role == Role.WITCH:
                player.role_private = {
                    "is_wolf": False,
                    "wolf_mates": [],
                    "potions": {"heal_left": 1, "poison_left": 1},
                }
            else:
                player.role_private = {"is_wolf": False, "wolf_mates": []}
            if seat.role == Role.HUNTER:
                player.hunter_has_shot = False
            self.players[seat.seat_id] = player
            self._day_spoken[seat.seat_id] = False

    def setup(self) -> None:
        self.prompt_repo.load()
        self._setup_sessions()
        self._wolf_intro()

    def _setup_sessions(self) -> None:
        for seat_id, player in self.players.items():
            system_prompt = self.prompt_repo.render("system_common", seat=seat_id)
            role_prompt_name = f"system_role_{player.role.value}"
            try:
                role_prompt = self.prompt_repo.get(role_prompt_name)
            except KeyError:
                role_prompt = ""
            _ = system_prompt + "\n" + role_prompt  # 日后接入真实 LLM 时使用
            self.sessions[seat_id] = self.llm_client.create_session(player)

    def _wolf_intro(self) -> None:
        wolf_ids = [seat for seat, player in self.players.items() if player.role == Role.WOLF]
        for wid in wolf_ids:
            mates = [sid for sid in wolf_ids if sid != wid]
            mates_text = "、".join(str(sid) for sid in mates) if mates else "无同伴"
            metadata = {"wolf_mates": mates_text}
            self._send_stage(wid, "stage_wolf_intro", metadata, expect_response=False)

    # ------------------------------------------------------------- utils/log --
    def _record_stage(self, seat: int, stage: str, prompt_text: str, response: Optional[str]) -> None:
        self._log.append(StageResult(seat=seat, stage=stage, prompt_text=prompt_text, response=response))

    def _display_stage(self, seat: int, stage: str, prompt_text: str, response: Optional[str]) -> None:
        header = f"\n=== 座位 {seat} ｜ {stage.upper()} ==="
        print(header)
        print(prompt_text.strip())
        if response is not None:
            print("--- 回复 ---")
            print(response.strip())

    def _send_stage(
        self,
        seat: int,
        stage_name: str,
        metadata: Dict[str, object],
        expect_response: bool,
    ) -> Optional[str]:
        template_name = stage_name.replace(".md", "")
        prompt_text = self.prompt_repo.render(template_name, **metadata)
        session = self.sessions[seat]
        response = session.interact(template_name, metadata, expect_response)
        self._display_stage(seat, template_name, prompt_text, response)
        self._record_stage(seat, template_name, prompt_text, response)
        return response

    # ------------------------------------------------------------- utilities --
    def _alive_map(self) -> Dict[int, bool]:
        return {seat: player.alive for seat, player in self.players.items()}

    def _alive_seats(self) -> List[int]:
        return [seat for seat, player in self.players.items() if player.alive]

    def _wolves_alive(self) -> List[int]:
        return [seat for seat, player in self.players.items() if player.alive and player.role == Role.WOLF]

    def _player(self, seat: int) -> PlayerState:
        return self.players[seat]

    def _build_digest_payload(self) -> Dict[str, object]:
        global_summary = "；".join(self.chronicle.global_summary[-3:]) or "暂无摘要"
        round_summaries: List[str] = []
        for round_no in sorted(self.chronicle.rounds.keys())[-2:]:
            record = self.chronicle.rounds[round_no]
            summary = "；".join(record.day.summary_10[-3:]) or "暂无摘要"
            round_summaries.append(f"R{round_no}: {summary}")
        recent_transcript: List[str] = []
        for round_no in sorted(self.chronicle.rounds.keys(), reverse=True):
            record = self.chronicle.rounds[round_no]
            for utter in reversed(record.day.utterances):
                recent_transcript.append(f"{utter['seat']}号：{utter['one_line']}")
                if len(recent_transcript) >= 6:
                    break
            if len(recent_transcript) >= 6:
                break
        return {
            "global_summary": global_summary or "暂无摘要",
            "round_summaries": "；".join(round_summaries) or "尚无轮次摘要",
            "recent_transcript": "；".join(recent_transcript) or "暂无口胡记录",
        }

    def _build_notes_payload(self, player: PlayerState) -> Dict[str, object]:
        recent = ["；".join(note.get("bullets", [])) for note in player.notes[-3:]]
        private_role = {
            "role": player.role.value,
            "wolf_mates": player.role_private.get("wolf_mates", []),
            "potions": player.role_private.get("potions"),
        }
        return {
            "persona": player.persona,
            "dialect_hint": player.dialect,
            "private_role": private_role,
            "recent_notes": recent,
        }

    def _parse_directive(self, text: str, keyword: str) -> Optional[int]:
        for match in DIRECTIVE_PATTERN.finditer(text):
            if match.group("action") == keyword:
                return int(match.group("seat"))
        return None

    def _extract_notes(self, text: str) -> List[str]:
        lines = []
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("- ") and len(line) > 2:
                lines.append(line[2:])
        return lines[:5]

    def _one_line_summary(self, text: str) -> str:
        first_line = text.strip().splitlines()[0] if text.strip() else ""
        return first_line[:60] if first_line else "暂无摘要"

    # ------------------------------------------------------------- lifecycle --
    def run_game(self) -> None:
        print("GM：对局开始，祝各位好运！")
        while not self._is_finished() and self.round_no <= self.config.max_rounds:
            self._night_phase()
            if self._is_finished():
                break
            self._daybreak()
            if self._is_finished():
                break
            self._day_phase()
            self.round_no += 1
        self._postgame()

    # --------------------------------------------------------------- phases --
    def _night_phase(self) -> None:
        self._night_outcome = NightOutcome()
        self._night_wolves()
        self._night_witch()
        self.chronicle.set_night_summary(
            self.round_no,
            [
                f"狼刀目标：{self._night_outcome.kill_target if self._night_outcome.kill_target else '未确定'}",
                f"女巫救：{self._night_outcome.healed_target if self._night_outcome.healed_target else '未用'}",
                f"女巫毒：{self._night_outcome.poisoned_target if self._night_outcome.poisoned_target else '未用'}",
            ],
        )

    def _night_wolves(self) -> None:
        alive_targets = self._alive_seats()
        wolf_votes: List[int] = []
        for wid in self._wolves_alive():
            player = self._player(wid)
            response = self._send_stage(wid, "stage_life_check", {"is_alive": player.alive}, expect_response=True)
            if response and response.strip() == "[SKIP]":
                continue
            ctx_payload = {
                "round": self.round_no,
                "stage": "NIGHT_WOLVES",
                "speaker_order": alive_targets,
                "turn_index": 0,
                "is_first_in_round": False,
                "alive_map": self._alive_map(),
                "time_left": "短"
            }
            self._send_stage(wid, "stage_context", ctx_payload, expect_response=False)
            self._send_stage(wid, "stage_chronicle_digest", self._build_digest_payload(), expect_response=False)
            self._send_stage(wid, "stage_your_notes", self._build_notes_payload(player), expect_response=False)
            action = self._send_stage(wid, "stage_night_wolves", {"alive_targets": alive_targets}, expect_response=True)
            if action:
                target = self._parse_directive(action, "击杀")
                if target is not None:
                    wolf_votes.append(target)
                    self.chronicle.log_night_event(self.round_no, {"t": f"N{self.round_no}_wolf_vote", "from": wid, "target": target})
                backup = self._parse_directive(action, "备选")
                if backup is not None:
                    self.chronicle.log_night_event(self.round_no, {"t": f"N{self.round_no}_wolf_backup", "from": wid, "target": backup})
        if wolf_votes:
            counts = Counter(wolf_votes)
            target, _ = counts.most_common(1)[0]
            self._night_outcome.kill_target = target
            self.chronicle.log_night_event(self.round_no, {"t": f"N{self.round_no}_kill", "target": target})

    def _night_witch(self) -> None:
        witch_seat = next((seat for seat, p in self.players.items() if p.role == Role.WITCH), None)
        if not witch_seat:
            return
        witch = self._player(witch_seat)
        if not witch.alive:
            return
        potions = witch.role_private.get("potions", {"heal_left": 0, "poison_left": 0})
        killed_list = [self._night_outcome.kill_target] if self._night_outcome and self._night_outcome.kill_target else []
        response = self._send_stage(witch_seat, "stage_life_check", {"is_alive": witch.alive}, expect_response=True)
        if response and response.strip() == "[SKIP]":
            return
        ctx_payload = {
            "round": self.round_no,
            "stage": "NIGHT_WITCH",
            "speaker_order": self._alive_seats(),
            "turn_index": 0,
            "is_first_in_round": False,
            "alive_map": self._alive_map(),
            "time_left": "短"
        }
        self._send_stage(witch_seat, "stage_context", ctx_payload, expect_response=False)
        self._send_stage(witch_seat, "stage_chronicle_digest", self._build_digest_payload(), expect_response=False)
        self._send_stage(witch_seat, "stage_your_notes", self._build_notes_payload(witch), expect_response=False)
        witch_action = self._send_stage(
            witch_seat,
            "stage_night_witch",
            {
                "killed_list": killed_list or "今晚无人被锁定",
                "heal_left": potions.get("heal_left", 0),
                "poison_left": potions.get("poison_left", 0),
                "alive_map": self._alive_map(),
                "alive_targets": self._alive_seats(),
            },
            expect_response=True,
        )
        if not witch_action:
            return
        if "【救人】" in witch_action and potions.get("heal_left", 0) > 0:
            target = self._parse_directive(witch_action, "救人")
            if target is not None:
                potions["heal_left"] = max(0, potions.get("heal_left", 0) - 1)
                self._night_outcome.healed_target = target
                self.chronicle.log_night_event(self.round_no, {"t": f"N{self.round_no}_witch_heal", "target": target})
        elif "【下毒】" in witch_action and potions.get("poison_left", 0) > 0:
            target = self._parse_directive(witch_action, "下毒")
            if target is not None:
                potions["poison_left"] = max(0, potions.get("poison_left", 0) - 1)
                self._night_outcome.poisoned_target = target
                self.chronicle.log_night_event(self.round_no, {"t": f"N{self.round_no}_witch_poison", "target": target})
        else:
            self.chronicle.log_night_event(self.round_no, {"t": f"N{self.round_no}_witch_idle"})
        witch.role_private["potions"] = potions

    def _daybreak(self) -> None:
        deaths = self._resolve_deaths()
        if deaths:
            announcement = ", ".join(str(seat) for seat in deaths)
            print(f"天亮公布：{announcement} 号倒下。")
        else:
            print("天亮公布：昨夜平安夜。")
        for seat in deaths:
            self._trigger_hunter_if_needed(seat, cause="night")
        self.chronicle.refresh_global_summary(f"第{self.round_no}夜结算：死亡 {deaths if deaths else '无'}")

    def _day_phase(self) -> None:
        alive_order = self._alive_seats()
        self.chronicle.ensure_round(self.round_no, order=alive_order)
        self._day_spoken = {seat: False for seat in self.players.keys()}
        for idx, seat in enumerate(alive_order, start=1):
            player = self._player(seat)
            self._send_stage(seat, "stage_life_check", {"is_alive": player.alive}, expect_response=True)
            if not player.alive:
                continue
            is_first = not any(self._day_spoken.values())
            ctx_payload = {
                "round": self.round_no,
                "stage": "DAY_TALK",
                "speaker_order": alive_order,
                "turn_index": idx,
                "is_first_in_round": is_first,
                "alive_map": self._alive_map(),
                "time_left": "适中",
                "total_speakers": len(alive_order),
            }
            self._send_stage(seat, "stage_context", ctx_payload, expect_response=False)
            self._send_stage(seat, "stage_chronicle_digest", self._build_digest_payload(), expect_response=False)
            self._send_stage(seat, "stage_your_notes", self._build_notes_payload(player), expect_response=False)
            if not self._day_spoken[seat]:
                self._send_stage(seat, "stage_opening", {"persona": player.persona, "dialect_hint": player.dialect}, expect_response=True)
            speech = self._send_stage(
                seat,
                "stage_day_talk",
                {"turn_index": idx, "total_speakers": len(alive_order)},
                expect_response=True,
            )
            if speech:
                self.chronicle.add_day_utterance(
                    self.round_no,
                    seat,
                    idx,
                    speech,
                    self._one_line_summary(speech),
                )
                self.chronicle.append_day_summary(self.round_no, self._one_line_summary(speech))
            notes_output = self._send_stage(seat, "stage_write_notes", {}, expect_response=True)
            if notes_output:
                bullets = self._extract_notes(notes_output)
                if bullets:
                    player.notes.append({"r": self.round_no, "d": "day", "bullets": bullets})
            self._day_spoken[seat] = True
        self._voting(alive_order)

    def _voting(self, order: Iterable[int]) -> None:
        vote_record = VoteRecord(round_no=self.round_no)
        alive_map = self._alive_map()
        for seat in order:
            player = self._player(seat)
            if not player.alive:
                continue
            self._send_stage(seat, "stage_life_check", {"is_alive": player.alive}, expect_response=True)
            ctx_payload = {
                "round": self.round_no,
                "stage": "VOTE",
                "speaker_order": list(order),
                "turn_index": 0,
                "is_first_in_round": False,
                "alive_map": alive_map,
                "time_left": "短",
            }
            self._send_stage(seat, "stage_context", ctx_payload, expect_response=False)
            self._send_stage(seat, "stage_chronicle_digest", self._build_digest_payload(), expect_response=False)
            self._send_stage(seat, "stage_your_notes", self._build_notes_payload(player), expect_response=False)
            vote = self._send_stage(seat, "stage_vote", {"alive_map": alive_map}, expect_response=True)
            target = self._parse_directive(vote or "", "投票") if vote else None
            target_player = self.players.get(target) if target is not None else None
            if target_player is None or not target_player.alive:
                wolves_alive = self._wolves_alive()
                target = wolves_alive[0] if wolves_alive else None
            vote_record.votes[seat] = target
            self.chronicle.add_vote(self.round_no, seat, target)
        tally = Counter(v for v in vote_record.votes.values() if v is not None)
        lynched: Optional[int] = None
        if tally:
            common = tally.most_common()
            top_vote, top_count = common[0]
            contenders = [seat for seat, cnt in common if cnt == top_count]
            lynched = self.rng.choice(contenders)
            print(f"投票结果：{lynched} 号被放逐（{top_count} 票，平票随机断定）。")
        else:
            print("投票结果：全场弃票，当轮无人出局。")
        vote_record.lynched = lynched
        self._vote_record = vote_record
        self.chronicle.set_lynch(self.round_no, lynched)
        if lynched is not None:
            target_player = self._player(lynched)
            target_player.alive = False
            self.chronicle.append_day_summary(self.round_no, f"放逐{lynched}号")
            self.chronicle.refresh_global_summary(f"第{self.round_no}日放逐：{lynched} 号")
            self._trigger_hunter_if_needed(lynched, cause="lynch")

    # --------------------------------------------------------------- helpers --
    def _resolve_deaths(self) -> List[int]:
        if not self._night_outcome:
            return []
        deaths: List[int] = []
        kill_target = self._night_outcome.kill_target
        if kill_target is not None:
            if self._night_outcome.healed_target == kill_target:
                pass
            else:
                deaths.append(kill_target)
        if self._night_outcome.poisoned_target is not None:
            deaths.append(self._night_outcome.poisoned_target)
        unique_deaths = []
        for seat in deaths:
            if seat not in unique_deaths and seat in self.players and self.players[seat].alive:
                unique_deaths.append(seat)
        for seat in unique_deaths:
            self.players[seat].alive = False
        return unique_deaths

    def _trigger_hunter_if_needed(self, seat: int, cause: str) -> None:
        player = self.players.get(seat)
        if not player or player.role != Role.HUNTER or player.hunter_has_shot:
            return
        alive_map = self._alive_map()
        response = self._send_stage(
            seat,
            "stage_hunter_trigger",
            {"alive_map": alive_map, "cause": cause},
            expect_response=True,
        )
        if not response:
            return
        if "【开枪】" in response:
            target = self._parse_directive(response, "开枪")
            if target is not None and self.players.get(target, player).alive:
                self.players[target].alive = False
                print(f"猎人 {seat} 号带走了 {target} 号！")
                self.chronicle.refresh_global_summary(f"猎人{seat}号枪杀：{target}号")
        else:
            print(f"猎人 {seat} 号选择不开枪。")
        player.hunter_has_shot = True

    def _is_finished(self) -> bool:
        wolves_alive = sum(1 for p in self.players.values() if p.alive and p.role == Role.WOLF)
        villagers_alive = sum(1 for p in self.players.values() if p.alive and p.role != Role.WOLF)
        if wolves_alive == 0:
            self._result = "villagers_win"
            return True
        if wolves_alive >= villagers_alive:
            self._result = "wolves_win"
            return True
        return False

    # --------------------------------------------------------------- postgame --
    def _build_postgame_digest(self) -> str:
        lines = ["对局关键信息复盘："]
        lines.extend(self.chronicle.global_summary)
        for round_no in sorted(self.chronicle.rounds.keys()):
            record = self.chronicle.rounds[round_no]
            lines.append(f"第{round_no}夜：" + "；".join(record.night.summary_5))
            lines.append(f"第{round_no}日：" + "；".join(record.day.summary_10))
        return "\n".join(line for line in lines if line.strip())

    def _postgame(self) -> None:
        result = getattr(self, "_result", "进行中")
        digest = self._build_postgame_digest()
        for seat, player in self.players.items():
            ctx_payload = {
                "result": result,
                "final_transcript_digest": digest,
                "your_notes_tail": player.notes[-1]["bullets"] if player.notes else [],
            }
            self._send_stage(seat, "stage_postgame_context", ctx_payload, expect_response=True)
            self._send_stage(seat, "stage_postgame_roundup", {}, expect_response=True)
            self._send_stage(seat, "stage_postgame_roast", {}, expect_response=True)
        print(f"对局结束，结果：{result}。")


