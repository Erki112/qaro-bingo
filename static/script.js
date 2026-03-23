// Telegram WebApp
const tg = window.Telegram.WebApp;
tg.expand();
tg.enableClosingConfirmation();

// Socket.IO
const socket = io();

// Game state
let currentGame = null;
let myGrid = [];
let userId = tg.initDataUnsafe.user ? tg.initDataUnsafe.user.id : Date.now();

// Init
document.addEventListener('DOMContentLoaded', initApp);

function initApp() {
    tg.MainButton.setText('🎮 Play Bingo').show().onClick(startGame);
    
    document.getElementById('createBtn').onclick = createGame;
    document.getElementById('joinBtn').onclick = joinGame;
    
    socket.on('number_called', updateCalledNumbers);
    socket.on('game_won', onGameWon);
    socket.on('player_joined', updatePlayerCount);
    socket.on('game_state', updateGameState);
}

async function createGame() {
    try {
        const response = await fetch('/api/game/create', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({user_id: userId})
        });
        
        const data = await response.json();
        if (data.game_id) {
            currentGame = data;
            showGame(data.game_id, data.grid);
            document.getElementById('gameCodeSection').style.display = 'none';
            document.getElementById('controls').style.display = 'flex';
            tg.MainButton.setText('Game Created!').hide();
            updateStatus('Game Created - Share ID: ' + data.game_id);
        }
    } catch (error) {
        alert('Error creating game');
    }
}

async function joinGame() {
    const gameId = document.getElementById('gameCode').value.trim();
    if (!gameId) {
        alert('Enter Game ID');
        return;
    }
    
    try {
        const response = await fetch(`/api/game/${gameId}/join`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                user_id: userId,
                username: tg.initDataUnsafe.user ? tg.initDataUnsafe.user.username || tg.initDataUnsafe.user.first_name : 'Player'
            })
        });
        
        const data = await response.json();
        if (data.success) {
            currentGame = {game_id: gameId};
            myGrid = data.grid;
            showGame(gameId, data.grid);
            document.getElementById('gameCodeSection').style.display = 'none';
            document.getElementById('controls').style.display = 'flex';
            socket.emit('join_game', {game_id: gameId});
        }
    } catch (error) {
        alert('Game not found or already joined');
    }
}

function showGame(gameId, grid) {
    currentGame = {...currentGame, game_id: gameId};
    myGrid = grid;
    
    // Render grid
    const cells = document.getElementById('gridCells');
    cells.innerHTML = '';
    grid.forEach((row, i) => {
        row.forEach((num, j) => {
            const cell = document.createElement('div');
            cell.className = 'cell';
            cell.dataset.number = num;
            cell.textContent = num === 0 ? 'FREE' : num;
            if (num === 0) cell.classList.add('free');
            cell.onclick = () => toggleCell(cell);
            cells.appendChild(cell);
        });
    });
    
    socket.emit('join_game', {game_id: gameId});
}

function toggleCell(cell) {
    const num = parseInt(cell.dataset.number);
    if (currentGame && currentGame.called_numbers?.includes(num)) {
        cell.classList.add('called');
    }
}

function updateCalledNumbers(data) {
    if (!currentGame) return;
    
    // Mark cells
    document.querySelectorAll('.cell').forEach(cell => {
        const num = parseInt(cell.dataset.number);
        if (data.number === num) {
            cell.classList.add('called');
        }
    });
    
    // Update called list
    updateCalledList(data.number);
}

function startNewRound() {
    if (!currentGame?.game_id) return;
    
    currentGame.status = 'active';
    currentGame.called_numbers = [];
    
    // Reset grid visuals
    document.querySelectorAll('.cell.called').forEach(cell => {
        if (parseInt(cell.dataset.number) !== 0) {
            cell.classList.remove('called');
        }
    });
    
    document.getElementById('calledNumbers').innerHTML = '<h3>Called Numbers</h3><div id="numbersList"></div>';
    updateStatus('New Round Started!');
}

document.getElementById('newRoundBtn')?.addEventListener('click', startNewRound);
document.getElementById('callBtn')?.addEventListener('click', callNumber);

async function callNumber() {
    const number = parseInt(document.getElementById('callNumber').value);
    if (!currentGame?.game_id || number < 1 || number > 75) return;
    
    try {
        const response = await fetch(`/api/game/${currentGame.game_id}/call/${number}`, {
            method: 'POST'
        });
        const data = await response.json();
        
        if (data.bingo) {
            alert(`🎉 BINGO! Winner: ${data.winner}`);
        }
    } catch (error) {
        console.error('Call error:', error);
    }
}

function updateStatus(text) {
    document.getElementById('gameStatus').textContent = text;
}

function updatePlayerCount(data) {
    document.getElementById('playerCount').textContent = `${data.total_players} players`;
}

function onGameWon(data) {
    alert(`🎉 BINGO! Winner: ${data.winner}`);
    updateStatus('Game Over - BINGO!');
}

function updateGameState(data) {
    updateStatus(`${data.status.toUpperCase()} (${data.players} players)`);
    if (data.called_numbers) {
        data.called_numbers.forEach(num => updateCalledList(num));
    }
}

function updateCalledList(number) {
    const list = document.getElementById('numbersList');
    const ball = document.createElement('span');
    ball.className = 'called-ball';
    ball.textContent = number;
    list.insertBefore(ball, list.firstChild);
}

function startGame() {
    document.getElementById('gameCodeSection').style.display = 'block';
    tg.MainButton.hide();
                }
