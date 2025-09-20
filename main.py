#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import sys
import json
import shutil
from dataclasses import dataclass
from typing import Optional, List

from PyQt6.QtCore import Qt, QRectF, QSize, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QAction
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFileDialog, QMessageBox,
    QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QLineEdit,
    QSplitter
)

import chess
import chess.pgn
import chess.engine

# ------------------------ Config & Engine ------------------------

SETTINGS_FILE = os.path.join(os.path.expanduser("~"), ".pyqt_chess_trainer.json")

DEFAULT_ENGINE_CANDIDATES = [
    "stockfish",
    "/usr/bin/stockfish",
    "/usr/local/bin/stockfish",
    os.path.expanduser("~/.local/bin/stockfish"),
    "C:/Program Files/Stockfish/stockfish.exe",
    "C:/stockfish/stockfish.exe",
]

UNICODE_PIECES = {
    chess.Piece.from_symbol('K'): '♔',
    chess.Piece.from_symbol('Q'): '♕',
    chess.Piece.from_symbol('R'): '♖',
    chess.Piece.from_symbol('B'): '♗',
    chess.Piece.from_symbol('N'): '♘',
    chess.Piece.from_symbol('P'): '♙',
    chess.Piece.from_symbol('k'): '♚',
    chess.Piece.from_symbol('q'): '♛',
    chess.Piece.from_symbol('r'): '♜',
    chess.Piece.from_symbol('b'): '♝',
    chess.Piece.from_symbol('n'): '♞',
    chess.Piece.from_symbol('p'): '♟',
}

@dataclass
class EngineConfig:
    path: Optional[str] = None
    limit_time_ms: int = 1000  # per query

    @staticmethod
    def auto_detect() -> Optional[str]:
        for p in DEFAULT_ENGINE_CANDIDATES:
            found = shutil.which(p) or (p if os.path.exists(p) else None)
            if found:
                return found
        return None

class EngineWrapper:
    def __init__(self, config: EngineConfig):
        self.config = config
        self._engine: Optional[chess.engine.SimpleEngine] = None

    def start(self) -> None:
        if self._engine is not None:
            return
        path = self.config.path or EngineConfig.auto_detect()
        if not path:
            raise FileNotFoundError("Stockfish not found. Set the path in Settings ▸ Engine Path…")
        self._engine = chess.engine.SimpleEngine.popen_uci(path)

    def stop(self) -> None:
        if self._engine is not None:
            try:
                self._engine.quit()
            finally:
                self._engine = None

    def best_move(self, board: chess.Board) -> Optional[chess.Move]:
        if self._engine is None:
            self.start()
        if self._engine is None:
            return None
        limit = chess.engine.Limit(time=max(0.05, self.config.limit_time_ms / 1000.0))
        try:
            info = self._engine.play(board, limit)
            return info.move
        except chess.engine.EngineTerminatedError:
            self._engine = None
            return None
        except Exception:
            return None

# -------------------------- Board Widget --------------------------

class BoardWidget(QWidget):
    # Émis à chaque coup joué manuellement
    movePlayed = pyqtSignal(chess.Move)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.board = chess.Board()
        self.selected_square: Optional[int] = None
        self.square_highlight: Optional[int] = None
        self.flip = False
        self.last_user_move: Optional[chess.Move] = None
        self.last_engine_move: Optional[chess.Move] = None
        self.feedback_label: Optional[QLabel] = None
        self.setMinimumSize(QSize(520, 520))
        self._font = QFont("Segoe UI Symbol", 40)

    def set_feedback_label(self, label: QLabel):
        self.feedback_label = label

    def sizeHint(self) -> QSize:
        s = min(720, max(self.width(), self.height()))
        return QSize(s, s)

    def _square_at(self, pos) -> Optional[int]:
        w = self.width()
        h = self.height()
        size = min(w, h)
        margin_x = (w - size) / 2
        margin_y = (h - size) / 2
        sq = size / 8
        x = pos.x() - margin_x
        y = pos.y() - margin_y
        if x < 0 or y < 0 or x >= size or y >= size:
            return None
        file_ = int(x // sq)
        rank_ = 7 - int(y // sq)
        if self.flip:
            file_ = 7 - file_
            rank_ = 7 - rank_
        return chess.square(file_, rank_)

    def paintEvent(self, event):
        painter = QPainter(self)
        w = self.width()
        h = self.height()
        size = min(w, h)
        margin_x = (w - size) / 2
        margin_y = (h - size) / 2
        sq = size / 8

        light = QColor(240, 217, 181)
        dark = QColor(181, 136, 99)
        sel = QColor(246, 246, 105)
        hint = QColor(120, 200, 120)

        # board squares
        for r in range(8):
            for f in range(8):
                x = margin_x + f * sq
                y = margin_y + (7 - r) * sq
                if self.flip:
                    x = margin_x + (7 - f) * sq
                    y = margin_y + r * sq
                rect = QRectF(x, y, sq, sq)
                color = light if (r + f) % 2 == 0 else dark
                sq_idx = chess.square(f if not self.flip else 7 - f, r if not self.flip else 7 - r)
                if self.selected_square == sq_idx:
                    color = sel
                elif self.square_highlight == sq_idx:
                    color = hint
                painter.fillRect(rect, color)

        # coords
        pen = QPen(QColor(70, 70, 70))
        painter.setPen(pen)
        font = QFont("Inter", 9)
        painter.setFont(font)
        for f in range(8):
            file_char = "abcdefgh"[f if not self.flip else 7 - f]
            x = margin_x + f * sq + 2
            y = margin_y + size - 2
            painter.drawText(QRectF(x, y - 14, sq, 14),
                             Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom, file_char)
        for r in range(8):
            rank_char = str(r + 1 if not self.flip else 8 - r)
            x = margin_x + 2
            y = margin_y + (7 - r) * sq + 12
            painter.drawText(QRectF(x, y, 14, 14), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, rank_char)

        # pieces
        painter.setFont(self._font)
        for square, piece in self.board.piece_map().items():
            f = chess.square_file(square)
            r = chess.square_rank(square)
            x = margin_x + (7 - f) * sq if self.flip else margin_x + f * sq
            y = margin_y + r * sq if self.flip else margin_y + (7 - r) * sq
            rect = QRectF(x, y, sq, sq)
            glyph = UNICODE_PIECES.get(piece)
            if glyph:
                painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, glyph)

        # last moves highlight (both from & to)
        if self.last_user_move:
            self._highlight_move(painter, self.last_user_move, QColor(66, 135, 245))
        if self.last_engine_move:
            self._highlight_move(painter, self.last_engine_move, QColor(220, 20, 60))

    def _square_to_rect(self, square: int) -> QRectF:
        w = self.width()
        h = self.height()
        size = min(w, h)
        margin_x = (w - size) / 2
        margin_y = (h - size) / 2
        sq = size / 8
        f = chess.square_file(square)
        r = chess.square_rank(square)
        x = margin_x + (7 - f) * sq if self.flip else margin_x + f * sq
        y = margin_y + r * sq if self.flip else margin_y + (7 - r) * sq
        return QRectF(x, y, sq, sq)

    def _highlight_move(self, painter: QPainter, move: chess.Move, color: QColor):
        """Draw both origin (dashed) and destination (solid) rectangles."""
        painter.save()
        # Destination: solid
        painter.setPen(QPen(color, 3, Qt.PenStyle.SolidLine))
        rect_to = self._square_to_rect(move.to_square)
        painter.drawRect(rect_to)
        # Origin: dashed
        painter.setPen(QPen(color, 2, Qt.PenStyle.DashLine))
        rect_from = self._square_to_rect(move.from_square)
        painter.drawRect(rect_from)
        painter.restore()

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        sq = self._square_at(event.position())
        if sq is None:
            return
        if self.selected_square is None:
            piece = self.board.piece_at(sq)
            if piece and piece.color == self.board.turn:
                self.selected_square = sq
                self.update()
        else:
            move = chess.Move(self.selected_square, sq)
            # auto-queen on promotion
            if move in self.board.generate_legal_moves():
                src_piece = self.board.piece_at(self.selected_square)
                if src_piece and src_piece.piece_type == chess.PAWN and (
                    chess.square_rank(sq) in (0, 7)
                ) and move.promotion is None:
                    move = chess.Move(self.selected_square, sq, promotion=chess.QUEEN)
            if move in self.board.legal_moves:
                self._apply_user_move(move)
            else:
                piece = self.board.piece_at(sq)
                if piece and piece.color == self.board.turn:
                    self.selected_square = sq
                else:
                    self.selected_square = None
            self.update()

    def _apply_user_move(self, move: chess.Move):
        self.board.push(move)
        self.last_user_move = move
        self.selected_square = None
        self.square_highlight = move.to_square
        self.movePlayed.emit(move)  # Notifie la fenêtre principale

    def set_board(self, board: chess.Board):
        self.board = board.copy(stack=True)
        self.selected_square = None
        self.square_highlight = None
        self.last_user_move = None
        self.last_engine_move = None
        self.update()

# --------------------------- Main Window ---------------------------

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyQt6 Chess Trainer")
        self.resize(960, 620)

        # Settings & engine
        self.engine_cfg = EngineConfig()
        self._load_settings()
        if not self.engine_cfg.path:
            self.engine_cfg.path = EngineConfig.auto_detect()
        self.engine = EngineWrapper(self.engine_cfg)

        # Board + status
        self.board_widget = BoardWidget()
        self.status = QLabel("Ready.")
        self.board_widget.set_feedback_label(self.status)
        self.board_widget.movePlayed.connect(self.on_user_move)

        # Controls (minimal)
        self.btn_new = QPushButton("New game")
        self.btn_undo = QPushButton("Undo")
        self.btn_flip = QPushButton("Rotate board")
        self.depth_label = QLabel("Engine time (ms):")
        self.time_edit = QLineEdit(str(self.engine_cfg.limit_time_ms))
        self.time_edit.setFixedWidth(80)

        # Layout
        controls = QVBoxLayout()
        controls.addWidget(self.btn_new)
        controls.addWidget(self.btn_undo)
        controls.addWidget(self.btn_flip)
        row = QHBoxLayout()
        row.addWidget(self.depth_label)
        row.addWidget(self.time_edit)
        row.addStretch(1)
        controls.addLayout(row)
        controls.addStretch(1)
        controls.addWidget(self.status)

        right_panel = QWidget()
        right_panel.setLayout(controls)

        splitter = QSplitter()
        splitter.addWidget(self.board_widget)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

        container = QWidget()
        lay = QVBoxLayout(container)
        lay.addWidget(splitter)
        self.setCentralWidget(container)

        # Menu (épuré)
        self._build_menu()

        # Signals
        self.btn_new.clicked.connect(self.on_new_game)
        self.btn_undo.clicked.connect(self.on_undo)
        self.btn_flip.clicked.connect(self.on_flip)
        self.time_edit.editingFinished.connect(self.on_time_changed)

    # ---------------------- Settings ----------------------
    def _load_settings(self):
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.engine_cfg.path = data.get('engine_path')
                self.engine_cfg.limit_time_ms = int(data.get('engine_time_ms', 1000))
            except Exception:
                pass

    def _save_settings(self):
        data = {
            'engine_path': self.engine_cfg.path,
            'engine_time_ms': self.engine_cfg.limit_time_ms,
        }
        try:
            with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # ------------------------ Menu ------------------------
    def _build_menu(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("File")

        open_pgn = QAction("Open PGN…", self)
        open_pgn.triggered.connect(self.on_open_pgn)
        file_menu.addAction(open_pgn)

        file_menu.addSeparator()
        quit_act = QAction("Quit", self)
        quit_act.triggered.connect(self.close)
        file_menu.addAction(quit_act)

        settings_menu = menubar.addMenu("Settings")
        set_engine = QAction("Engine Path…", self)
        set_engine.triggered.connect(self.on_set_engine_path)
        settings_menu.addAction(set_engine)

    # ----------------------- Slots ------------------------
    def on_new_game(self):
        self.board_widget.set_board(chess.Board())
        self.status.setText("New initial position.")
        self.board_widget.square_highlight = None
        self.board_widget.last_engine_move = None
        self.board_widget.update()

    def on_undo(self):
        if self.board_widget.board.move_stack:
            self.board_widget.board.pop()
            self.board_widget.update()
            self.status.setText("Move undone.")

    def on_flip(self):
        self.board_widget.flip = not self.board_widget.flip
        self.board_widget.update()

    def on_time_changed(self):
        try:
            val = int(self.time_edit.text())
            self.engine_cfg.limit_time_ms = max(50, min(val, 10000))
            self._save_settings()
            self.status.setText(f"Engine time set to {self.engine_cfg.limit_time_ms} ms.")
        except ValueError:
            self.time_edit.setText(str(self.engine_cfg.limit_time_ms))

    def on_open_pgn(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open a PGN file", "", "PGN Files (*.pgn);;All (*.*)")
        if not path:
            return
        try:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                game = chess.pgn.read_game(f)
            if not game:
                QMessageBox.warning(self, "PGN", "Could not read a game from this PGN.")
                return
            board = game.board()
            for mv in game.mainline_moves():
                board.push(mv)
            self.board_widget.set_board(board)
            self.status.setText("PGN loaded. Final position shown.")
        except Exception as e:
            QMessageBox.critical(self, "PGN", f"Read error: {e}")

    def on_set_engine_path(self):
        from PyQt6.QtWidgets import QInputDialog
        current = self.engine_cfg.path or ""
        text, ok = QInputDialog.getText(self, "Stockfish Path", "Executable path:", text=current)
        if ok:
            p = text.strip()
            if not p:
                self.engine_cfg.path = None
            else:
                if shutil.which(p) or os.path.exists(p):
                    self.engine_cfg.path = p
                else:
                    QMessageBox.warning(self, "Engine", "Invalid path — please check the executable.")
                    return
            self.engine.stop()
            self._save_settings()
            self.status.setText("Engine path updated.")

    # --- Core feature: après TON coup, suggérer le meilleur coup du camp au trait ---
    def on_user_move(self, move: chess.Move):
        side_to_move = "White" if self.board_widget.board.turn == chess.WHITE else "Black"
        suggestion = self.engine.best_move(self.board_widget.board)
        if suggestion:
            try:
                san = self.board_widget.board.san(suggestion)
            except Exception:
                san = suggestion.uci()
            self.board_widget.last_engine_move = suggestion
            self.board_widget.square_highlight = suggestion.to_square
            self.board_widget.update()
            self.status.setText(f"Engine suggests for {side_to_move}: {san}")
        else:
            self.status.setText("Engine unavailable.")

    # Clean shutdown
    def closeEvent(self, event):
        try:
            self.engine.stop()
        finally:
            super().closeEvent(event)

# ------------------------------ Main -------------------------------------

def main():
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
