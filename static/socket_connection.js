const socket = io();

socket.on('connect', () => {
    console.log('Connected to server');
});

socket.on('trade_update', (data) => {
    const symbol = data.symbol;
    const lastAction = data.last_action;
    const tradeRecords = data.trade_records;

    // Update last action
    const lastActionElement = document.getElementById(`last_action-${symbol}`);
    if (lastActionElement) {
        lastActionElement.innerHTML = `${lastAction.action} at $${lastAction.price}`;
    }

    // Update trade history
    const tradeHistoryElement = document.querySelector('.trade-history ul');
    if (tradeHistoryElement) {
        tradeHistoryElement.innerHTML = tradeRecords.map(trade => `
            <li>
                <strong>${trade.side.charAt(0).toUpperCase() + trade.side.slice(1)}:</strong>
                ${trade.symbol} - ${trade.qty} shares at $${trade.price} on ${new Date(trade.time).toLocaleString()}
            </li>
        `).join('');
    }
});
