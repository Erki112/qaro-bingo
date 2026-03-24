const tg = window.Telegram.WebApp;
tg.expand();

let currentGame = null;
let myGrid = [];
let userId = tg.initDataUnsafe?.user?.id || Date.now();
let gameInterval;

tg.MainButton.setText('🎮 Play Bingo').show().onClick(() => {
    document.getElementById('gameCodeSection').style.display = 'block';
    tg.MainButton.hide();
});

document.getElementById('createBtn').onclick = createGame;
document.getElementById('joinBtn').onclick = joinGame;
document.getElementById('newRoundBtn').onclick = newRound;
document.getElementById('callBtn').onclick = callNumber;

async function createGame() {
    try {
        const res = await fetch('/api/game/create', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({user_id: userId})
        });
        const data = await res.json();
        if (data.game_id) {
            currentGame = data;
            showGame(data.game_id, data.grid);
            document.getElementById('gameStatus').textContent = `Game ID: ${data.game_id}`;
            tg.MainButton.setText('Game Created!').show();
        }
    } catch(e) { alert('Error creating game'); }
}

async function joinGame() {
    const gameId = document.getElementById('gameCode').value.trim();
    if (!gameId) return alert('Enter Game ID');
    
    try {
        const res = await fetch(`/api/game/${gameId}/join`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                user_id: userId,
                username: tg.initDataUnsafe?.user?.first_name || 'Player'
            })
        });
        const data = await res.json();
        if (data.success) {
            currentGame = {game_id: gameId};
            showGame(gameId, data.grid);
            startGamePolling(gameId);
        }
    } catch(e) { alert('Game not found'); }
}

function showGame(gameId, grid) {
    currentGame.game_id = gameId;
    myGrid = grid;
    document.getElementById('gameCodeSection').style.display = 'none';
    document.getElementById('bingoGrid').style.display = 'block';
    document.getElementById('controls').style.display = 'flex';
    document.getElementById('calledNumbers').style.display = 'block';
    
    const cells = document.getElementById('gridCells');
    cells.innerHTML = '';
    grid.forEach(row => {
        row.forEach(num => {
            const cell = document.createElement('div');
            cell.className = 'cell';
            cell.dataset.number = num;
            cell.textContent = num === 0 ? 'FREE' : num;
            if (num === 0) cell.classList.add('free');
            cells.appendChild(cell);
        });
    });
}

async function newRound() {
    if (!currentGame?.game_id) return;
    await fetch(`/api/game/${currentGame.game_id}/newround`, {method: 'POST'});
    location.reload();
}

async function callNumber() {
    const num = parseInt(document.getElementById('callNumber').value);
    if (!currentGame?.game_id || num < 1 || num > 75) return;
    
    const res = await fetch(`/api/game/${currentGame.game_id}/call/${num}`, {method: 'POST'});
    const data = await res.json();
    if (data.bingo) alert(`🎉 BINGO! Winner: ${data.winner}`);
}

function startGamePolling(gameId) {
    clearInterval(gameInterval);
    gameInterval = setInterval(async () => {
        try {
            const res = await fetch(`/api/game/${gameId}`);
            const data = await res.json();
            if (data.called_numbers) {
                data.called_numbers.forEach(n => markNumber(n));
            }
            document.getElementById('playerCount').textContent = `${data.players} players`;
        } catch(e) {}
    }, 2000);
}

function markNumber(num) {
    document.querySelectorAll('.cell').forEach(cell => {
        if (parseInt(cell.dataset.number) === num) {
            cell.classList.add('called');
        }
    });
                }
