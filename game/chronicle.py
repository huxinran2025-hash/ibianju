"""公共纪要结构与工具。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class DayRecord:
    order: List[int]
    utterances: List[Dict[str, object]] = field(default_factory=list)
    votes: List[Dict[str, Optional[int]]] = field(default_factory=list)
    lynch: Optional[int] = None
    summary_10: List[str] = field(default_factory=list)


@dataclass
class NightRecord:
    events: List[Dict[str, object]] = field(default_factory=list)
    summary_5: List[str] = field(default_factory=list)


@dataclass
class RoundRecord:
    round: int
    night: NightRecord = field(default_factory=NightRecord)
    day: DayRecord = field(default_factory=lambda: DayRecord(order=[]))


@dataclass
class Chronicle:
    seats: List[int]
    rounds: Dict[int, RoundRecord] = field(default_factory=dict)
    global_summary: List[str] = field(default_factory=lambda: ["首夜进行中。"])

    def ensure_round(self, round_no: int, order: Optional[List[int]] = None) -> RoundRecord:
        if round_no not in self.rounds:
            self.rounds[round_no] = RoundRecord(round=round_no, day=DayRecord(order=order or []))
        elif order is not None:
            self.rounds[round_no].day.order = order
        return self.rounds[round_no]

    def log_night_event(self, round_no: int, event: Dict[str, object]) -> None:
        record = self.ensure_round(round_no)
        record.night.events.append(event)

    def set_night_summary(self, round_no: int, summary: List[str]) -> None:
        record = self.ensure_round(round_no)
        record.night.summary_5 = summary[:5]

    def add_day_utterance(self, round_no: int, seat: int, idx: int, text: str, one_line: str) -> None:
        record = self.ensure_round(round_no)
        record.day.utterances.append({"seat": seat, "idx": idx, "text": text, "one_line": one_line})

    def add_vote(self, round_no: int, from_seat: int, to_seat: Optional[int]) -> None:
        record = self.ensure_round(round_no)
        record.day.votes.append({"from": from_seat, "to": to_seat})

    def set_lynch(self, round_no: int, seat: Optional[int]) -> None:
        record = self.ensure_round(round_no)
        record.day.lynch = seat

    def append_day_summary(self, round_no: int, summary: str) -> None:
        record = self.ensure_round(round_no)
        if summary not in record.day.summary_10:
            record.day.summary_10.append(summary)
            record.day.summary_10 = record.day.summary_10[:10]

    def refresh_global_summary(self, text: str) -> None:
        if text not in self.global_summary:
            self.global_summary.append(text)
            if len(self.global_summary) > 6:
                self.global_summary = self.global_summary[-6:]



