# GM Orchestrator 伪代码

> 适配“无预言家、双强神”规则：夜晚仅包含狼人刀人与女巫决策，猎人只在触发时处理技能。

```python
class GameMaster:
    def __init__(self, llm_client, tts_client):
        self.llm = llm_client
        self.tts = tts_client
        self.chronicle = init_chronicle()
        self.players = init_player_notes()
        self.sessions = {}

    def setup_sessions(self, seating_plan):
        for seat in seating_plan:
            persona = seat.persona
            dialect = seat.dialect
            role = seat.role
            system_prompt = load("prompts/system_common.md").format(seat=seat.id)
            role_prompt = load(f"prompts/system_role_{role}.md").format(**role.context)
            self.sessions[seat.id] = self.llm.create_session(system_prompt + "\n" + role_prompt)
            self.players[seat.id]["persona"] = persona
            self.players[seat.id]["dialect_hint"] = dialect
        self._wolf_intro()

    def _wolf_intro(self):
        wolf_ids = [s.id for s in seats if s.role == "wolf"]
        for wid in wolf_ids:
            send_stage(wid, "stage_wolf_intro.md", wolf_mates=[i for i in wolf_ids if i != wid])

    def run_game(self):
        round_no = 1
        while not self._is_finished():
            self._run_night(round_no)
            self._daybreak(round_no)
            self._run_day(round_no)
            round_no += 1
        self._postgame()

    def _run_night(self, round_no):
        self._night_wolves(round_no)
        self._night_witch(round_no)
        update_chronicle_night(self.chronicle, round_no)

    def _night_wolves(self, round_no):
        alive_targets = alive_list(allow_wolves=True)
        for wid in wolves_alive():
            ctx = base_context(wid, round_no, stage="NIGHT_WOLVES")
            send_stage(wid, "stage_life_check.md", is_alive=is_alive(wid))
            if not is_alive(wid):
                continue
            send_stage(wid, "stage_context.md", **ctx)
            send_digest(wid)
            send_notes(wid)
            send_stage(wid, "stage_night_wolves.md", alive_targets=alive_targets)
        resolve_wolf_votes()

    def _night_witch(self, round_no):
        wid = seat_with_role("witch")
        if not wid or not is_alive(wid):
            return
        ctx = base_context(wid, round_no, stage="NIGHT_WITCH")
        send_stage(wid, "stage_life_check.md", is_alive=True)
        send_stage(wid, "stage_context.md", **ctx)
        send_digest(wid)
        send_notes(wid)
        send_stage(
            wid,
            "stage_night_witch.md",
            killed_list=current_kill_targets(),
            heal_left=potions(wid).heal,
            poison_left=potions(wid).poison,
        )
        apply_witch_actions()

    def _daybreak(self, round_no):
        resolve_deaths()
        announce_results()
        update_chronicle_daybreak(self.chronicle, round_no)

    def _run_day(self, round_no):
        order = speaker_order(round_no)
        for index, seat in enumerate(order, start=1):
            ctx = base_context(seat, round_no, stage="DAY_TALK", turn_index=index)
            send_stage(seat, "stage_life_check.md", is_alive=is_alive(seat))
            if not is_alive(seat):
                continue
            send_stage(seat, "stage_context.md", **ctx)
            send_digest(seat)
            send_notes(seat)
            if first_time_today(seat):
                send_stage(seat, "stage_opening.md", persona=persona(seat), dialect_hint=dialect(seat))
            send_stage(
                seat,
                "stage_day_talk.md",
                turn_index=index,
                total_speakers=len(order),
            )
            capture_utterance(seat)
            send_stage(seat, "stage_write_notes.md")
            store_notes(seat)
        self._voting(round_no, order)

    def _voting(self, round_no, order):
        for seat in order:
            send_stage(seat, "stage_life_check.md", is_alive=is_alive(seat))
            if not is_alive(seat):
                continue
            ctx = base_context(seat, round_no, stage="VOTE")
            send_stage(seat, "stage_context.md", **ctx)
            send_digest(seat)
            send_notes(seat)
            send_stage(seat, "stage_vote.md")
            record_vote(seat)
        resolve_votes(round_no)
        trigger_hunter_if_needed()
        update_chronicle_day(self.chronicle, round_no)

    def _postgame(self):
        result = compute_result()
        digest = build_postgame_digest(self.chronicle)
        for seat in seats:
            send_stage(seat, "stage_postgame_context.md", result=result, final_transcript_digest=digest, your_notes_tail=tail_notes(seat))
            send_stage(seat, "stage_postgame_roundup.md")
            store_roundup(seat)
            send_stage(seat, "stage_postgame_roast.md")
            store_roast(seat)
        render_final_summary(self.chronicle, digest)
```
