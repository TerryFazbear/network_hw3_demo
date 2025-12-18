"""
Simple Chat Game - Server
A basic multiplayer chat server
"""
import socket
import threading
import argparse
import json
import struct


class ChatServer:
    def __init__(self, port, max_players):
        self.port = port
        self.max_players = max_players
        self.clients = []
        self.players_joined = 0  # Track total players who have joined
        self.lock = threading.Lock()
        self.running = True
    
    def broadcast(self, message, exclude=None):
        """Broadcast message to all clients except excluded one"""
        with self.lock:
            for client in self.clients:
                if client != exclude:
                    try:
                        self.send_message(client, message)
                    except:
                        pass
    
    def send_message(self, sock, message):
        """Send a JSON message"""
        data = json.dumps(message).encode('utf-8')
        sock.sendall(struct.pack('!I', len(data)) + data)
    
    def receive_message(self, sock):
        """Receive a JSON message"""
        try:
            # Read length
            length_data = sock.recv(4)
            if not length_data:
                return None
            length = struct.unpack('!I', length_data)[0]
            
            # Read message
            data = b''
            while len(data) < length:
                chunk = sock.recv(length - len(data))
                if not chunk:
                    return None
                data += chunk
            
            return json.loads(data.decode('utf-8'))
        except:
            return None
    
    def handle_client(self, client_socket, addr):
        """Handle a connected client"""
        username = None
        
        try:
            # Receive username
            msg = self.receive_message(client_socket)
            if not msg or msg.get('type') != 'join':
                return
            
            username = msg.get('username', f'Player{len(self.clients)+1}')
            
            # Add to clients
            with self.lock:
                if len(self.clients) >= self.max_players:
                    self.send_message(client_socket, {
                        'type': 'error',
                        'message': 'Server full'
                    })
                    return
                
                self.clients.append(client_socket)
                self.players_joined += 1 # Increment total players
            
            # Send welcome
            self.send_message(client_socket, {
                'type': 'welcome',
                'message': f'Welcome {username}! Type messages to chat. Type /quit to leave.'
            })
            
            # Announce join
            self.broadcast({
                'type': 'system',
                'message': f'{username} joined the chat'
            }, exclude=client_socket)
            
            print(f"[Server] {username} connected ({len(self.clients)}/{self.max_players})")
            
            # Handle messages
            while self.running:
                msg = self.receive_message(client_socket)
                if not msg:
                    break
                
                if msg.get('type') == 'chat':
                    text = msg.get('text', '')
                    if text:
                        # Broadcast to all OTHER clients (exclude sender)
                        self.broadcast({
                            'type': 'chat',
                            'username': username,
                            'text': text
                        }, exclude=client_socket)
                elif msg.get('type') == 'quit':
                    print(f"[Server] {username} quit")
                    break
        
        except Exception as e:
            print(f"[Server] Client error: {e}")
        
        finally:
            # Remove client
            with self.lock:
                if client_socket in self.clients:
                    self.clients.remove(client_socket)
                no_clients_left = (len(self.clients) == 0)
            
            # Announce leave
            if username:
                self.broadcast({
                    'type': 'system',
                    'message': f'{username} left the chat'
                })
                print(f"[Server] {username} disconnected ({len(self.clients)}/{self.max_players})")
            
            # Shutdown server if all players who joined have left
            if no_clients_left and len(self.clients) == 0:
                print("[Server] All players have left, shutting down game server.")
                self.running = False
            
            try:
                client_socket.close()
            except:
                pass
    
    def start(self):
        """Start the server"""
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.settimeout(1.0)  # Non-blocking accept with 1 second timeout
        server_socket.bind(('0.0.0.0', self.port))
        server_socket.listen(5)
        
        print(f"[Chat Server] Listening on port {self.port}")
        print(f"[Chat Server] Max players: {self.max_players}")
        
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
                    # Timeout allows checking self.running periodically
                    continue
        except KeyboardInterrupt:
            print("\n[Server] Shutting down...")
        finally:
            self.running = False
            server_socket.close()
            print("[Server] Server stopped.")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, required=True)
    parser.add_argument('--players', type=int, default=10)
    args = parser.parse_args()
    
    server = ChatServer(args.port, args.players)
    server.start()
