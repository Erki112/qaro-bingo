class BingoWebApp {
    constructor() {
        this.userId = window.Telegram.WebApp.initDataUnsafe.user?.id || 'guest';
        this.init();
    }

    async init() {
        window.Telegram.WebApp.ready();
        window.Telegram.WebApp.expand();
        
        this.userId = window.Telegram.WebApp.initDataUnsafe.user?.id?.toString() || 'guest';
        this.statusEl = document.getElementById('status');
        this.gridEl = document.getElementById('bingoGrid');
        this.winsEl = document.getElementById('winsList');
        this.calledListEl = document.getElementById('calledList');
        this.currentNumberEl = document.getElementById('currentNumber');
        this.currentLetterEl = document.getElementById('currentLetter');
        
        await this.loadGame();
        this.renderGrid();
        this.bindEvents();
        
        // Poll for updates every 2 seconds
        setInterval(() => this.loadGame(), 2000);
    }

    async loadGame() {
        try {
            const response = await fetch(`/api/game/${this.userId}`);
            if (response.ok) {
                const data = await response.json();
                this.gameData = data;
                this.renderGrid();
                this.updateStatus();
                this.updateWins();
                this.updateCalledNumbers();
            } else {
                this.statusEl.textContent = '👆 Use /new command to create game';
                this.statusEl.style.color = '#ff6b6b';
            }
        } catch (e) {
            console.error('Load game error:', e);
            this.statusEl.textContent = 'Connection error';
        }
    }

    renderGrid() {
        if (!this.gameData?.grid) return;
        
        this.gridEl.innerHTML = '';
        this.gameData.grid.forEach((row, i) => {
            row.forEach((num, j) => {
                const cell = document.createElement('div');
                cell.className = 'cell';
                cell.dataset.row = i;
                cell.dataset.col = j;
                cell.dataset.number = num;
                cell.textContent = num === 0 ? 'FREE' : num;
                
                if (num === 0) {
                    cell.classList.add('free');
                }
                
                if (this.gameData.marked[i][j]) {
                    cell.classList.add('marked');
                }
                
                cell.addEventListener('click', () => this.markNumber(num));
                this.gridEl.appendChild(cell);
            });
        });
    }

    async markNumber(number) {
        if (number === 0) return;
        
        try {
            const response = await fetch(`/api/game/${this.userId}/mark`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ number })
            });
            
            if (response.ok) {
                const data = await response.json();
                if (data.won) {
                    window.Telegram.WebApp.showAlert('🎉 BINGO! You WON!');
                }
                await this.loadGame();
            }
        } catch (e) {
            console.error('Mark error:', e);
        }
    }

    updateStatus() {
        this.statusEl.textContent = this.gameData?.wins?.length > 0 
            ? `🎉 ${this.gameData.wins.length} Win(s)!` 
            : 'Ready to play!';
        this.statusEl.style.color = this.gameData?.wins?.length > 0 ? '#4ecdc4' : '#333';
    }

    updateWins() {
        if (!this.gameData?.wins || this.gameData.wins.length === 0) {
            document.getElementById('winsContainer').style.display = 'none';
            return;
        }
        
        document.getElementById('winsContainer').style.display = 'block';
        document.getElementById('winsList').innerHTML = this.gameData.wins.map(win => 
            `<div class="wins-list">${win}</div>`
        ).join('');
    }

    updateCalledNumbers() {
        const calledList = document.getElementById('calledList');
        if (this.gameData?.called_numbers) {
            calledList.innerHTML = this.gameData.called_numbers.slice(-15).map(num => {
                const letter = "BINGO"[Math.floor(num / 15)];
                return `<span class="called-number-small">${letter}${num}</span>`;
            }).join('');
        }
    }

    bindEvents() {
        document.getElementById('newGameBtn').onclick = () => {
            window.Telegram.WebApp.sendData(JSON.stringify({action: 'new_game'}));
            window.Telegram.WebApp.close();
        };

        document.getElementById('autoMarkBtn').onclick = () => {
            const latestCalled = this.gameData?.called_numbers?.slice(-1)[0];
            if (latestCalled) {
                this.markNumber(latestCalled);
            }
        };

        document.getElementById('shareBtn').onclick = () => {
            window.Telegram.WebApp.shareUrl(
                window.Telegram.WebApp.initDataUnsafe.start_app_username,
                'Check out my Bingo card! 🎮'
            );
        };
    }
}

new BingoWebApp();
