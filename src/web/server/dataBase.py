from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from flask import abort, request, redirect, send_from_directory, send_file
from flask import jsonify, json, url_for
import os
import requests
from flask_cors import CORS
from flask_migrate import Migrate

# Create config for app
basedir = os.path.abspath(os.path.dirname(__file__))
static_folder_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'client', 'dist')
print(f"Static folder path: {static_folder_path}")

app = Flask(__name__, static_folder=static_folder_path)

ENV = os.getenv('FLASK_ENV', 'development')

if ENV == 'production':
    # On Heroku, 'DATABASE_URL' is automatically set
    database_url = os.getenv('DATABASE_URL')
    if database_url is None:
        raise ValueError("DATABASE_URL is not set in the environment variables.")
    # Replace 'postgres://' with 'postgresql://' for SQLAlchemy compatibility
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
else:
    # Use SQLite for local development
    database_url = 'sqlite:///db.sqlite'

# Get DATABASE_URL from environment variable or use a default local SQLite for dev
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['CORS_HEADERS'] = 'Content-Type'

db = SQLAlchemy(app)
CORS(app)

# Initialize Flask-Migrate
migrate = Migrate(app, db)

# Initialize the database every time the app starts
with app.app_context():
    try:
        app.logger.info("Initializing the database...")
        print("Initializing the database...")
        db.create_all()  # Ensure the tables are created
        app.logger.info(f"Database file should be located at: {app.config['SQLALCHEMY_DATABASE_URI']}")
        print(f"Database initialized at {app.config['SQLALCHEMY_DATABASE_URI']}")
    except Exception as e:
        app.logger.error(f"Error initializing database: {e}")
        print(f"Error initializing database: {e}")

import sys
class ChessGame(db.Model):
    id = db.Column(db.Integer, primary_key=True)  
    fen = db.Column(db.String, nullable=False)       
    moves = db.Column(db.String, nullable=True)  
    game_status = db.Column(db.String(20), nullable=False, default='ongoing')  
    opening_phase = db.Column(db.Boolean, nullable=False, default=True)  
    player_color = db.Column(db.String(5), nullable=False)  
#from dataBase import app

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Now you can import modules from chessGame
from chessGame import Engine
from chessGame import Board
from chessGame import ChessNet
import torch

MODEL_URL = os.getenv('MODEL_URL')
MODEL_DIR = 'models'
MODEL_PATH = os.path.join(MODEL_DIR, 'model.pth')

def download_model():
    if not os.path.exists(MODEL_PATH):
        os.makedirs(MODEL_DIR, exist_ok=True)
        print('Downloading model from', MODEL_URL)
        response = requests.get(MODEL_URL, stream=True)
        if response.status_code == 200:
            with open(MODEL_PATH, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            print('Model downloaded successfully.')
        else:
            print(f'Failed to download model. Status code: {response.status_code}')
            raise Exception('Failed to download model.')
    else:
        print('Model already exists locally.')

def load_model():
    download_model()
    model = ChessNet()
    model.load_state_dict(torch.load(MODEL_PATH, map_location=torch.device('cpu')))
    model.eval()
    return model

# Load the model at startup
model = load_model()

@app.route('/')
def index():
    app.logger.info('Serving index.html')
    return send_file(os.path.join(app.static_folder, 'index.html'))

@app.route('/<path:filename>')
def serve_static(filename):
    print(f"Serving static file: {filename}")
    return send_from_directory(app.static_folder, filename)

@app.route('/new_game/<player>', methods=['POST'])
def new_game(player):
    app.logger.info(f"new_game route hit with player_color: {player}")
    print(player)
    # Create a new game
    player_color = "white" if player=="1" else "black"
    game = ChessGame(fen=Board().generate_fen(), player_color=player_color)
    db.session.add(game)
    db.session.commit()

    return jsonify({"status": "success", "game_id": game.id, "fen": game.fen})

@app.route('/engine_move/<game_id>', methods=['PUT'])
def make_move(game_id):
    # Load the game from the database
    game = ChessGame.query.get_or_404(game_id)
    print(game)
    if not game:
        return jsonify({"status": "error", "message": "Game not found"}), 404
    if game.game_status != 'ongoing':
        return jsonify({"status": "error", "message": "Game is already over"}), 400

    board = Board(game.fen)
    print(game.fen)
    engine = Engine(color="white" if game.player_color=="black" else "black", opening_phase=game.opening_phase, played_moves=[] if not game.moves else game.moves.split(" ")[:-1])
    print(engine.played_moves)
    print(engine.opening_phase)
    print(engine.color)
    
    # Apply the move to the engine
    engine_move = engine.engine_move(board, model)
    print(engine_move)
    if not engine_move:
        return jsonify({"status": "error", "message": "No valid moves found"}), 400
    engine_m, move = engine_move
    move = move.uci()
    engine_start_pos, engine_end_pos = engine_m
    print(engine_start_pos, engine_end_pos)
    next_move = engine.update((engine_start_pos, engine_end_pos), board, True)
    if board.move_piece(engine_start_pos, engine_end_pos, None):
        game.fen = board.generate_fen()
        next_move = engine.played_moves[-1] if engine.opening_phase else next_move
        game.moves = (game.moves or '') + next_move + " "  # Update move history
        game.opening_phase = engine.opening_phase
        db.session.commit()

        return jsonify({"status": "success", "fen": game.fen, "next_move": move})
    else:
        return jsonify({"status": "error", "message": "Invalid move"}), 400
    
@app.route('/move/<game_id>', methods=['POST'])
def move(game_id):
    # Load the game from the database
    game = ChessGame.query.get_or_404(game_id)
    print(game)
    if not game:
        return jsonify({"status": "error", "message": "Game not found"}), 404
    if game.game_status != 'ongoing':
        return jsonify({"status": "error", "message": "Game is already over"}), 400

    board = Board(game.fen)
    move = request.json.get('move')
    move_data = move.get('move', {})
    from_square = move_data.get('from')  # E.g., 'e2'
    to_square = move_data.get('to')
    print(from_square, to_square)
    start_pos, end_pos = board.algebraic_to_index(from_square), board.algebraic_to_index(to_square)
    start_pos = (7-start_pos[0], start_pos[1])
    end_pos = (7-end_pos[0], end_pos[1])
    tmp_engine = Engine()
    print(start_pos, end_pos)
    update = tmp_engine.update((start_pos, end_pos), board, actual=True)
    if board.move_piece(start_pos, end_pos, None):
        game.fen = board.generate_fen()
        game.moves = (game.moves or '') + update + " " # Update move history
        del tmp_engine
        db.session.commit()

        return jsonify({"status": "success", "fen": game.fen})
    else:
        return jsonify({"status": "error", "message": "Invalid move"}), 400

@app.route('/game_status/<game_id>', methods=['GET'])
def game_status(game_id):
    # Load the game from the database
    game = ChessGame.query.get_or_404(game_id)
    if not game:
        return jsonify({"status": "error", "message": "Game not found"}), 404

    return jsonify({"status": "success", "game_status": game.game_status})

@app.route('/game/<game_id>', methods=['GET'])
def get_game(game_id):
    # Load the game from the database
    game = ChessGame.query.get_or_404(game_id)
    if not game:
        return jsonify({"status": "error", "message": "Game not found"}), 404

    return jsonify({"status": "success", "fen": game.fen, "moves": game.moves, "game_status": game.game_status})

#@app.route('/possible_moves/<game_id>', methods=['GET'])
#def possible_moves(game_id):
#    # Load the game from the database
#    game = ChessGame.query.get_or_404(game_id)
#    if not game:
#        return jsonify({"status": "error", "message": "Game not found"}), 404
#
#    board = Board(game.fen)
#    square = request.json.get('square')
#    row, col = square.get('row'), square.get('col')
#    piece = board.piece_at(row, col)
#    if not piece:
#        return jsonify({"status": "error", "message": "No piece at the specified square"}), 400
#    
#    moves = piece.get_moves(board, row, col)
#    return jsonify({"status": "success", "moves": moves})

@app.errorhandler(404)
def not_found_error(error):
    app.logger.error(f'404 error: {error}')
    return 'File not found', 404