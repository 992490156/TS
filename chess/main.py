"""
国际象棋 - 人机对战
==================
功能:
  - 人机对战 (可执白/执黑)
  - AI 引擎 (Minimax + Alpha-Beta 剪枝)
  - 棋谱记录 (PGN 格式)
  - Polyglot 开局库支持 (.bin)
  - 悔棋、翻转棋盘、局面评估

运行方式:
  python main.py
"""

import sys
import os

# 确保能找到同目录下的模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gui import ChessGUI


def main():
    app = ChessGUI()
    app.run()


if __name__ == "__main__":
    main()
