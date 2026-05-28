"""
国际象棋引擎 - 游戏逻辑、AI、PGN记录、开局库
"""

import chess
import chess.pgn
import chess.polyglot
import random
import math
import os
from datetime import datetime

# ---------------------------------------------------------------------------
# 子力估值 (centipawn)
# ---------------------------------------------------------------------------
PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 20000,
}

# ---------------------------------------------------------------------------
# 棋子-位置价值表 (from white's perspective, 8x8, A1=0, H8=63)
# 数据来源: https://www.chessprogramming.org/Simplified_Evaluation_Function
# ---------------------------------------------------------------------------
PAWN_TABLE = [
    0,  0,  0,  0,  0,  0,  0,  0,
    50, 50, 50, 50, 50, 50, 50, 50,
    10, 10, 20, 30, 30, 20, 10, 10,
    5,  5, 10, 25, 25, 10,  5,  5,
    0,  0,  0, 20, 20,  0,  0,  0,
    5, -5,-10,  0,  0,-10, -5,  5,
    5, 10, 10,-20,-20, 10, 10,  5,
    0,  0,  0,  0,  0,  0,  0,  0,
]

KNIGHT_TABLE = [
    -50,-40,-30,-30,-30,-30,-40,-50,
    -40,-20,  0,  0,  0,  0,-20,-40,
    -30,  0, 10, 15, 15, 10,  0,-30,
    -30,  5, 15, 20, 20, 15,  5,-30,
    -30,  0, 15, 20, 20, 15,  0,-30,
    -30,  5, 10, 15, 15, 10,  5,-30,
    -40,-20,  0,  5,  5,  0,-20,-40,
    -50,-40,-30,-30,-30,-30,-40,-50,
]

BISHOP_TABLE = [
    -20,-10,-10,-10,-10,-10,-10,-20,
    -10,  0,  0,  0,  0,  0,  0,-10,
    -10,  0,  5, 10, 10,  5,  0,-10,
    -10,  5,  5, 10, 10,  5,  5,-10,
    -10,  0, 10, 10, 10, 10,  0,-10,
    -10, 10, 10, 10, 10, 10, 10,-10,
    -10,  5,  0,  0,  0,  0,  5,-10,
    -20,-10,-10,-10,-10,-10,-10,-20,
]

ROOK_TABLE = [
    0,  0,  0,  0,  0,  0,  0,  0,
    5, 10, 10, 10, 10, 10, 10,  5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    0,  0,  0,  5,  5,  0,  0,  0,
]

QUEEN_TABLE = [
    -20,-10,-10, -5, -5,-10,-10,-20,
    -10,  0,  0,  0,  0,  0,  0,-10,
    -10,  0,  5,  5,  5,  5,  0,-10,
    -5,  0,  5,  5,  5,  5,  0, -5,
    0,  0,  5,  5,  5,  5,  0, -5,
    -10,  5,  5,  5,  5,  5,  0,-10,
    -10,  0,  5,  0,  0,  0,  0,-10,
    -20,-10,-10, -5, -5,-10,-10,-20,
]

KING_TABLE = [
    -30,-40,-40,-50,-50,-40,-40,-30,
    -30,-40,-40,-50,-50,-40,-40,-30,
    -30,-40,-40,-50,-50,-40,-40,-30,
    -30,-40,-40,-50,-50,-40,-40,-30,
    -20,-30,-30,-40,-40,-30,-30,-20,
    -10,-20,-20,-20,-20,-20,-20,-10,
    20, 20,  0,  0,  0,  0, 20, 20,
    20, 30, 10,  0,  0, 10, 30, 20,
]

PIECE_TABLES = {
    chess.PAWN: PAWN_TABLE,
    chess.KNIGHT: KNIGHT_TABLE,
    chess.BISHOP: BISHOP_TABLE,
    chess.ROOK: ROOK_TABLE,
    chess.QUEEN: QUEEN_TABLE,
    chess.KING: KING_TABLE,
}


def _mirror_square(sq: int) -> int:
    """将黑方视角的格子镜像为白方视角 (rank 翻转)"""
    return chess.square_mirror(sq)


def evaluate_board(board: chess.Board) -> float:
    """评估局面，返回白方视角的分数 (centipawn)"""
    if board.is_checkmate():
        return -PIECE_VALUES[chess.KING] if board.turn == chess.WHITE else PIECE_VALUES[chess.KING]
    if board.is_stalemate() or board.is_insufficient_material():
        return 0

    score = 0.0
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece is None:
            continue

        val = PIECE_VALUES[piece.piece_type]
        table = PIECE_TABLES[piece.piece_type]

        if piece.color == chess.WHITE:
            score += val
            score += table[square]
        else:
            score -= val
            score -= table[_mirror_square(square)]

    # 机动性加分: 合法走法数量
    mobility = len(list(board.legal_moves))
    if board.turn == chess.WHITE:
        score += mobility * 2
    else:
        score -= mobility * 2

    return score


def _move_ordering_key(move: chess.Move, board: chess.Board) -> tuple:
    """走法排序: 吃子优先 (MVV-LVA), 然后是其他"""
    captured = board.piece_at(move.to_square)
    if captured is not None:
        attacker = board.piece_at(move.from_square)
        return (0, -PIECE_VALUES[captured.piece_type],
                PIECE_VALUES[attacker.piece_type] if attacker else 0)
    # 兵升变优先
    if move.promotion:
        return (1, -PIECE_VALUES[move.promotion])
    return (2, 0)


# ---------------------------------------------------------------------------
# AI 引擎
# ---------------------------------------------------------------------------
class ChessAI:
    """国际象棋 AI，使用 Minimax + Alpha-Beta 剪枝"""

    def __init__(self, depth: int = 3):
        self.depth = depth
        self.nodes_searched = 0

    def _order_moves(self, board: chess.Board) -> list:
        moves = list(board.legal_moves)
        moves.sort(key=lambda m: _move_ordering_key(m, board))
        return moves

    def _minimax(self, board: chess.Board, depth: int, alpha: float,
                 beta: float, is_maximizing: bool) -> float:
        self.nodes_searched += 1
        if depth == 0 or board.is_game_over():
            return evaluate_board(board)

        if is_maximizing:
            value = -float("inf")
            for move in self._order_moves(board):
                board.push(move)
                value = max(value, self._minimax(board, depth - 1,
                                                  alpha, beta, False))
                board.pop()
                alpha = max(alpha, value)
                if beta <= alpha:
                    break
            return value
        else:
            value = float("inf")
            for move in self._order_moves(board):
                board.push(move)
                value = min(value, self._minimax(board, depth - 1,
                                                  alpha, beta, True))
                board.pop()
                beta = min(beta, value)
                if beta <= alpha:
                    break
            return value

    def best_move(self, board: chess.Board) -> chess.Move | None:
        """返回当前局面的最佳走法"""
        if board.is_game_over():
            return None

        self.nodes_searched = 0
        is_maximizing = board.turn == chess.WHITE
        best = None
        best_value = -float("inf") if is_maximizing else float("inf")

        for move in self._order_moves(board):
            board.push(move)
            value = self._minimax(board, self.depth - 1,
                                   -float("inf"), float("inf"),
                                   not is_maximizing)
            board.pop()

            if is_maximizing:
                if value > best_value:
                    best_value = value
                    best = move
            else:
                if value < best_value:
                    best_value = value
                    best = move

        return best


# ---------------------------------------------------------------------------
# 开局库
# ---------------------------------------------------------------------------
class OpeningBook:
    """Polyglot 开局库支持"""

    def __init__(self):
        self.reader = None
        self.book_path = None

    def load(self, path: str) -> bool:
        """加载 .bin 开局库文件"""
        if not os.path.isfile(path):
            self.reader = None
            self.book_path = None
            return False
        try:
            self.reader = chess.polyglot.open_reader(path)
            self.book_path = path
            return True
        except Exception:
            self.reader = None
            self.book_path = None
            return False

    def close(self):
        if self.reader:
            self.reader.close()
            self.reader = None

    def get_move(self, board: chess.Board) -> chess.Move | None:
        """从开局库中查找当前局面的走法 (加权随机)"""
        if self.reader is None:
            return None
        try:
            entry = self.reader.choice(board, random=True)
            return entry.move if entry else None
        except Exception:
            return None

    def has_position(self, board: chess.Board) -> bool:
        """检查当前局面是否在开局库中"""
        if self.reader is None:
            return False
        try:
            return len(self.reader.find(board)) > 0
        except Exception:
            return False

    @staticmethod
    def find_books(search_path: str = ".") -> list[str]:
        """在指定目录下查找 .bin 开局库文件"""
        result = []
        for f in os.listdir(search_path):
            if f.lower().endswith(".bin") and os.path.isfile(os.path.join(search_path, f)):
                result.append(os.path.join(search_path, f))
        return result


# ---------------------------------------------------------------------------
# 游戏管理器
# ---------------------------------------------------------------------------
class GameManager:
    """管理整局游戏：棋盘、走法、PGN、AI、开局库"""

    def __init__(self, ai_depth: int = 3):
        self.board = chess.Board()
        self.ai = ChessAI(depth=ai_depth)
        self.opening_book = OpeningBook()
        self.move_history_san: list[str] = []   # SAN 表示
        self.move_history_uci: list[chess.Move] = []  # Move 对象
        self.current_move_index = -1
        self.player_color = chess.WHITE  # 玩家执白
        self.game_over = False
        self.game_result = "*"    # PGN result

        # 玩家和电脑名称
        self.player_name = "Player"
        self.ai_name = f"AI (Depth {ai_depth})"

    def new_game(self, player_color: chess.Color = chess.WHITE):
        """开始新游戏"""
        self.board.reset()
        self.move_history_san.clear()
        self.move_history_uci.clear()
        self.current_move_index = -1
        self.player_color = player_color
        self.game_over = False
        self.game_result = "*"

    def make_move(self, move: chess.Move) -> bool:
        """执行一步棋，返回是否成功"""
        if self.game_over:
            return False
        if move not in self.board.legal_moves:
            return False

        san = self.board.san(move)
        self.board.push(move)
        self.move_history_san.append(san)
        self.move_history_uci.append(move)
        self.current_move_index += 1

        # 检测游戏是否结束
        self._check_game_end()
        return True

    def undo_move(self) -> bool:
        """悔棋一步 (如果是 AI 走完后的回合，退回两步)"""
        if self.current_move_index < 0:
            return False

        # 如果是 AI 走完之后悔棋，撤销 AI 的棋 + 玩家的棋
        steps_back = 2 if len(self.move_history_uci) >= 2 \
                        and self._is_ai_turn_before_last() else 1

        for _ in range(steps_back):
            if self.current_move_index >= 0:
                self.board.pop()
                self.move_history_san.pop()
                self.move_history_uci.pop()
                self.current_move_index -= 1

        self.game_over = False
        self.game_result = "*"
        return True

    def _is_ai_turn_before_last(self) -> bool:
        """判断上一步是否是 AI 走的"""
        if self.current_move_index < 0:
            return False
        total_moves = self.current_move_index + 1
        if self.player_color == chess.WHITE:
            # 白方是玩家：奇数步数(0-indexed)是AI
            return total_moves % 2 == 0
        else:
            # 黑方是玩家：偶数步数(0-indexed)是AI
            return total_moves % 2 == 1

    def is_player_turn(self) -> bool:
        """当前是否轮到玩家走棋"""
        if self.game_over:
            return False
        return self.board.turn == self.player_color

    def ai_move(self) -> chess.Move | None:
        """AI 走棋，返回走的棋"""
        if self.game_over:
            return None
        if self.board.turn == self.player_color:
            return None

        # 先查开局库
        move = self.opening_book.get_move(self.board)
        if move is None:
            move = self.ai.best_move(self.board)

        if move and self.make_move(move):
            return move
        return None

    def _check_game_end(self):
        """检测对局是否结束"""
        if self.board.is_checkmate():
            self.game_over = True
            winner = "White" if self.board.turn == chess.BLACK else "Black"
            self.game_result = "1-0" if winner == "White" else "0-1"
        elif self.board.is_stalemate():
            self.game_over = True
            self.game_result = "1/2-1/2"
        elif self.board.is_insufficient_material():
            self.game_over = True
            self.game_result = "1/2-1/2"
        elif self.board.is_fifty_moves():
            self.game_over = True
            self.game_result = "1/2-1/2"
        elif self.board.is_repetition():
            self.game_over = True
            self.game_result = "1/2-1/2"

    def get_pgn(self) -> str:
        """导出 PGN 格式的棋谱"""
        game = chess.pgn.Game()
        game.headers["Event"] = "Chess Game"
        game.headers["Site"] = "Local"
        game.headers["Date"] = datetime.now().strftime("%Y.%m.%d")
        game.headers["Round"] = "-"
        game.headers["White"] = self.player_name if self.player_color == chess.WHITE else self.ai_name
        game.headers["Black"] = self.ai_name if self.player_color == chess.WHITE else self.player_name
        game.headers["Result"] = self.game_result

        node = game
        for move in self.move_history_uci:
            node = node.add_variation(move)

        # 添加评价注释
        exporter = chess.pgn.StringExporter(headers=True, variations=True, comments=True)
        return game.accept(exporter)

    def load_pgn(self, pgn_text: str) -> bool:
        """从 PGN 文本加载对局"""
        try:
            game = chess.pgn.read_game(pgn_text)
            if game is None:
                return False

            self.new_game()

            # 设置玩家和AI颜色
            white_name = game.headers.get("White", "Player")
            black_name = game.headers.get("Black", "AI")

            node = game
            while node.variations:
                next_node = node.variation(0)
                move = next_node.move
                if move and move in self.board.legal_moves:
                    self.board.push(move)
                    self.move_history_san.append(self.board.san(move))
                    self.move_history_uci.append(move)
                    self.current_move_index += 1
                node = next_node

            self._check_game_end()
            return True
        except Exception:
            return False

    def get_result_text(self) -> str:
        """获取结果描述"""
        if not self.game_over:
            return ""
        if self.game_result == "1-0":
            return "白方胜! (1-0)"
        elif self.game_result == "0-1":
            return "黑方胜! (0-1)"
        elif self.game_result == "1/2-1/2":
            return "和棋! (1/2-1/2)"
        return ""

    def get_last_move(self) -> chess.Move | None:
        """获取最后一步棋"""
        if self.move_history_uci:
            return self.move_history_uci[-1]
        return None
