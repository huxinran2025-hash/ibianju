# Stage Prompt — CONTEXT
【CONTEXT】
round={round}
stage={stage}
speaker_order={speaker_order}
turn_index={turn_index}
is_first_in_round={is_first_in_round}
alive_map={alive_map}
time_left={time_left}

- 明确这是第 {round} 轮、第 {turn_index}/{len(speaker_order)} 位发言。
- `is_first_in_round=true` 时需主动设定今日盘面基调。
- `alive_map` 告知哪些座位仍在游戏中。
