"""
Simple Chat Game - Client v1.1
Enhanced with better UI
"""
import socket
import threading
import argparse
import json
import struct
import sys


class ChatClient:
    def __init__(self, host, port, username):
        self.host = host
        self.port = port
        self.username = username
        self.socket = None
        self.running = False
    
    def send_message(self, message):
        """Send a JSON message"""
        try:
            data = json.dumps(message).encode('utf-8')
            self.socket.sendall(struct.pack('!I', len(data)) + data)
            return True
        except:
            return False
    
    def receive_message(self):
        """Receive a JSON message"""
        try:
            # Read length
            length_data = self.socket.recv(4)
            if not length_data:
                return None
            length = struct.unpack('!I', length_data)[0]
            
            # Read message
            data = b''
            while len(data) < length:
                chunk = self.socket.recv(length - len(data))
                if not chunk:
                    return None
                data += chunk
            
            return json.loads(data.decode('utf-8'))
        except:
            return None
    
    def receive_loop(self):
        """Background thread to receive messages"""
        while self.running:
            msg = self.receive_message()
            if not msg:
                break
            
            msg_type = msg.get('type')
            
            if msg_type == 'welcome':
                print(f"\n{'='*60}")
                print(msg.get('message', ''))
                print('='*60)
            elif msg_type == 'system':
                print(f"\n💬 {msg.get('message', '')}")
            elif msg_type == 'chat':
                username = msg.get('username', 'Unknown')
                text = msg.get('text', '')
                print(f"\n[{username}] {text}")
            elif msg_type == 'error':
                print(f"\n❌ {msg.get('message', '')}")
                self.running = False
        
        self.running = False
    
    def connect(self):
        """Connect to game server"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            
            # Send join message
            self.send_message({
                'type': 'join',
                'username': self.username
            })
            
            return True
        except Exception as e:
            print(f"Connection failed: {e}")
            return False
    
    def run(self):
        """Run the client"""
        print("="*60)
        print(f"   Simple Chat v1.1 - Player: {self.username}")
        print("="*60)
        print(f"Connecting to {self.host}:{self.port}...")
        
        if not self.connect():
            return
        
        print("Connected!")
        self.running = True
        
        # Start receive thread
        receive_thread = threading.Thread(target=self.receive_loop, daemon=True)
        receive_thread.start()
        
        # Input loop
        try:
            while self.running:
                text = input()
                
                if not self.running:
                    break
                
                if not text.strip():
                    continue
                
                if text.strip().lower() == '/quit':
                    self.send_message({'type': 'quit'})
                    break
                
                # Print own message locally (v1.1 - with emoji)
                print(f"\n💬 [{self.username}] {text}")
                
                # Send chat message
                if not self.send_message({
                    'type': 'chat',
                    'text': text
                }):
                    print("Failed to send message")
                    break
        
        except KeyboardInterrupt:
            print("\nDisconnecting...")
        
        finally:
            self.running = False
            try:
                self.socket.close()
            except:
                pass


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', type=str, required=True)
    parser.add_argument('--port', type=int, required=True)
    parser.add_argument('--username', type=str, required=True)
    args = parser.parse_args()
    
    client = ChatClient(args.host, args.port, args.username)
    client.run()
