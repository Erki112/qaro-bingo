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
        
        this.loadGame();
        this.renderGrid();
        this.bindEvents();
        
        // Poll for updates
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
                this.statusEl.textContent = 'Create new game with /new';
            }
        } catch (e) {
            console.error('Load game error:', e);
        }
    }

    renderGrid() {
        if (!this.gameData?.grid) return;
        
        this.gridEl.innerHTML = '';
        this.gameData.grid.forEach((row, i) => {
            row.forEach((num, j) => {
                const cell = document.createElement('div');
                cell.className = 'cell';
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
                    window.Telegram.WebApp.showAlert('🎉 BINGO! You won!');
                    this.updateWins();
                }
                this.loadGame();
            }
        } catch (e) {
            console.error('Mark error:', e);
        }
    }

    updateStatus() {
        if
