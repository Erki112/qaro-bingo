# main.py
from flask import Flask, render_template, request, jsonify
import random
import json

app = Flask(__name__)

# Sample bingo card data (5x5 grid)
def generate_bingo_card():
    cards = []
    for i in range(5):
        row = []
        for j in range(5):
            # Generate random numbers for each position
            # We'll use different ranges for each column
            if j == 0:  # B column (1-15)
                row.append(random.randint(1, 15))
            elif j == 1:  # I column (16-30)
                row.append(random.randint(16, 30))
            elif j == 2:  # N column (31-45)
                row.append(random.randint(31, 45))
            elif j == 3:  # G column (46-60)
                row.append(random.randint(46, 60))
            else:  # O column (61-75)
                row.append(random.randint(61, 75))
        cards.append(row)
    # Make center square free (0)
    cards[2][2] = 0
    return cards

# Store game state
games = {}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/start_game', methods=['POST'])
def start_game():
    player_id = request.json.get('player_id', 'default')
    card = generate_bingo_card()
    games[player_id] = {
        'card': card,
        'called_numbers': [],
        'game_over': False
    }
    return jsonify({
        'card': card,
        'player_id': player_id
    })

@app.route('/call_number', methods=['POST'])
def call_number():
    player_id = request.json.get('player_id', 'default')
    if player_id not in games:
        return jsonify({'error': 'Game not found'}), 404
    
    # Generate a new number
    game = games[player_id]
    new_number = random.randint(1, 75)
    
    # Make sure we don't repeat numbers
    while new_number in game['called_numbers']:
        new_number = random.randint(1, 75)
    
    game['called_numbers'].append(new_number)
    
    # Check for bingo
    is_winner = check_bingo(game['card'], game['called_numbers'])
    game['game_over'] = is_winner
    
    return jsonify({
        'number': new_number,
        'called_numbers': game['called_numbers'],
        'winner': is_winner
    })

@app.route('/check_bingo', methods=['POST'])
def check_bingo_route():
    player_id = request.json.get('player_id', 'default')
    if player_id not in games:
        return jsonify({'error': 'Game not found'}), 404
    
    card = games[player_id]['card']
    called_numbers = games[player_id]['called_numbers']
    
    is_winner = check_bingo(card, called_numbers)
    return jsonify({'winner': is_winner})

def check_bingo(card, called_numbers):
    # Flatten called numbers for easier lookup
    called_set = set(called_numbers)
    
    # Check rows
    for row in card:
        if all(cell == 0 or cell in called_set for cell in row):
            return True
    
    # Check columns
    for col in range(5):
        if all(card[row][col] == 0 or card[row][col] in called_set for row in range(5)):
            return True
    
    # Check diagonals
    if all(card[i][i] == 0 or card[i][i] in called_set for i in range(5)):
        return True
    if all(card[i][4-i] == 0 or card[i][4-i] in called_set for i in range(5)):
        return True
    
    return False

if __name__ == '__main__':
    app.run(debug=True)
