#!/bin/bash
# Start all servers on Linux

echo "Starting Game Store Servers..."
echo ""

echo "Starting Database Server (port 10001)..."
python3 server/database_server.py &
DB_PID=$!
sleep 2

echo "Starting Developer Server (port 10003)..."
python3 server/developer_server.py &
DEV_PID=$!
sleep 1

echo "Starting Lobby Server (port 10002)..."
python3 server/lobby_server.py &
LOBBY_PID=$!
sleep 1

echo ""
echo "All servers started!"
echo "Database Server: 127.0.0.1:10001 (PID: $DB_PID)"
echo "Lobby Server: 0.0.0.0:10002 → linux4.cs.nycu.edu.tw:10002 (PID: $LOBBY_PID)"
echo "Developer Server: 127.0.0.1:10003 (PID: $DEV_PID)"
echo ""
echo "Clients should connect to: linux4.cs.nycu.edu.tw"
echo "Press Ctrl+C to stop all servers"

# Wait for interrupt
trap "kill $DB_PID $DEV_PID $LOBBY_PID 2>/dev/null; echo ''; echo 'All servers stopped'; exit" INT
wait
