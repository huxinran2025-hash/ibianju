"""Web服务器接口。"""

from __future__ import annotations

import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Optional

from flask import Flask, jsonify, request

from .chronicle import Chronicle
from .cli import build_default_config
from .gm import GameMaster
from .llm import RuleBasedLLMClient
from .models import GameConfig, PlayerState, Role
from .prompts import PromptRepository


@dataclass
class GameSession:
    """游戏会话。"""

    game_id: str
    gm: GameMaster
    status: str  # "setup", "running", "finished"
    logs: list


app = Flask(__name__)
app.json.ensure_ascii = False

# 游戏会话存储（生产环境应使用数据库）
_games: Dict[str, GameSession] = {}
_game_counter = 0


def _create_game_id() -> str:
    global _game_counter
    _game_counter += 1
    return f"game_{_game_counter}"


def _ensure_prompts_dir() -> Path:
    prompt_dir = Path(__file__).resolve().parent.parent / "prompts"
    if not prompt_dir.exists() or not prompt_dir.is_dir():
        raise FileNotFoundError(f"未找到 prompts 目录：{prompt_dir}")
    return prompt_dir


def _serialize_player_state(player: PlayerState) -> dict:
    """序列化玩家状态，隐藏私有信息。"""
    return {
        "seat_id": player.seat_id,
        "role": player.role.value if isinstance(player.role, Role) else player.role,
        "persona": player.persona,
        "dialect": player.dialect,
        "alive": player.alive,
        "trust": player.trust,
    }


def _serialize_chronicle(chronicle: Chronicle) -> dict:
    """序列化游戏纪要。"""
    rounds_data = {}
    for round_no, record in chronicle.rounds.items():
        rounds_data[round_no] = {
            "round": record.round,
            "night": {
                "events": record.night.events,
                "summary_5": record.night.summary_5,
            },
            "day": {
                "order": record.day.order,
                "utterances": record.day.utterances,
                "votes": record.day.votes,
                "lynch": record.day.lynch,
                "summary_10": record.day.summary_10,
            },
        }
    return {
        "seats": chronicle.seats,
        "rounds": rounds_data,
        "global_summary": chronicle.global_summary,
    }


@app.route("/", methods=["GET"])
def index():
    """API首页。"""
    return jsonify({
        "name": "狼人杀 AI 游戏服务器",
        "version": "1.0.0",
        "endpoints": {
            "POST /games": "创建新游戏",
            "GET /games/<game_id>": "获取游戏详情",
            "GET /games/<game_id>/status": "获取游戏状态",
            "POST /games/<game_id>/run": "执行游戏（自动运行到结束）",
            "POST /games/<game_id>/step": "执行一步（单个阶段）",
            "GET /games": "列出所有游戏",
        },
    })


@app.route("/games", methods=["POST"])
def create_game():
    """创建新游戏。"""
    data = request.get_json() or {}
    seed = data.get("seed")
    game_id = _create_game_id()

    rng = random.Random(seed)
    prompt_dir = _ensure_prompts_dir()
    prompt_repo = PromptRepository(base_dir=prompt_dir)

    config = build_default_config()
    llm_client = RuleBasedLLMClient(rng=rng)
    gm = GameMaster(config=config, prompt_repo=prompt_repo, llm_client=llm_client, rng=rng)

    session = GameSession(
        game_id=game_id,
        gm=gm,
        status="setup",
        logs=[],
    )

    gm.setup()
    session.status = "running"
    _games[game_id] = session

    return jsonify({
        "game_id": game_id,
        "status": session.status,
        "message": "游戏已创建并初始化",
    }), 201


@app.route("/games", methods=["GET"])
def list_games():
    """列出所有游戏。"""
    return jsonify({
        "games": [
            {
                "game_id": session.game_id,
                "status": session.status,
                "round": session.gm.round_no,
            }
            for session in _games.values()
        ]
    })


@app.route("/games/<game_id>", methods=["GET"])
def get_game(game_id: str):
    """获取游戏详情。"""
    if game_id not in _games:
        return jsonify({"error": "游戏不存在"}), 404

    session = _games[game_id]
    gm = session.gm

    players_data = {str(seat): _serialize_player_state(player) for seat, player in gm.players.items()}

    return jsonify({
        "game_id": game_id,
        "status": session.status,
        "round": gm.round_no,
        "result": getattr(gm, "_result", "ongoing"),
        "players": players_data,
        "chronicle": _serialize_chronicle(gm.chronicle),
    })


@app.route("/games/<game_id>/status", methods=["GET"])
def get_status(game_id: str):
    """获取游戏状态摘要。"""
    if game_id not in _games:
        return jsonify({"error": "游戏不存在"}), 404

    session = _games[game_id]
    gm = session.gm

    alive_seats = gm._alive_seats()
    wolves_alive = gm._wolves_alive()
    villagers_alive = [seat for seat in alive_seats if seat not in wolves_alive]

    return jsonify({
        "game_id": game_id,
        "status": session.status,
        "round": gm.round_no,
        "result": getattr(gm, "_result", "ongoing"),
        "alive_seats": alive_seats,
        "wolves_alive": wolves_alive,
        "villagers_alive": villagers_alive,
        "is_finished": gm._is_finished(),
    })


@app.route("/games/<game_id>/run", methods=["POST"])
def run_game(game_id: str):
    """自动运行游戏直到结束。"""
    if game_id not in _games:
        return jsonify({"error": "游戏不存在"}), 404

    session = _games[game_id]
    if session.status == "finished":
        return jsonify({"error": "游戏已结束"}), 400

    try:
        session.gm.run_game()
        session.status = "finished"
        return jsonify({
            "game_id": game_id,
            "status": session.status,
            "result": session.gm._result,
            "round": session.gm.round_no,
            "message": "游戏执行完成",
        })
    except Exception as e:
        return jsonify({"error": f"执行失败: {str(e)}"}), 500


@app.route("/games/<game_id>/step", methods=["POST"])
def step_game(game_id: str):
    """执行游戏的一个阶段。"""
    if game_id not in _games:
        return jsonify({"error": "游戏不存在"}), 404

    session = _games[game_id]
    if session.status == "finished":
        return jsonify({"error": "游戏已结束"}), 400

    gm = session.gm
    if gm._is_finished():
        session.status = "finished"
        return jsonify({
            "game_id": game_id,
            "status": "finished",
            "result": gm._result,
            "message": "游戏已结束",
        })

    # 执行一个阶段：夜晚 -> 天亮 -> 白天
    try:
        current_round = gm.round_no
        gm._night_phase()
        if gm._is_finished():
            session.status = "finished"
            return jsonify({
                "game_id": game_id,
                "status": "finished",
                "result": gm._result,
                "round": gm.round_no,
                "phase": "night",
                "message": "游戏在夜晚阶段结束",
            })

        gm._daybreak()
        if gm._is_finished():
            session.status = "finished"
            return jsonify({
                "game_id": game_id,
                "status": "finished",
                "result": gm._result,
                "round": gm.round_no,
                "phase": "daybreak",
                "message": "游戏在天亮阶段结束",
            })

        gm._day_phase()
        gm.round_no += 1

        if gm._is_finished():
            gm._postgame()
            session.status = "finished"

        return jsonify({
            "game_id": game_id,
            "status": session.status,
            "round": current_round,
            "phase": "day",
            "is_finished": gm._is_finished(),
            "message": f"第{current_round}轮执行完成",
        })
    except Exception as e:
        return jsonify({"error": f"执行失败: {str(e)}"}), 500


def run_server(host: str = "127.0.0.1", port: int = 3001, debug: bool = False):
    """启动Web服务器。"""
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    run_server()


