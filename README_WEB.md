# 狼人杀 Web API 使用说明

## 启动服务器

```bash
python server.py
```

服务器将在 `http://127.0.0.1:3001` 启动。

## API 接口

### 1. 获取API信息
```
GET http://127.0.0.1:3001/
```

### 2. 创建新游戏
```
POST http://127.0.0.1:3001/games
Content-Type: application/json

{
  "seed": 42  // 可选，随机种子
}
```

响应：
```json
{
  "game_id": "game_1",
  "status": "running",
  "message": "游戏已创建并初始化"
}
```

### 3. 获取游戏详情
```
GET http://127.0.0.1:3001/games/{game_id}
```

### 4. 获取游戏状态
```
GET http://127.0.0.1:3001/games/{game_id}/status
```

### 5. 自动运行完整游戏
```
POST http://127.0.0.1:3001/games/{game_id}/run
```

游戏将自动运行直到结束。

### 6. 单步执行游戏
```
POST http://127.0.0.1:3001/games/{game_id}/step
```

每次调用执行一个完整回合（夜晚 + 天亮 + 白天）。

### 7. 列出所有游戏
```
GET http://127.0.0.1:3001/games
```

## 使用示例

### 使用 curl

```bash
# 创建游戏
curl -X POST http://127.0.0.1:3001/games \
  -H "Content-Type: application/json" \
  -d '{"seed": 42}'

# 运行游戏
curl -X POST http://127.0.0.1:3001/games/game_1/run

# 查看游戏状态
curl http://127.0.0.1:3001/games/game_1/status

# 获取游戏详情
curl http://127.0.0.1:3001/games/game_1
```

### 使用 Python requests

```python
import requests

base_url = "http://127.0.0.1:3001"

# 创建游戏
response = requests.post(f"{base_url}/games", json={"seed": 42})
game = response.json()
game_id = game["game_id"]

# 运行游戏
requests.post(f"{base_url}/games/{game_id}/run")

# 获取游戏详情
details = requests.get(f"{base_url}/games/{game_id}").json()
print(details)
```


