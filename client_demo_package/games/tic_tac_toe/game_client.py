#!/usr/bin/env python3
"""
Tic Tac Toe Game Client
Simple 2-player turn-based game
"""
import socket
import json
import threading
import argparse
import sys

class TicTacToeClient:
    def __init__(self, host, port, username):
        self.host = host
        self.port = port
        self.username = username
        self.socket = None
        self.running = True
        self.my_symbol = None
        self.my_turn = False
        self.player_num = None
        self.board = [' '] * 9
        self.game_over = False
        self.recv_buffer = b''  # Line-buffered receive
    
    def send_json(self, data):
        """Send JSON message"""
        try:
            message = json.dumps(data) + '\n'
            self.socket.sendall(message.encode('utf-8'))
            return True
        except:
            return False
    
    def receive_json(self):
        """Receive JSON message with proper line buffering"""
        try:
            # Read until we have a complete line
            while b'\n' not in self.recv_buffer:
                chunk = self.socket.recv(1024)
                if not chunk:
                    return None
                self.recv_buffer += chunk
            
            # Split at first newline
            line, remainder = self.recv_buffer.split(b'\n', 1)
            self.recv_buffer = remainder
            
            # Parse and return the message
            message = line.decode('utf-8').strip()
            return json.loads(message)
        except Exception as e:
            print(f"[Client] receive_json error: {e}", flush=True)
            return None
    
    def display_board(self):
        """Display the game board"""
        print("\n  Positions:       Current Board:")
        print(f"   0 | 1 | 2        {self.board[0]} | {self.board[1]} | {self.board[2]}")
        print(f"  ---+---+---      ---+---+---")
        print(f"   3 | 4 | 5        {self.board[3]} | {self.board[4]} | {self.board[5]}")
        print(f"  ---+---+---      ---+---+---")
        print(f"   6 | 7 | 8        {self.board[6]} | {self.board[7]} | {self.board[8]}")
        print()
    
    def receive_messages(self):
        """Receive messages from server"""
        while self.running:
            msg = self.receive_json()
            if not msg:
                break
            
            msg_type = msg.get('type')
            
            if msg_type == 'welcome':
                self.my_symbol = msg.get('symbol')
                self.player_num = msg.get('player_num')
                print(f"\n✓ {msg.get('message')}")
                print("Waiting for opponent...")
                self.my_turn = (self.player_num == 0)
            
            elif msg_type == 'player_joined':
                username = msg.get('username')
                symbol = msg.get('symbol')
                print(f"\n✓ {username} joined as {symbol}")
            
            elif msg_type == 'game_start':
                print("\n" + "="*50)
                print("🎮 GAME STARTING!")
                print("="*50)
                self.board = msg.get('board', [' '] * 9)
                current_player = msg.get('current_player', 0)
                self.my_turn = (self.player_num == current_player)
                self.display_board()
                if self.my_turn:
                    print(f"👉 Your turn! (You are {self.my_symbol})")
                    print("Enter position (0-8) or 'quit': ", end='', flush=True)
                else:
                    print(f"⏳ Waiting for opponent's move...")
            
            elif msg_type == 'move':
                position = msg.get('position')
                symbol = msg.get('symbol')
                username = msg.get('username')
                self.board = msg.get('board')
                current_player = msg.get('current_player')
                
                print(f"\n{username} ({symbol}) placed at position {position}")
                self.display_board()
                
                # Update turn based on server's current_player
                self.my_turn = (current_player == self.player_num)
                
                if self.my_turn:
                    print(f"👉 Your turn! (You are {self.my_symbol})")
                    print("Enter position (0-8) or 'quit': ", end='', flush=True)
                else:
                    print(f"⏳ Waiting for opponent's move...")
            
            elif msg_type == 'game_over':
                self.game_over = True
                self.board = msg.get('board')
                winner = msg.get('winner')
                
                print("\n" + "="*50)
                print("🏁 GAME OVER!")
                print("="*50)
                self.display_board()
                
                if winner:
                    winner_name = msg.get('winner_name', 'Unknown')
                    if winner == self.my_symbol:
                        print(f"🎉 YOU WIN! Congratulations!")
                    else:
                        print(f"😢 {winner_name} ({winner}) wins!")
                else:
                    print(f"🤝 It's a draw!")
                
                print("\nType '/quit' to exit")
                self.running = False
            
            elif msg_type == 'player_left':
                username = msg.get('username')
                print(f"\n👋 {username} left the game")
                if not self.game_over:
                    print("Game ended due to player leaving.")
                    self.running = False
            
            elif msg_type == 'error':
                print(f"\n❌ {msg.get('message')}")
                if self.my_turn:
                    print("Enter position (0-8) or 'quit': ", end='', flush=True)
        
        print("\n[Connection closed]")
    
    def run(self):
        """Run the client"""
        try:
            # Connect to server
            print(f"🔌 Connecting to {self.host}:{self.port}...")
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            print("✓ Connected!")
            
            # Send join message
            self.send_json({
                'type': 'join',
                'username': self.username
            })
            
            # Start receive thread
            receive_thread = threading.Thread(target=self.receive_messages, daemon=True)
            receive_thread.start()
            
            # Input loop - only read when it's our turn
            import time
            while self.running:
                try:
                    # Only prompt for input when it's our turn
                    if self.my_turn and not self.game_over:
                        user_input = input().strip()
                        
                        if user_input.lower() in ['/quit', 'quit']:
                            self.send_json({'type': 'quit'})
                            break
                        
                        # Try to parse as position
                        try:
                            position = int(user_input)
                            if 0 <= position <= 8:
                                # Set turn to false immediately after submitting
                                self.my_turn = False
                                self.send_json({
                                    'type': 'move',
                                    'position': position
                                })
                            else:
                                print("Invalid position! Enter 0-8")
                                print("Enter position (0-8) or 'quit': ", end='', flush=True)
                        except ValueError:
                            if user_input:  # Ignore empty input
                                print("Invalid input! Enter a number 0-8 or 'quit'")
                                print("Enter position (0-8) or 'quit': ", end='', flush=True)
                    else:
                        # Not our turn or game over - sleep briefly
                        time.sleep(0.1)
                
                except EOFError:
                    break
        
        except ConnectionRefusedError:
            print(f"❌ Could not connect to {self.host}:{self.port}")
        except Exception as e:
            print(f"❌ Error: {e}")
        finally:
            self.running = False
            if self.socket:
                self.socket.close()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Tic Tac Toe Game Client')
    parser.add_argument('--host', type=str, required=True, help='Server host')
    parser.add_argument('--port', type=int, required=True, help='Server port')
    parser.add_argument('--username', type=str, required=True, help='Your username')
    
    args = parser.parse_args()
    
    client = TicTacToeClient(args.host, args.port, args.username)
    client.run()
