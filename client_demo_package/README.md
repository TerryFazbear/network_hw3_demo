# Game Store Client - TA Demo Guide

## 🎯 Quick Start (5 Minutes)

This package contains everything needed to demo the Game Store System as a client. The server is already running on `linux4.cs.nycu.edu.tw`.

---

## 📦 What's Included

```
client_demo/
├── lobby_client.py          # Player client
├── developer_client.py      # Developer client
├── common/
│   ├── protocol.py          # Network protocol
│   └── validate_game.py     # Game validation
├── games/
│   ├── simple_chat/         # Chat game v1.0
│   ├── simple_chat_v1.1/    # Chat game v1.1 (enhanced)
│   └── tic_tac_toe/         # Tic Tac Toe v1.0
└── README.md                # This file
```

---

## 🚀 Demo Instructions

### Step 1: Get the Files

```bash
# Clone from GitHub
git clone https://github.com/YOUR_REPO/hw3_client_demo.git
cd hw3_client_demo

# Or if you have the zip:
unzip hw3_client_demo.zip
cd hw3_client_demo
```

### Step 2: Test Connection

```bash
# Verify you can reach the server
ping linux4.cs.nycu.edu.tw
```

### Step 3: Demo as Developer

```bash
# Run developer client (connects to linux4 automatically)
python developer_client.py
```

**In the developer client:**
1. Register account: `developer1` / `password`
2. Login
3. Upload game: Enter `games/simple_chat` when prompted
4. Upload game: Enter `games/tic_tac_toe` when prompted  
5. Update game: Enter `games/simple_chat_v1.1` when prompted
6. List games (verify: simple_chat is now v1.1, tic_tac_toe is v1.0)
7. Quit

### Step 4: Demo as Player (Two Terminals)

**Terminal 1 (Player A - Host):**
```bash
python lobby_client.py

# In client:
# 1. Register: alice / password
# 2. Login
# 3. Download "simple_chat"
# 4. Create room "demo_room" for "simple_chat"
# 5. Wait for Player B to join
```

**Terminal 2 (Player B - Guest):**
```bash
python lobby_client.py

# In client:
# 1. Register: bob / password
# 2. Login
# 3. Download "simple_chat"
# 4. Join room "demo_room"
# 5. Wait for host to start
```

**Back in Terminal 1:**
- Select "Start Game"
- Game client launches automatically for both players
- Type messages to chat
- Type `/quit` to exit game
- Both return to lobby
- **Try starting another game** (shows room reuse!)

### Step 5: Demo Tic Tac Toe (Optional)

Repeat Step 4 but use "tic_tac_toe" instead:
- Download "tic_tac_toe"
- Create/join room for "tic_tac_toe"
- Play by entering positions 0-8
- Winner detected automatically

---

## 🎮 Use Case Coverage

This demo covers all requirements:

**Developer (D1-D3):**
- ✅ D1: Upload game (simple_chat, tic_tac_toe)
- ✅ D2: Update game (simple_chat v1.1)
- ✅ D3: Remove game (optional - use menu)

**Player (P1-P4):**
- ✅ P1: Browse games, view details, download
- ✅ P2: Create room, join room, start game, play
- ✅ P3: Submit review (after playing, use menu)
- ✅ P4: Multiple games (room resets after game ends)

---

## 🌐 Server Connection

**Clients connect to `linux4.cs.nycu.edu.tw` automatically** - no configuration needed!

- Lobby Server: `linux4.cs.nycu.edu.tw:10002`
- Developer Server: `linux4.cs.nycu.edu.tw:10003`
- Game Servers: `linux4.cs.nycu.edu.tw:5000-5100`

**Optional - To use different server:**
```bash
# Player client
python lobby_client.py <host> <port>

# Developer client
python developer_client.py <host> <port>
```

---

## 🎯 Expected Behavior

### ✅ What Should Work

1. **Cross-machine gameplay** - Host on one machine, guest on another
2. **Real-time communication** - Messages/moves appear immediately
3. **Room reuse** - After game ends, room resets to "waiting"
4. **Host migration** - If host leaves waiting room, guest becomes host
5. **Version updates** - Rooms auto-upgrade when developer uploads new version
6. **Clean exits** - Both players return to lobby after game ends

### 🎲 Game Descriptions

**Simple Chat v1.0:**
- 2 players
- Type messages to chat
- `/quit` to exit

**Simple Chat v1.1:**
- Same as v1.0 but with emoji support
- Supports emoji if you paste them: 😊 👍 🎮

**Tic Tac Toe v1.0:**
- 2 players (X and O)
- Enter position 0-8 to place mark
- Win by getting 3 in a row
- `/quit` to exit

---

## 🐛 Troubleshooting

### "Connection refused"
- Check if server is running: `nc -vz linux4.cs.nycu.edu.tw 10002`
- Verify firewall allows outbound connections
- Try `ping linux4.cs.nycu.edu.tw`

### "Game client exited immediately"
- Game server port may be unreachable
- This is a server-side firewall issue (ports 5000-5100)
- Server admin should check `game_server_logs/` directory

### "Username already exists"
- Use different username
- Or ask server admin to run: `python clean_database.py --force`

### Game doesn't start after clicking "Start Game"
- Wait 1-2 seconds (game server needs time to start)
- Check if all players have downloaded the game
- If stuck, leave room and create new one

---


## ✅ System Requirements

- Python 3.7 or higher
- Network access to linux4.cs.nycu.edu.tw
- Standard library only (no pip install needed)



