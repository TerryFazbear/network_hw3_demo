"""
TCP Protocol for Game Store System
Handles message serialization/deserialization with length-prefixed JSON
"""
import json
import struct
import socket
from typing import Optional, Dict, Any


class Protocol:
    """Simple TCP protocol with length-prefixed JSON messages"""
    
    def __init__(self, sock: socket.socket):
        self.sock = sock
        self.closed = False
    
    def send_message(self, message: Dict[str, Any]) -> bool:
        """Send a JSON message with 4-byte length prefix"""
        try:
            data = json.dumps(message).encode('utf-8')
            length = struct.pack('!I', len(data))
            self.sock.sendall(length + data)
            return True
        except Exception as e:
            print(f"[Protocol] Send error: {e}")
            self.closed = True
            return False
    
    def receive_message(self) -> Optional[Dict[str, Any]]:
        """Receive a length-prefixed JSON message"""
        try:
            # Read 4-byte length header
            length_data = self._recv_exact(4)
            if not length_data:
                self.closed = True
                return None
            
            length = struct.unpack('!I', length_data)[0]
            
            # Read message body
            message_data = self._recv_exact(length)
            if not message_data:
                self.closed = True
                return None
            
            return json.loads(message_data.decode('utf-8'))
        except Exception as e:
            print(f"[Protocol] Receive error: {e}")
            self.closed = True
            return None
    
    def _recv_exact(self, n: int) -> Optional[bytes]:
        """Receive exactly n bytes from socket"""
        data = b''
        while len(data) < n:
            chunk = self.sock.recv(n - len(data))
            if not chunk:
                return None
            data += chunk
        return data
    
    def send_file(self, filepath: str) -> bool:
        """Send a file over the socket"""
        try:
            import os
            with open(filepath, 'rb') as f:
                file_data = f.read()
            
            # Send file size first
            file_size = len(file_data)
            self.sock.sendall(struct.pack('!Q', file_size))
            
            # Send file data in chunks
            chunk_size = 8192
            for i in range(0, file_size, chunk_size):
                chunk = file_data[i:i+chunk_size]
                self.sock.sendall(chunk)
            
            return True
        except Exception as e:
            print(f"[Protocol] File send error: {e}")
            return False
    
    def receive_file(self, save_path: str) -> bool:
        """Receive a file and save it"""
        try:
            import os
            
            # Receive file size
            size_data = self._recv_exact(8)
            if not size_data:
                return False
            file_size = struct.unpack('!Q', size_data)[0]
            
            # Create directory if needed
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            
            # Receive file data
            received = 0
            with open(save_path, 'wb') as f:
                while received < file_size:
                    chunk_size = min(8192, file_size - received)
                    chunk = self.sock.recv(chunk_size)
                    if not chunk:
                        return False
                    f.write(chunk)
                    received += len(chunk)
            
            return True
        except Exception as e:
            print(f"[Protocol] File receive error: {e}")
            return False
    
    def close(self):
        """Close the socket"""
        if not self.closed:
            try:
                self.sock.close()
            except:
                pass
            self.closed = True
