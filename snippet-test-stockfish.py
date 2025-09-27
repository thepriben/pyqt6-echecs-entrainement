import chess
import chess.engine

engine = chess.engine.SimpleEngine.popen_uci("stockfish")

board = chess.Board() 

info = engine.analyse(board, chess.engine.Limit(depth=15))
best_move = engine.play(board, chess.engine.Limit(time=0.5)).move

print("Evaluate:", info.get("score"))
print("best_move:", best_move)

engine.quit()
