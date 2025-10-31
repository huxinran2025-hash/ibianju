"""核心数据模型定义。"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class Role(str, Enum):
    """玩家身份角色。"""

    WOLF = "wolf"
    WITCH = "witch"
    HUNTER = "hunter"
    VILLAGER = "villager"


@dataclass(slots=True)
class PotionState:
    """女巫药水余量。"""

    heal_left: int = 1
    poison_left: int = 1


@dataclass(slots=True)
class SeatConfig:
    """座位配置。"""

    seat_id: int
    role: Role
    persona: str
    dialect: str


@dataclass(slots=True)
class PlayerState:
    """运行期玩家状态。"""

    seat_id: int
    role: Role
    persona: str
    dialect: str
    alive: bool = True
    trust: Dict[int, int] = field(default_factory=dict)
    notes: List[Dict] = field(default_factory=list)
    role_private: Dict[str, object] = field(default_factory=dict)
    hunter_has_shot: bool = False

    def is_wolf(self) -> bool:
        return self.role == Role.WOLF

    def ensure_trust_initialised(self, seats: List[int]) -> None:
        for sid in seats:
            self.trust.setdefault(sid, 50)


@dataclass(slots=True)
class GameConfig:
    """基础游戏配置。"""

    seating_plan: List[SeatConfig]
    max_rounds: int = 10

    @property
    def seat_ids(self) -> List[int]:
        return [seat.seat_id for seat in self.seating_plan]


@dataclass(slots=True)
class VoteRecord:
    """单轮投票记录。"""

    round_no: int
    votes: Dict[int, Optional[int]] = field(default_factory=dict)
    lynched: Optional[int] = None


@dataclass(slots=True)
class NightOutcome:
    """夜晚结算结果。"""

    kill_target: Optional[int] = None
    healed_target: Optional[int] = None
    poisoned_target: Optional[int] = None



