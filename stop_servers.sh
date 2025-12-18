#!/bin/bash
# Stop all Game Store servers

echo "🛑 Stopping all servers..."

# Kill servers by port
pkill -f "database_server.py" && echo "✓ Database server stopped"
pkill -f "developer_server.py" && echo "✓ Developer server stopped"
pkill -f "lobby_server.py" && echo "✓ Lobby server stopped"

# Alternative: kill by port if above doesn't work
# lsof -ti:10001 | xargs kill -9 2>/dev/null
# lsof -ti:10002 | xargs kill -9 2>/dev/null
# lsof -ti:10003 | xargs kill -9 2>/dev/null

echo "✓ All servers stopped"
