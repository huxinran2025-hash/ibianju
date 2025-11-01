"""测试Web API的简单脚本。"""

import json
import requests

BASE_URL = "http://127.0.0.1:3001"


def test_api():
    """测试API功能。"""
    print("=" * 50)
    print("测试狼人杀 Web API")
    print("=" * 50)

    # 1. 测试首页
    print("\n1. 获取API信息...")
    response = requests.get(f"{BASE_URL}/")
    print(f"状态码: {response.status_code}")
    print(f"响应: {json.dumps(response.json(), ensure_ascii=False, indent=2)}")

    # 2. 创建游戏
    print("\n2. 创建新游戏...")
    response = requests.post(f"{BASE_URL}/games", json={"seed": 42})
    game_data = response.json()
    print(f"状态码: {response.status_code}")
    print(f"响应: {json.dumps(game_data, ensure_ascii=False, indent=2)}")
    game_id = game_data["game_id"]

    # 3. 获取游戏状态
    print(f"\n3. 获取游戏 {game_id} 的状态...")
    response = requests.get(f"{BASE_URL}/games/{game_id}/status")
    status = response.json()
    print(f"状态码: {response.status_code}")
    print(f"状态: {json.dumps(status, ensure_ascii=False, indent=2)}")

    # 4. 运行游戏
    print(f"\n4. 运行游戏 {game_id}...")
    response = requests.post(f"{BASE_URL}/games/{game_id}/run")
    result = response.json()
    print(f"状态码: {response.status_code}")
    print(f"结果: {json.dumps(result, ensure_ascii=False, indent=2)}")

    # 5. 获取最终游戏详情
    print(f"\n5. 获取游戏 {game_id} 的详细信息...")
    response = requests.get(f"{BASE_URL}/games/{game_id}")
    details = response.json()
    print(f"状态码: {response.status_code}")
    print(f"回合数: {details.get('round')}")
    print(f"游戏结果: {details.get('result')}")
    print(f"存活玩家: {len([p for p in details.get('players', {}).values() if p.get('alive')])}")

    print("\n" + "=" * 50)
    print("测试完成！")
    print("=" * 50)


if __name__ == "__main__":
    try:
        test_api()
    except requests.exceptions.ConnectionError:
        print("错误：无法连接到服务器。请确保服务器正在运行：")
        print("  python server.py")
    except Exception as e:
        print(f"错误: {e}")


