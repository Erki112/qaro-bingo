class BingoWebApp {
    constructor() {
        this.init();
    }

    async init() {
        // Telegram WebApp setup
        window.Telegram.WebApp.ready();
        window.Telegram.WebApp.expand();
        window.Telegram.WebApp.MainButton.setText('New Game').show().onClick(this.createNewGame.bind(this));
        
        // Get user ID properly
        const user = window.Telegram.WebApp.initDataUnsafe?.user;
        this.userId = user ? String(user.id) : 'guest_' + Date.now();
        
        console.log('🆔 User ID:', this.userId); // Debug
        
        this.statusEl = document.getElementById('status');
        this.gridEl = document.getElementById('bingoGrid');
        this.winsEl = document.getElementById('winsList');
        this.calledListEl = document.getElementById('calledList');
        
        this.statusEl.textContent = 'Loading game...';
        await this.loadGame();
        this.bindEvents();
        
        // Auto-refresh every 3 seconds
        setInterval(() => this.loadGame(), 3000);
    }

    async createNewGame() {
        try {
            this.statusEl.textContent = 'Creating new game...';
            const response = await fetch(`/api/new/${this.userId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            
            if (response.ok) {
                const data = await response.json();
                console.log('✅ New game created:', data);
                this.statusEl.textContent = '🎫 New game ready!';
                await this.loadGame();
            }
        } catch (error) {
            console.error('❌ Create game error:', error);
            this.statusEl.textContent = 'Error creating game';
        }
    }

    async loadGame() {
        try {
            console.log('🔄 Loading game for:', this.userId);
            const response = await fetch(`/api/game/${this.userId}`);
            
            if (response.ok) {
                const data = await response.json();
                console.log('✅ Game data loaded:', data.grid?.length || 'no grid');
                this.gameData = data;
                this.renderGrid();
                this.updateStatus();
                this.updateWins();
                this.updateCalledNumbers();
            } else {
                console.log('⚠️ No game yet - waiting for /new or WebApp new game');
                this.statusEl.textContent = '👆 Click "New Game" or use /new command';
            }
        } catch (error) {
            console.error('❌ Load game error:', error);
            this.statusEl.textContent = 'Connection error - check console';
        }
    }

    renderGrid() {
        if (!this.gameData?.grid) {
            this.gridEl.innerHTML = '<div style="grid-column: 1/-1; text-align: center; padding: 40px; color: #666;">No game yet - click New Game!</div>';
            return;
        }
        
        this.gridEl.innerHTML = '';
        this.gameData.grid.forEach((row, i) => {
            row.forEach((num, j) => {
                const cell = document.createElement('div');
                cell.className = 'cell';
                cell.dataset.number = num;
                cell.textContent = num === 0 ? 'FREE' : num;
                
                if (num === 0) cell.classList.add('free');
                if (this.gameData.marked[i][j]) cell.classList.add('marked');
                
                cell.addEventListener('click', () => this.markNumber(num));
                this.gridEl.appendChild(cell);
            });
        });
    }

    async markNumber(number) {
        if (number === 0 || !this.gameData) return;
        
        try {
            const response = await fetch(`/api/game/${this.userId}/mark`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ number })
            });
            
            if (response.ok) {
                await this.loadGame();
            }
        } catch (error) {
            console.error('Mark error:', error);
        }
    }

    updateStatus() {
        if (this.gameData?.wins?.length > 0) {
            this.statusEl.textContent = `🎉 ${this.gameData.wins.length} WIN${this.gameData.wins.length === 1 ? '' : 'S'}!`;
            this.statusEl.style.color = '#4ecdc4';
        } else {
            this.statusEl.textContent = 'Ready! Use /call to mark numbers';
        }
    }

    updateWins() {
        const container = document.getElementById('winsContainer');
        if (!this.gameData?.wins?.length) {
            container.style.display = 'none';
            return;
        }
        container.style.display = 'block';
        document.getElementById('winsList').innerHTML = 
            this.gameData.wins.map(w => `<div>${w}</div>`).join('');
    }

    updateCalledNumbers() {
        const calledList = document.getElementById('calledList');
        if (this.gameData?.called_numbers) {
            calledList.innerHTML = this.gameData.called_numbers.slice(-10).map(num => {
                const letter = "BINGO"[Math.floor((num-1) / 15)];
                return `<span class="called-number-small">${letter}${num}</span>`;
            }).join('');
        }
    }

    bindEvents() {
        // Main button handles new game now
        document.getElementById('newGameBtn').style.display = 'none'; // Hide duplicate
        
        document.getElementById('autoMarkBtn').onclick = () => {
            const latest = this.gameData?.called_numbers?.slice(-1)[0];
            if (latest) this.markNumber(latest);
        };
        
        document.getElementById('shareBtn').onclick = () => {
            window.Telegram.WebApp.openTelegramLink(
                `https://t.me/${window.Telegram.WebApp.initDataUnsafe.start_app_username}?start=share`
            );
        };
    }
}

// Initialize when page loads
window.addEventListener('DOMContentLoaded', () => {
    new BingoWebApp();
});
