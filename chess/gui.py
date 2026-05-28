"""
国际象棋 GUI - 基于 tkinter 的图形界面
"""

import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
from datetime import datetime
import chess
from engine import GameManager, OpeningBook, evaluate_board


# ---------------------------------------------------------------------------
# 界面配色方案
# ---------------------------------------------------------------------------
COLOR_LIGHT = "#F0D9B5"
COLOR_DARK = "#B58863"
COLOR_SELECTED = "#829769"
COLOR_LAST_MOVE = "#CDC93C"
COLOR_LEGAL_MOVE = "#52C452"
COLOR_LEGAL_CAPTURE = "#C45252"
COLOR_CHECK = "#FF6B6B"
COLOR_BG = "#2D2D2D"
COLOR_PANEL_BG = "#3C3C3C"
COLOR_TEXT = "#FFFFFF"
COLOR_BUTTON_BG = "#5A5A5A"
COLOR_BUTTON_FG = "#FFFFFF"

SQUARE_SIZE_DEFAULT = 64
PIECE_UNICODE = {
    chess.PAWN: {chess.WHITE: "♙", chess.BLACK: "♟"},
    chess.KNIGHT: {chess.WHITE: "♘", chess.BLACK: "♞"},
    chess.BISHOP: {chess.WHITE: "♗", chess.BLACK: "♝"},
    chess.ROOK: {chess.WHITE: "♖", chess.BLACK: "♜"},
    chess.QUEEN: {chess.WHITE: "♕", chess.BLACK: "♛"},
    chess.KING: {chess.WHITE: "♔", chess.BLACK: "♚"},
}

FILE_LABELS = ["a", "b", "c", "d", "e", "f", "g", "h"]
RANK_LABELS = ["8", "7", "6", "5", "4", "3", "2", "1"]


class ChessGUI:
    """国际象棋图形界面"""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("国际象棋 - 人机对战")
        self.root.configure(bg=COLOR_BG)
        self.root.resizable(False, False)

        # 动态棋盘尺寸
        self.square_size = SQUARE_SIZE_DEFAULT
        self.board_px = self.square_size * 8
        self.fullscreen = False

        # 游戏管理器
        self.game = GameManager(ai_depth=3)

        # 界面状态
        self.selected_square: int | None = None
        self.legal_moves_for_selected: set = set()
        self.flipped = False  # 棋盘是否翻转 (黑方在下)

        # 自动保存目录
        self.pgn_dir = os.path.dirname(os.path.abspath(__file__))

        # 尝试自动加载开局库
        self._auto_load_book()

        # 构建界面
        self._build_ui()

        # 更新显示
        self._update_display()

        # 键盘绑定
        self.root.bind("<F11>", lambda e: self._toggle_fullscreen())
        self.root.bind("<Escape>", lambda e: self._exit_fullscreen())

        # 如果玩家执黑，AI 先走
        self.root.after(300, self._check_ai_turn)

    def _auto_load_book(self):
        """自动加载同目录下的 .bin 开局库"""
        app_dir = os.path.dirname(os.path.abspath(__file__))
        books = OpeningBook.find_books(app_dir)
        if books:
            self.game.opening_book.load(books[0])

    # -----------------------------------------------------------------------
    # UI 构建
    # -----------------------------------------------------------------------
    def _build_ui(self):
        self.root.grid_columnconfigure(0, weight=0)
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(0, weight=0)
        self.root.grid_rowconfigure(1, weight=1)

        # 顶部信息栏
        self._build_header()
        # 主区域
        self._build_main()
        # 底部状态栏
        self._build_statusbar()

    def _build_header(self):
        header = tk.Frame(self.root, bg=COLOR_PANEL_BG, height=40)
        header.grid(row=0, column=0, columnspan=2, sticky="ew", padx=2, pady=(2, 0))
        header.grid_propagate(False)

        self.lbl_info = tk.Label(
            header, text="轮到你走棋 (白方)", bg=COLOR_PANEL_BG,
            fg=COLOR_TEXT, font=("Microsoft YaHei", 12, "bold")
        )
        self.lbl_info.pack(side=tk.LEFT, padx=15, pady=5)

        self.lbl_book = tk.Label(
            header, text="", bg=COLOR_PANEL_BG, fg="#AAAAAA",
            font=("Microsoft YaHei", 9)
        )
        self.lbl_book.pack(side=tk.RIGHT, padx=15, pady=5)

    def _build_main(self):
        main = tk.Frame(self.root, bg=COLOR_BG)
        main.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=2, pady=2)
        main.grid_columnconfigure(0, weight=0)
        main.grid_columnconfigure(1, weight=1)

        # 棋盘
        board_frame = tk.Frame(main, bg=COLOR_BG)
        board_frame.grid(row=0, column=0, sticky="w", padx=(10, 5), pady=5)
        self._build_board(board_frame)

        # 右侧面板
        right = tk.Frame(main, bg=COLOR_PANEL_BG, relief=tk.RIDGE, bd=2)
        right.grid(row=0, column=1, sticky="nsew", padx=(5, 10), pady=5)
        right.grid_rowconfigure(1, weight=1)
        right.grid_columnconfigure(0, weight=1)
        self._build_right_panel(right)

    def _build_board(self, parent):
        # 棋盘 Canvas（坐标直接画在画布上，随棋盘大小自适应）
        self.canvas = tk.Canvas(
            parent, width=self.board_px, height=self.board_px,
            highlightthickness=0
        )
        self.canvas.grid(row=0, column=0)
        self.canvas.bind("<Button-1>", self._on_click)

        # 绘制棋盘格 + 坐标
        self._draw_board_squares()

    def _draw_board_squares(self):
        self.canvas.delete("square")
        self.canvas.delete("coord")
        for row in range(8):
            for col in range(8):
                x1 = col * self.square_size
                y1 = row * self.square_size
                x2 = x1 + self.square_size
                y2 = y1 + self.square_size
                color = COLOR_LIGHT if (row + col) % 2 == 0 else COLOR_DARK
                self.canvas.create_rectangle(
                    x1, y1, x2, y2, fill=color, outline="",
                    tags=("square",)
                )

        # 坐标标签 - 在棋盘边缘绘制小字 (不占用额外空间)
        fs = max(7, self.square_size // 9)
        # 文件标签 a-h (底部)
        for col in range(8):
            x = col * self.square_size + self.square_size // 2
            y = 8 * self.square_size - 3
            self.canvas.create_text(
                x, y, text=FILE_LABELS[col],
                font=("Microsoft YaHei", fs),
                fill="#444", anchor="s", tags="coord"
            )
        # 行标签 1-8 (右侧)
        for row in range(8):
            x = 8 * self.square_size - 3
            y = row * self.square_size + self.square_size // 2
            self.canvas.create_text(
                x, y, text=RANK_LABELS[row],
                font=("Microsoft YaHei", fs),
                fill="#444", anchor="e", tags="coord"
            )

    def _build_right_panel(self, parent):
        # 标题
        title = tk.Label(parent, text="棋谱记录", bg=COLOR_PANEL_BG,
                         fg=COLOR_TEXT, font=("Microsoft YaHei", 11, "bold"))
        title.grid(row=0, column=0, pady=(10, 5))

        # 棋谱文本区域
        text_frame = tk.Frame(parent, bg=COLOR_PANEL_BG)
        text_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        text_frame.grid_rowconfigure(0, weight=1)
        text_frame.grid_columnconfigure(0, weight=1)

        self.txt_moves = tk.Text(
            text_frame, wrap=tk.WORD, font=("Consolas", 10),
            bg="#2A2A2A", fg="#E0E0E0", relief=tk.SUNKEN, bd=1,
            state=tk.DISABLED
        )
        self.txt_moves.grid(row=0, column=0, sticky="nsew")

        scrollbar = tk.Scrollbar(text_frame, command=self.txt_moves.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.txt_moves.configure(yscrollcommand=scrollbar.set)

        # 局面评估
        self.lbl_eval = tk.Label(parent, text="", bg=COLOR_PANEL_BG,
                                  fg="#BBBBBB", font=("Consolas", 10))
        self.lbl_eval.grid(row=2, column=0, pady=(0, 5))

        # 按钮
        btn_frame = tk.Frame(parent, bg=COLOR_PANEL_BG)
        btn_frame.grid(row=3, column=0, pady=(5, 15))

        self._create_button(btn_frame, "新游戏", self._on_new_game, 0)
        self._create_button(btn_frame, "悔棋", self._on_undo, 1)
        self._create_button(btn_frame, "翻转棋盘", self._on_flip, 2)
        self._create_button(btn_frame, "保存PGN", self._on_save_pgn, 3)
        self._create_button(btn_frame, "加载PGN", self._on_load_pgn, 4)
        self._create_button(btn_frame, "加载开局库", self._on_load_book, 5)
        self._create_button(btn_frame, "全屏", self._toggle_fullscreen, 6)

    def _create_button(self, parent, text, command, col):
        btn = tk.Button(
            parent, text=text, command=command,
            bg=COLOR_BUTTON_BG, fg=COLOR_BUTTON_FG,
            font=("Microsoft YaHei", 9),
            relief=tk.RAISED, bd=2, padx=10, pady=3,
            activebackground="#6A6A6A", activeforeground="#FFFFFF"
        )
        btn.grid(row=0, column=col, padx=3)

    def _build_statusbar(self):
        self.status_bar = tk.Label(
            self.root, text="就绪", bg=COLOR_PANEL_BG, fg="#AAAAAA",
            font=("Microsoft YaHei", 9), anchor=tk.W
        )
        self.status_bar.grid(row=2, column=0, columnspan=2, sticky="ew",
                              padx=2, pady=(0, 2))

    # -----------------------------------------------------------------------
    # 全屏功能
    # -----------------------------------------------------------------------
    def _toggle_fullscreen(self):
        self.fullscreen = not self.fullscreen
        self.root.attributes("-fullscreen", self.fullscreen)

        if self.fullscreen:
            self.root.resizable(True, True)
            screen_w = self.root.winfo_screenwidth()
            screen_h = self.root.winfo_screenheight()
            # 右侧面板约 250px，顶部/底部约 100px
            avail_w = screen_w - 260
            avail_h = screen_h - 100
            max_px = min(avail_w, avail_h)
            self.square_size = max(40, min(128, max_px // 8))
        else:
            self.square_size = SQUARE_SIZE_DEFAULT
            self.root.resizable(False, False)

        self.board_px = self.square_size * 8
        self.canvas.config(width=self.board_px, height=self.board_px)
        self._draw_board_squares()
        self._update_display()

    def _exit_fullscreen(self):
        if self.fullscreen:
            self._toggle_fullscreen()

    # -----------------------------------------------------------------------
    # 事件处理
    # -----------------------------------------------------------------------
    def _on_click(self, event):
        if not self.game.is_player_turn():
            return

        col = event.x // self.square_size
        row = event.y // self.square_size

        if not (0 <= col < 8 and 0 <= row < 8):
            return

        square = self._canvas_to_square(col, row)
        piece = self.game.board.piece_at(square)

        # 如果点击的是已选中棋子 → 取消选择
        if square == self.selected_square:
            self.selected_square = None
            self.legal_moves_for_selected = set()
            self._update_display()
            return

        # 如果点击的是己方棋子 → 选中它
        if piece and piece.color == self.game.player_color:
            self.selected_square = square
            self.legal_moves_for_selected = set()
            for move in self.game.board.legal_moves:
                if move.from_square == square:
                    self.legal_moves_for_selected.add(move.to_square)
            self._update_display()
            return

        # 如果点击的是合法目标格 → 走棋
        if self.selected_square is not None and square in self.legal_moves_for_selected:
            # 构造走法
            from_sq = self.selected_square
            piece = self.game.board.piece_at(from_sq)

            # 兵升变：自动升变为后
            promotion = None
            if piece and piece.piece_type == chess.PAWN:
                rank = chess.square_rank(square)
                if rank == 0 or rank == 7:
                    promotion = chess.QUEEN

            move = chess.Move(from_sq, square, promotion=promotion)

            # 尝试车王易位
            if piece and piece.piece_type == chess.KING and abs(square - from_sq) == 2:
                for legal_move in self.game.board.legal_moves:
                    if legal_move.from_square == from_sq and legal_move.to_square == square:
                        move = legal_move
                        break

            if self.game.make_move(move):
                self.selected_square = None
                self.legal_moves_for_selected = set()
                self._update_display()

                # 检查游戏是否结束
                if self.game.game_over:
                    self._show_game_result()
                else:
                    # AI 走棋
                    self.root.after(200, self._do_ai_move)

    def _on_new_game(self):
        menu = tk.Menu(self.root, tearoff=0, bg=COLOR_PANEL_BG, fg=COLOR_TEXT)
        menu.add_command(label="执白 (先手)", command=lambda: self._start_new(chess.WHITE))
        menu.add_command(label="执黑 (后手)", command=lambda: self._start_new(chess.BLACK))
        menu.post(self.root.winfo_pointerx(), self.root.winfo_pointery())

    def _start_new(self, color):
        depth = simpledialog.askinteger("AI难度",
                                         "请选择AI搜索深度 (2-6，越大越强):",
                                         initialvalue=3, minvalue=2, maxvalue=6,
                                         parent=self.root)
        if depth is None:
            depth = 3
        self.game = GameManager(ai_depth=depth)

        # 重新加载开局库
        books = OpeningBook.find_books(os.path.dirname(os.path.abspath(__file__)))
        if books:
            self.game.opening_book.load(books[0])

        self.game.new_game(player_color=color)
        self.selected_square = None
        self.legal_moves_for_selected = set()
        self._update_display()

        if color == chess.BLACK:
            self.root.after(300, self._do_ai_move)

    def _on_undo(self):
        if self.game.game_over:
            messagebox.showinfo("提示", "对局已结束，请点击「新游戏」重新开始")
            return
        if self.game.current_move_index < 0:
            messagebox.showinfo("提示", "没有可以悔的棋")
            return
        self.game.undo_move()
        self.selected_square = None
        self.legal_moves_for_selected = set()
        self._update_display()

    def _on_flip(self):
        self.flipped = not self.flipped
        self.selected_square = None
        self.legal_moves_for_selected = set()
        self._update_display()

    def _on_save_pgn(self):
        pgn = self.game.get_pgn()
        initial = os.path.join(self.pgn_dir, f"chess_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pgn")
        path = filedialog.asksaveasfilename(
            title="保存棋谱 (PGN)",
            initialdir=self.pgn_dir,
            initialfile=os.path.basename(initial),
            defaultextension=".pgn",
            filetypes=[("PGN 文件", "*.pgn"), ("所有文件", "*.*")]
        )
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(pgn)
                self.pgn_dir = os.path.dirname(path)
                messagebox.showinfo("保存成功", f"棋谱已保存到:\n{path}")
            except Exception as e:
                messagebox.showerror("保存失败", f"无法保存文件:\n{e}")

    def _on_load_pgn(self):
        path = filedialog.askopenfilename(
            title="加载棋谱 (PGN)",
            initialdir=self.pgn_dir,
            defaultextension=".pgn",
            filetypes=[("PGN 文件", "*.pgn"), ("所有文件", "*.*")]
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                pgn_text = f.read()
            if self.game.load_pgn(pgn_text):
                self.pgn_dir = os.path.dirname(path)
                self.selected_square = None
                self.legal_moves_for_selected = set()
                self._update_display()
                if self.game.game_over:
                    self._show_game_result()
                messagebox.showinfo("加载成功", "棋谱已加载，可浏览走法")
            else:
                messagebox.showerror("加载失败", "无法解析此 PGN 文件")
        except Exception as e:
            messagebox.showerror("加载失败", str(e))

    def _on_load_book(self):
        path = filedialog.askopenfilename(
            title="选择 Polyglot 开局库 (.bin)",
            initialdir=self.pgn_dir,
            defaultextension=".bin",
            filetypes=[("Polyglot Book", "*.bin"), ("所有文件", "*.*")]
        )
        if path:
            if self.game.opening_book.load(path):
                self.pgn_dir = os.path.dirname(path)
                messagebox.showinfo("加载成功", f"开局库已加载:\n{os.path.basename(path)}")
                self._update_display()
            else:
                messagebox.showerror("加载失败", "无法加载开局库文件")

    def _do_ai_move(self):
        if self.game.game_over:
            return
        if self.game.board.turn == self.game.player_color:
            return

        self.status_bar.config(text="AI 思考中...")
        self.root.update()

        move = self.game.ai_move()
        if move:
            self._update_display()

            if self.game.game_over:
                self._show_game_result()
        else:
            self.status_bar.config(text="AI 无棋可走")

    def _check_ai_turn(self):
        """开局时如果AI先走"""
        if not self.game.is_player_turn() and not self.game.game_over:
            self._do_ai_move()

    def _show_game_result(self):
        result = self.game.get_result_text()
        messagebox.showinfo("对局结束", result)

    # -----------------------------------------------------------------------
    # 绘制
    # -----------------------------------------------------------------------
    def _canvas_to_square(self, col: int, row: int) -> chess.Square:
        """将 Canvas 坐标转换为棋盘格子"""
        if self.flipped:
            return chess.square(7 - col, row)
        else:
            return chess.square(col, 7 - row)

    def _square_to_canvas(self, square: chess.Square) -> tuple[int, int]:
        """将棋盘格子转换为 Canvas 坐标 (col, row)"""
        col = chess.square_file(square)
        row = chess.square_rank(square)
        if self.flipped:
            return (7 - col, row)
        else:
            return (col, 7 - row)

    def _update_display(self):
        """更新所有界面元素"""
        self._draw_board()
        self._update_move_list()
        self._update_info()
        self._update_status()

    def _draw_board(self):
        self.canvas.delete("piece")
        self.canvas.delete("highlight")
        self.canvas.delete("legal")

        board = self.game.board
        last_move = self.game.get_last_move()

        # 高亮上一步走法 (用半透明色替代 stipple，避免 Windows 渲染问题)
        if last_move:
            for sq in (last_move.from_square, last_move.to_square):
                col, row = self._square_to_canvas(sq)
                x1 = col * self.square_size
                y1 = row * self.square_size
                self.canvas.create_rectangle(
                    x1, y1, x1 + self.square_size, y1 + self.square_size,
                    fill=COLOR_LAST_MOVE, stipple="",
                    outline="", tags="highlight"
                )

        # 高亮选中棋子
        if self.selected_square is not None:
            col, row = self._square_to_canvas(self.selected_square)
            x1 = col * self.square_size
            y1 = row * self.square_size
            self.canvas.create_rectangle(
                x1, y1, x1 + self.square_size, y1 + self.square_size,
                fill=COLOR_SELECTED, outline="#FFFF00", width=2,
                tags="highlight"
            )

        # 高亮合法走法
        for sq in self.legal_moves_for_selected:
            col, row = self._square_to_canvas(sq)
            x1 = col * self.square_size
            y1 = row * self.square_size
            xc = x1 + self.square_size // 2
            yc = y1 + self.square_size // 2

            # 是吃子还是普通走法
            if board.piece_at(sq):
                self.canvas.create_rectangle(
                    x1, y1, x1 + self.square_size, y1 + self.square_size,
                    outline=COLOR_LEGAL_CAPTURE, width=3,
                    tags="legal"
                )
            else:
                self.canvas.create_oval(
                    xc - 8, yc - 8, xc + 8, yc + 8,
                    fill=COLOR_LEGAL_MOVE, outline="",
                    tags="legal"
                )

        # 绘制棋子
        for square in chess.SQUARES:
            piece = board.piece_at(square)
            if piece is None:
                continue
            col, row = self._square_to_canvas(square)
            x1 = col * self.square_size
            y1 = row * self.square_size

            symbol = PIECE_UNICODE[piece.piece_type][piece.color]
            font_size = self.square_size - 10

            # 王被将军时红色高亮
            if piece.piece_type == chess.KING and board.is_check():
                fill_color = COLOR_CHECK
            else:
                fill_color = "#FFFFFF" if piece.color == chess.WHITE else "#000000"

            self.canvas.create_text(
                x1 + self.square_size // 2, y1 + self.square_size // 2,
                text=symbol, font=("Segoe UI Symbol", font_size),
                fill=fill_color, tags="piece"
            )

        # 确保棋子始终在最上层，避免 Canvas 渲染重叠问题
        self.canvas.tag_raise("piece")

    def _update_move_list(self):
        """更新棋谱列表"""
        self.txt_moves.config(state=tk.NORMAL)
        self.txt_moves.delete(1.0, tk.END)

        moves = self.game.move_history_san
        text_lines = []
        i = 0
        while i < len(moves):
            move_num = i // 2 + 1
            white_move = moves[i] if i < len(moves) else ""
            black_move = moves[i + 1] if i + 1 < len(moves) else ""
            line = f"{move_num:>3}. {white_move:>7}"
            if black_move:
                line += f"  {black_move:>7}"
            text_lines.append(line)
            i += 2

        self.txt_moves.insert(1.0, "\n".join(text_lines))
        self.txt_moves.see(tk.END)
        self.txt_moves.config(state=tk.DISABLED)

    def _update_info(self):
        """更新信息栏"""
        # 局面评估
        if not self.game.game_over and self.game.board.fullmove_number > 1:
            score = evaluate_board(self.game.board) / 100.0
            if self.game.player_color == chess.BLACK:
                score = -score
            eval_text = f"局面评估: {score:+.2f}"
            # 显示搜索节点数
            eval_text += f"  |  搜索节点: {self.game.ai.nodes_searched}"
            self.lbl_eval.config(text=eval_text)
        else:
            self.lbl_eval.config(text="")

        # 开局库状态
        if self.game.opening_book.book_path:
            book_name = os.path.basename(self.game.opening_book.book_path)
            in_book = self.game.opening_book.has_position(self.game.board)
            status = "✓ 开局库中" if in_book else "✗ 脱离开局库"
            self.lbl_book.config(text=f"📖 {book_name} | {status}")
        else:
            self.lbl_book.config(text="📖 未加载开局库")

    def _update_status(self):
        """更新状态栏"""
        parts = []
        move_num = self.game.board.fullmove_number
        parts.append(f"回合: {move_num}")

        if self.game.game_over:
            parts.append(self.game.get_result_text())
        elif self.game.board.is_check():
            parts.append("将军!")
            parts.append("轮到你走棋" if self.game.is_player_turn() else "AI 思考中...")
        elif self.game.is_player_turn():
            parts.append("轮到你走棋")
        else:
            parts.append("AI 思考中...")

        # 棋盘方向
        color_name = "白方" if self.game.player_color == chess.WHITE else "黑方"
        parts.append(f" | 你执 {color_name}")

        self.status_bar.config(text=" | ".join(parts))

        # 顶部信息
        if self.game.game_over:
            self.lbl_info.config(text=f"对局结束 - {self.game.get_result_text()}")
        elif self.game.board.is_check():
            self.lbl_info.config(text="将军!")
        elif self.game.is_player_turn():
            self.lbl_info.config(text="轮到你走棋")
        else:
            self.lbl_info.config(text="AI 思考中...")

    # -----------------------------------------------------------------------
    # 启动
    # -----------------------------------------------------------------------
    def run(self):
        self.root.mainloop()
