document.addEventListener('DOMContentLoaded', function() {
    var socket = io.connect(window.location.origin);

    socket.on('connect', function() {
        console.log('Connected to the server!');
    });

    socket.on('data_update', function(data) {
        console.log('Received data update:', data);
        updateData(data);
    });

    socket.on('trade_update', function(data) {
        console.log('Received trade update:', data);
        updateTradeData(data);
    });

    function updateData(data) {
        if (data.market_status) {
            document.getElementById('market_status').innerText = data.market_status;
        }
        if (data.portfolio_balance) {
            document.getElementById('portfolio_balance').innerText = `$${data.portfolio_balance}`;
        }
        if (data.account_type) {
            document.getElementById('account_type').innerText = data.account_type;
        }
        updateStockCards(data.data_list, data.last_actions);
    }

    function updateTradeData(data) {
        if (data.last_action) {
            document.getElementById(`last_action-${data.symbol}`).innerText = `${data.last_action.action} at $${data.last_action.price}`;
        }
        updateTradeHistory(data.trade_records);
    }

    function updateStockCards(dataList, lastActions) {
        const cardContainer = document.querySelector('.card-container');
        cardContainer.innerHTML = '';
        dataList.forEach(data => {
            const card = document.createElement('div');
            card.className = 'card';
            card.id = `card-${data.symbol}`;
            card.innerHTML = `
                <h3>${data.symbol}</h3>
                <p>Last Close: $${data.last_close}<br>
                ${data.last_close_time ? `(${new Date(data.last_close_time).toLocaleString()})` : '(Time data not available)'}</p>
                <p>Exchange: ${data.exchange}</p>
                <p><strong>Last Action:</strong> <span id="last_action-${data.symbol}">${lastActions[data.symbol].action ? `${lastActions[data.symbol].action} at $${lastActions[data.symbol].price}` : 'No action taken'}</span></p>
            `;
            cardContainer.appendChild(card);
        });
    }

    function updateTradeHistory(tradeRecords) {
        const tradeHistory = document.querySelector('.trade-history');
        tradeHistory.innerHTML = '';
        if (tradeRecords.length > 0) {
            const ul = document.createElement('ul');
            tradeRecords.forEach(trade => {
                const li = document.createElement('li');
                li.innerHTML = `<strong>${trade.side.charAt(0).toUpperCase() + trade.side.slice(1)}:</strong> ${trade.symbol} - ${trade.qty} shares at $${trade.price} on ${new Date(trade.time).toLocaleString()}`;
                ul.appendChild(li);
            });
            tradeHistory.appendChild(ul);
        } else {
            tradeHistory.innerHTML = '<p>No trades have been made yet.</p>';
        }
    }
});
