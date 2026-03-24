// static/script.js
document.addEventListener('DOMContentLoaded', function() {
    const startScreen = document.getElementById('start-screen');
    const gameContainer = document.getElementById('game-container');
    const startBtn = document.getElementById('start-btn');
    const callBtn = document.getElementById('call-btn');
    const newGameBtn = document.getElementById('new-game-btn');
    const playerIdInput = document.getElementById('player-id');
    const cardElement = document.getElementById('card');
    const calledNumbersElement = document.getElementById('called-numbers');
    const statusElement = document.getElementById('status');
    
    let playerId = '';
    let currentCard = [];
    let calledNumbers = [];
    
    startBtn.addEventListener('click', startGame);
    callBtn.addEventListener('click', callNumber);
    newGameBtn.addEventListener('click', newGame);
    
    function startGame() {
        playerId = playerIdInput.value.trim() || 'player1';
        fetch('/start_game', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({player_id: playerId})
        })
        .then(response => response.json())
        .then(data => {
            currentCard = data.card;
            calledNumbers = [];
            updateCardDisplay();
            startScreen.classList.add('hidden');
            gameContainer.classList.remove('hidden');
            updateGameInfo();
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Error starting game');
        });
    }
    
    function callNumber() {
        fetch('/call_number', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({player_id: playerId})
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                alert(data.error);
                return;
            }
            
            calledNumbers.push(data.number);
            updateGameInfo();
            updateCardDisplay();
            
            if (data.winner) {
                statusElement.textContent = 'BINGO! You win!';
                callBtn.disabled = true;
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Error calling number');
        });
    }
    
    function newGame() {
        startGame();
    }
    
    function updateCardDisplay() {
        cardElement.innerHTML = '';
        currentCard.forEach((row, rowIndex) => {
            row.forEach((cell, colIndex) => {
                const cellElement = document.createElement('div');
                cellElement.className = 'card-cell';
                cellElement.textContent = cell;
                
                if (cell === 0) {
                    cellElement.classList.add('free');
                    cellElement.textContent = 'FREE';
                } else if (calledNumbers.includes(cell)) {
                    cellElement.classList.add('highlighted');
                }
                
                cardElement.appendChild(cellElement);
            });
        });
    }
    
    function updateGameInfo() {
        calledNumbersElement.textContent = calledNumbers.join(', ') || 'None';
        if (calledNumbers.length > 0) {
            statusElement.textContent = '';
        }
    }
});
