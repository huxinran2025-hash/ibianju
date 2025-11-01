"""Web服务器入口。"""

from game import run_server

if __name__ == "__main__":
    run_server(host="127.0.0.1", port=3001, debug=True)


