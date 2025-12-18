"""
Developer Server - Port 10003
Handles game uploads, updates, and removals
"""
import socket
import os
import sys
import shutil
from threading import Thread

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.protocol import Protocol
from common.validate_game import validate_game_package, get_game_files


class DeveloperServer:
    def __init__(self, host='0.0.0.0', port=10003, db_port=10001, upload_dir='uploaded_games'):
        self.host = host
        self.port = port
        self.db_host = '127.0.0.1'
        self.db_port = db_port
        self.upload_dir = upload_dir
        self.running = False
        
        print("\n" + "="*70)
        print("🔧 DEVELOPER SERVER v2.1 - BUILD 2025-12-17-18:30")
        print("="*70)
        print(f"✓ Port: {self.port}")
        print(f"✓ Upload dir: {self.upload_dir}")
        print("="*70 + "\n")
        
        os.makedirs(upload_dir, exist_ok=True)
    
    def _db_request(self, request: dict) -> dict:
        """Send a request to database server"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((self.db_host, self.db_port))
            protocol = Protocol(sock)
            
            protocol.send_message(request)
            response = protocol.receive_message()
            
            protocol.close()
            return response or {'success': False, 'error': 'No response'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def start(self):
        """Start the developer server"""
        self.running = True
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((self.host, self.port))
        server_socket.listen(5)
        
        print(f"[Dev Server] Listening on {self.host}:{self.port}")
        
        try:
            while self.running:
                client_socket, addr = server_socket.accept()
                print(f"[Dev Server] Connection from {addr}")
                Thread(target=self._handle_client, args=(client_socket,), daemon=True).start()
        except KeyboardInterrupt:
            print("\n[Dev Server] Shutting down...")
        finally:
            server_socket.close()
    
    def _handle_client(self, client_socket: socket.socket):
        """Handle developer client connection"""
        protocol = Protocol(client_socket)
        session = {'logged_in': False, 'user_id': None, 'username': None}
        
        try:
            while not protocol.closed:
                message = protocol.receive_message()
                if not message:
                    break
                
                response = self._process_request(protocol, session, message)
                if response:
                    protocol.send_message(response)
        except Exception as e:
            print(f"[Dev Server] Client error: {e}")
        finally:
            protocol.close()
    
    def _process_request(self, protocol: Protocol, session: dict, request: dict) -> dict:
        """Process developer requests"""
        action = request.get('action')
        
        # Auth actions (no login required)
        if action == 'register':
            return self._handle_register(request)
        elif action == 'login':
            return self._handle_login(session, request)
        
        # Protected actions (login required)
        if not session['logged_in']:
            return {'success': False, 'error': 'Not logged in'}
        
        if action == 'my_games':
            return self._handle_my_games(session)
        elif action == 'upload_game':
            return self._handle_upload_game(protocol, session, request)
        elif action == 'update_game':
            return self._handle_update_game(protocol, session, request)
        elif action == 'remove_game':
            return self._handle_remove_game(session, request)
        elif action == 'logout':
            session['logged_in'] = False
            return {'success': True}
        
        return {'success': False, 'error': 'Unknown action'}
    
    def _handle_register(self, request: dict) -> dict:
        """Register a new developer account"""
        from server.database_server import hash_password
        
        username = request.get('username', '').strip()
        password = request.get('password', '').strip()
        
        if not username or not password:
            return {'success': False, 'error': 'Username and password required'}
        
        # Check if username exists
        check = self._db_request({
            'action': 'find_one',
            'collection': 'User',
            'data': {'query': {'username': username, 'account_type': 'developer'}}
        })
        
        if check.get('success'):
            return {'success': False, 'error': 'Username already exists'}
        
        # Create user
        result = self._db_request({
            'action': 'insert',
            'collection': 'User',
            'data': {
                'username': username,
                'password_hash': hash_password(password),
                'account_type': 'developer'
            }
        })
        
        if result.get('success'):
            return {'success': True, 'message': 'Developer account created'}
        return {'success': False, 'error': 'Registration failed'}
    
    def _handle_login(self, session: dict, request: dict) -> dict:
        """Login a developer"""
        from server.database_server import hash_password
        
        username = request.get('username', '').strip()
        password = request.get('password', '').strip()
        
        if not username or not password:
            return {'success': False, 'error': 'Username and password required'}
        
        # Find user
        result = self._db_request({
            'action': 'find_one',
            'collection': 'User',
            'data': {'query': {'username': username, 'account_type': 'developer'}}
        })
        
        if not result.get('success'):
            return {'success': False, 'error': 'Invalid username or password'}
        
        user = result['result']
        if user['password_hash'] != hash_password(password):
            return {'success': False, 'error': 'Invalid username or password'}
        
        # Set session
        session['logged_in'] = True
        session['user_id'] = user['_id']
        session['username'] = user['username']
        
        return {'success': True, 'message': f'Welcome {username}!'}
    
    def _handle_my_games(self, session: dict) -> dict:
        """Get developer's games"""
        result = self._db_request({
            'action': 'find',
            'collection': 'Game',
            'data': {'query': {'developer_id': session['user_id']}}
        })
        
        if result.get('success'):
            return {'success': True, 'games': result['results']}
        return {'success': False, 'error': 'Failed to fetch games'}
    
    def _handle_upload_game(self, protocol: Protocol, session: dict, request: dict) -> dict:
        """Handle game upload"""
        game_name = request.get('game_name', '').strip()
        
        if not game_name:
            return {'success': False, 'error': 'Game name required'}
        
        # Check if game name exists
        check = self._db_request({
            'action': 'find_one',
            'collection': 'Game',
            'data': {'query': {'name': game_name}}
        })
        
        if check.get('success'):
            return {'success': False, 'error': 'Game name already exists'}
        
        # Send ready signal
        protocol.send_message({'success': True, 'message': 'Ready to receive files'})
        
        # Receive file count
        file_msg = protocol.receive_message()
        if not file_msg:
            return None
        
        file_count = file_msg.get('file_count', 0)
        if file_count == 0:
            return {'success': False, 'error': 'No files to upload'}
        
        # Create temporary upload directory
        import uuid
        temp_id = str(uuid.uuid4())[:8]
        temp_dir = os.path.join(self.upload_dir, f'temp_{temp_id}')
        os.makedirs(temp_dir, exist_ok=True)
        
        try:
            # Receive all files
            for i in range(file_count):
                file_info = protocol.receive_message()
                if not file_info:
                    raise Exception("Failed to receive file info")
                
                rel_path = file_info['path']
                file_path = os.path.join(temp_dir, rel_path)
                
                # Create directory if needed
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                
                # Receive file data
                if not protocol.receive_file(file_path):
                    raise Exception(f"Failed to receive file: {rel_path}")
            
            # Validate game package
            success, error, game_info = validate_game_package(temp_dir)
            if not success:
                raise Exception(f"Invalid game package: {error}")
            
            # Create game record
            version = game_info['version']
            final_dir_name = f"{game_name}_{version}"
            final_dir = os.path.join(self.upload_dir, final_dir_name)
            
            # Move to final location
            if os.path.exists(final_dir):
                shutil.rmtree(final_dir)
            shutil.move(temp_dir, final_dir)
            
            # Save to database
            game_result = self._db_request({
                'action': 'insert',
                'collection': 'Game',
                'data': {
                    'name': game_name,
                    'developer_id': session['user_id'],
                    'developer_name': session['username'],
                    'latest_version': version,
                    'description': game_info.get('description', ''),
                    'min_players': game_info.get('min_players', 2),
                    'max_players': game_info.get('max_players', 2),
                    'status': 'active'
                }
            })
            
            if not game_result.get('success'):
                raise Exception("Failed to save game to database")
            
            game_id = game_result['id']
            
            # Save version record
            self._db_request({
                'action': 'insert',
                'collection': 'Version',
                'data': {
                    'game_id': game_id,
                    'version': version,
                    'file_path': final_dir_name
                }
            })
            
            return {'success': True, 'message': f'Game "{game_name}" v{version} uploaded successfully'}
            
        except Exception as e:
            # Cleanup on error
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            return {'success': False, 'error': str(e)}
    
    def _handle_update_game(self, protocol: Protocol, session: dict, request: dict) -> dict:
        """Handle game update (new version)"""
        game_name = request.get('game_name', '').strip()
        
        if not game_name:
            return {'success': False, 'error': 'Game name required'}
        
        # Check if game exists and belongs to developer
        game_result = self._db_request({
            'action': 'find_one',
            'collection': 'Game',
            'data': {'query': {'name': game_name, 'developer_id': session['user_id']}}
        })
        
        if not game_result.get('success'):
            return {'success': False, 'error': 'Game not found or you do not own it'}
        
        game = game_result['result']
        
        # Send ready signal
        protocol.send_message({'success': True, 'message': 'Ready to receive files'})
        
        # Receive file count
        file_msg = protocol.receive_message()
        if not file_msg:
            return None
        
        file_count = file_msg.get('file_count', 0)
        
        # Create temporary directory
        import uuid
        temp_id = str(uuid.uuid4())[:8]
        temp_dir = os.path.join(self.upload_dir, f'temp_{temp_id}')
        os.makedirs(temp_dir, exist_ok=True)
        
        try:
            # Receive all files
            for i in range(file_count):
                file_info = protocol.receive_message()
                if not file_info:
                    raise Exception("Failed to receive file info")
                
                rel_path = file_info['path']
                file_path = os.path.join(temp_dir, rel_path)
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                
                if not protocol.receive_file(file_path):
                    raise Exception(f"Failed to receive file: {rel_path}")
            
            # Validate game package
            success, error, game_info = validate_game_package(temp_dir)
            if not success:
                raise Exception(f"Invalid game package: {error}")
            
            # Move to final location
            version = game_info['version']
            final_dir_name = f"{game_name}_{version}"
            final_dir = os.path.join(self.upload_dir, final_dir_name)
            
            if os.path.exists(final_dir):
                shutil.rmtree(final_dir)
            shutil.move(temp_dir, final_dir)
            
            # Update game record
            self._db_request({
                'action': 'update',
                'collection': 'Game',
                'data': {
                    'query': {'_id': game['_id']},
                    'update': {
                        'latest_version': version,
                        'min_players': game_info.get('min_players', 2),
                        'max_players': game_info.get('max_players', 10),
                        'description': game_info.get('description', '')
                    }
                }
            })
            
            # Add version record
            self._db_request({
                'action': 'insert',
                'collection': 'Version',
                'data': {
                    'game_id': game['_id'],
                    'version': version,
                    'file_path': final_dir_name
                }
            })
            
            return {'success': True, 'message': f'Game "{game_name}" updated to v{version}'}
            
        except Exception as e:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            return {'success': False, 'error': str(e)}
    
    def _handle_remove_game(self, session: dict, request: dict) -> dict:
        """Remove a game (mark as inactive)"""
        game_name = request.get('game_name', '').strip()
        
        if not game_name:
            return {'success': False, 'error': 'Game name required'}
        
        # Check ownership
        game_result = self._db_request({
            'action': 'find_one',
            'collection': 'Game',
            'data': {'query': {'name': game_name, 'developer_id': session['user_id']}}
        })
        
        if not game_result.get('success'):
            return {'success': False, 'error': 'Game not found or you do not own it'}
        
        # Mark as removed
        self._db_request({
            'action': 'update',
            'collection': 'Game',
            'data': {
                'query': {'name': game_name, 'developer_id': session['user_id']},
                'update': {'status': 'removed'}
            }
        })
        
        return {'success': True, 'message': f'Game "{game_name}" removed from store'}


if __name__ == '__main__':
    # Developer server accepts remote connections
    server = DeveloperServer()
    server.start()
