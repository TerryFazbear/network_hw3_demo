#!/usr/bin/env python3
"""
Tic Tac Toe Game Server
Simple 2-player turn-based game
"""
import socket
import json
import threading
import argparse

class TicTacToeServer:
    def __init__(self, port, max_players=2):
        self.port = port
        self.max_players = max_players
        self.clients = []
        self.usernames = {}
        self.recv_buffers = {}  # Per-socket receive buffers
        self.lock = threading.RLock()  # Re-entrant lock to prevent broadcast deadlock
        self.running = True
        
        # Game state
        self.board = [' '] * 9  # 3x3 board
        self.current_player = 0  # 0 or 1
        self.players = []  # Ordered list of client sockets
        self.game_started = False
        self.game_over = False
    
    def send_json(self, client_socket, data):
        """Send JSON message"""
        try:
            message = json.dumps(data) + '\n'
            client_socket.sendall(message.encode('utf-8'))
            return True
        except:
            return False
    
    def receive_json(self, client_socket):
        """Receive JSON message with proper line buffering"""
        try:
            # Initialize buffer for this socket if needed
            if client_socket not in self.recv_buffers:
                self.recv_buffers[client_socket] = b''
            
            # Read until we have a complete line
            while b'\n' not in self.recv_buffers[client_socket]:
                chunk = client_socket.recv(1024)
                if not chunk:
                    return None
                self.recv_buffers[client_socket] += chunk
            
            # Split at first newline
            line, remainder = self.recv_buffers[client_socket].split(b'\n', 1)
            self.recv_buffers[client_socket] = remainder
            
            # Parse and return the message
            message = line.decode('utf-8').strip()
            return json.loads(message)
        except Exception as e:
            print(f"[Server] receive_json error: {e}", flush=True)
            return None
    
    def broadcast(self, data, exclude=None):
        """Broadcast message to all clients"""
        with self.lock:
            for client in self.clients[:]:
                if client != exclude:
                    if not self.send_json(client, data):
                        self.clients.remove(client)
    
    def check_winner(self):
        """Check if there's a winner"""
        # Check rows
        for i in range(0, 9, 3):
            if self.board[i] == self.board[i+1] == self.board[i+2] != ' ':
                return self.board[i]
        
        # Check columns
        for i in range(3):
            if self.board[i] == self.board[i+3] == self.board[i+6] != ' ':
                return self.board[i]
        
        # Check diagonals
        if self.board[0] == self.board[4] == self.board[8] != ' ':
            return self.board[0]
        if self.board[2] == self.board[4] == self.board[6] != ' ':
            return self.board[2]
        
        return None
    
    def is_board_full(self):
        """Check if board is full"""
        return ' ' not in self.board
    
    def get_board_display(self):
        """Get formatted board"""
        return f"""
     {self.board[0]} | {self.board[1]} | {self.board[2]}
    ---+---+---
     {self.board[3]} | {self.board[4]} | {self.board[5]}
    ---+---+---
     {self.board[6]} | {self.board[7]} | {self.board[8]}
"""
    
    def handle_client(self, client_socket, addr):
        """Handle individual client connection"""
        username = None
        symbol = None
        
        try:
            # Receive username
            msg = self.receive_json(client_socket)
            if not msg or msg.get('type') != 'join':
                return
            
            username = msg.get('username', 'Player')
            
            with self.lock:
                if len(self.clients) >= self.max_players:
                    self.send_json(client_socket, {'type': 'error', 'message': 'Game full'})
                    return
                
                self.clients.append(client_socket)
                self.players.append(client_socket)
                player_num = len(self.players) - 1
                symbol = 'X' if player_num == 0 else 'O'
                self.usernames[client_socket] = username
                
                print(f"[Server] {username} joined as {symbol} ({len(self.clients)}/{self.max_players})")
            
            # Send welcome
            self.send_json(client_socket, {
                'type': 'welcome',
                'symbol': symbol,
                'player_num': player_num,
                'message': f'Welcome {username}! You are {symbol}'
            })
            
            # Announce to others
            self.broadcast({
                'type': 'player_joined',
                'username': username,
                'symbol': symbol,
                'players': len(self.clients)
            }, exclude=client_socket)
            
            # Start game if we have 2 players
            with self.lock:
                if len(self.clients) == self.max_players and not self.game_started:
                    self.game_started = True
                    self.broadcast({
                        'type': 'game_start',
                        'message': 'Game starting!',
                        'current_player': self.current_player,
                        'board': self.board
                    })
            
            # Game loop
            while self.running and not self.game_over:
                msg = self.receive_json(client_socket)
                if not msg:
                    break
                
                if msg.get('type') == 'move':
                    position = msg.get('position')
                    
                    with self.lock:
                        # Check if it's this player's turn
                        if self.players[self.current_player] != client_socket:
                            self.send_json(client_socket, {
                                'type': 'error',
                                'message': 'Not your turn!'
                            })
                            continue
                        
                        # Check if position is valid
                        if position < 0 or position > 8 or self.board[position] != ' ':
                            self.send_json(client_socket, {
                                'type': 'error',
                                'message': 'Invalid move!'
                            })
                            continue
                        
                        # Make move
                        self.board[position] = symbol
                        
                        # Check for winner
                        winner = self.check_winner()
                        if winner:
                            self.game_over = True
                            self.broadcast({
                                'type': 'game_over',
                                'winner': winner,
                                'winner_name': username,
                                'board': self.board,
                                'message': f'{username} ({winner}) wins!'
                            })
                            break
                        
                        # Check for draw
                        if self.is_board_full():
                            self.game_over = True
                            self.broadcast({
                                'type': 'game_over',
                                'winner': None,
                                'board': self.board,
                                'message': "It's a draw!"
                            })
                            break
                        
                        # Switch turns
                        self.current_player = 1 - self.current_player
                        
                        # Broadcast move
                        self.broadcast({
                            'type': 'move',
                            'position': position,
                            'symbol': symbol,
                            'username': username,
                            'board': self.board,
                            'current_player': self.current_player
                        })
                
                elif msg.get('type') == 'quit':
                    break
        
        except Exception as e:
            print(f"[Server] Client error: {e}")
        
        finally:
            # Remove client
            with self.lock:
                if client_socket in self.clients:
                    self.clients.remove(client_socket)
                if client_socket in self.players:
                    self.players.remove(client_socket)
                no_clients_left = (len(self.clients) == 0)
            
            # Announce leave
            if username:
                self.broadcast({
                    'type': 'player_left',
                    'username': username
                })
                print(f"[Server] {username} disconnected ({len(self.clients)}/{self.max_players})")
            
            # Shutdown server if last client left
            if no_clients_left:
                print("[Server] No clients left, shutting down game server.")
                self.running = False
            
            try:
                client_socket.close()
            except:
                pass
    
    def start(self):
        """Start the server"""
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.settimeout(1.0)
        server_socket.bind(('0.0.0.0', self.port))
        server_socket.listen(5)
        
        print(f"[Tic Tac Toe Server] Listening on port {self.port}")
        print(f"[Server] Max players: {self.max_players}")
        
        try:
            while self.running:
                try:
                    client_socket, addr = server_socket.accept()
                    thread = threading.Thread(
                        target=self.handle_client,
                        args=(client_socket, addr),
                        daemon=True
                    )
                    thread.start()
                except socket.timeout:
                    continue
        except KeyboardInterrupt:
            print("\n[Server] Shutting down...")
        finally:
            self.running = False
            server_socket.close()
            print("[Server] Server stopped.")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Tic Tac Toe Game Server')
    parser.add_argument('--port', type=int, required=True, help='Server port')
    parser.add_argument('--players', type=int, default=2, help='Max players')
    
    args = parser.parse_args()
    
    server = TicTacToeServer(args.port, args.players)
    server.start()
