document.addEventListener('DOMContentLoaded', function() {
    var socket = io.connect(window.location.origin);

    socket.on('connect', function() {
        console.log('Connected to the server!');
    });

    socket.on('data_update', function(data) {
        console.log('Received data:', data);
        if (data.market_status) {
            document.getElementById('market_status').innerText = data.market_status;
        }
        if (data.portfolio_balance) {
            document.getElementById('portfolio_balance').innerText = `$${data.portfolio_balance}`;
        }
       
    });
});