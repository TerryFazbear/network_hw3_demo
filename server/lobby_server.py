"""  
Lobby Server - Port 10002
Manages player authentication, room management, and game launching
"""
import socket
import os
import sys
import subprocess
import json
import time
from threading import Thread, Lock
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.protocol import Protocol
from common.validate_game import get_game_files


class LobbyServer:
    def __init__(self, host='0.0.0.0', port=10002, db_port=10001, upload_dir='uploaded_games', advertise_host='linux4.cs.nycu.edu.tw'):
        self.host = host
        self.port = port
        self.advertise_host = advertise_host  # Host clients should connect to for game servers
        self.db_host = '127.0.0.1'
        self.db_port = db_port
        self.upload_dir = upload_dir
        self.running = False
        
        # Create logs directory for game server stderr
        self.logs_dir = 'game_server_logs'
        os.makedirs(self.logs_dir, exist_ok=True)
        
        # Active sessions and rooms
        self.sessions = {}  # {user_id: {'username': ..., 'protocol': ...}}
        self.rooms = {}     # {room_id: {...}}
        self.lock = Lock()
        
        self.next_game_port = 5000
        
        # VERSION FOOTPRINT
        print("\n" + "="*70)
        print("🎮 LOBBY SERVER v2.1 - BUILD 2025-12-17-18:30 (ROOM RESET FIX)")
        print("="*70)
        print(f"✓ Bind host: {self.host}:{self.port} (listening on all interfaces)")
        print(f"✓ Advertise host: {self.advertise_host} (for game server connections)")
        print(f"✓ Game port range: 5000+")
        print(f"✓ Upload dir: {self.upload_dir}")
        print(f"✓ Features: Room auto-reset, version tracking, ghost cleanup")
        print("="*70 + "\n")
    
    def _find_available_port(self) -> int:
        """Find an available port for game server"""
        import socket as sock_module
        
        # Try ports in range
        for port in range(self.next_game_port, 5100):
            try:
                # Try to bind to check if port is available
                test_socket = sock_module.socket(sock_module.AF_INET, sock_module.SOCK_STREAM)
                test_socket.setsockopt(sock_module.SOL_SOCKET, sock_module.SO_REUSEADDR, 1)
                test_socket.bind(('0.0.0.0', port))
                test_socket.close()
                
                # Port is available
                self.next_game_port = port + 1
                return port
            except OSError:
                # Port in use, try next
                continue
        
        # Wrap around if we hit the max
        self.next_game_port = 5000
        raise Exception("No available ports in range 5000-5100")
    
    def _db_request(self, request: dict) -> dict:
        """Send request to database server"""
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
        """Start the lobby server"""
        self.running = True
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((self.host, self.port))
        server_socket.listen(5)
        
        print(f"[Lobby Server] Listening on {self.host}:{self.port}")
        
        try:
            while self.running:
                client_socket, addr = server_socket.accept()
                print(f"[Lobby] Connection from {addr}")
                Thread(target=self._handle_client, args=(client_socket,), daemon=True).start()
        except KeyboardInterrupt:
            print("\n[Lobby] Shutting down...")
        finally:
            server_socket.close()
    
    def _handle_client(self, client_socket: socket.socket):
        """Handle player client connection"""
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
            print(f"[Lobby] Client error: {e}")
        finally:
            # Cleanup on disconnect
            if session['logged_in']:
                self._cleanup_session(session)
            protocol.close()
    
    def _cleanup_session(self, session: dict):
        """Clean up when player disconnects"""
        with self.lock:
            user_id = session['user_id']
            if user_id in self.sessions:
                del self.sessions[user_id]
            
            # Remove from any rooms
            self._remove_user_from_all_rooms(user_id)
    
    def _remove_user_from_all_rooms(self, user_id: str):
        """Remove user from all rooms (prevents ghost membership)"""
        for room_id, room in list(self.rooms.items()):
            if user_id in room['players']:
                room['players'].remove(user_id)
                if len(room['players']) == 0:
                    # Kill game server if exists
                    if room.get('game_process'):
                        room['game_process'].terminate()
                    del self.rooms[room_id]
                elif user_id == room['host_id']:
                    # Transfer host to first remaining player
                    room['host_id'] = room['players'][0]
                    if room['players'][0] in self.sessions:
                        room['host_name'] = self.sessions[room['players'][0]]['username']
    
    def _process_request(self, protocol: Protocol, session: dict, request: dict) -> dict:
        """Process player requests"""
        action = request.get('action')
        
        # Auth actions
        if action == 'register':
            return self._handle_register(request)
        elif action == 'login':
            return self._handle_login(protocol, session, request)
        
        # Protected actions
        if not session['logged_in']:
            return {'success': False, 'error': 'Not logged in'}
        
        if action == 'list_games':
            return self._handle_list_games()
        elif action == 'game_info':
            return self._handle_game_info(request)
        elif action == 'download_game':
            return self._handle_download_game(protocol, request)
        elif action == 'list_rooms':
            return self._handle_list_rooms()
        elif action == 'create_room':
            return self._handle_create_room(session, request)
        elif action == 'join_room':
            return self._handle_join_room(session, request)
        elif action == 'leave_room':
            return self._handle_leave_room(session)
        elif action == 'start_game':
            return self._handle_start_game(session)
        elif action == 'check_game_status':
            return self._handle_check_game_status(session)
        elif action == 'end_game':
            return self._handle_end_game(session)
        elif action == 'submit_review':
            return self._handle_submit_review(session, request)
        elif action == 'logout':
            self._cleanup_session(session)
            session['logged_in'] = False
            return {'success': True}
        
        return {'success': False, 'error': 'Unknown action'}
    
    def _handle_register(self, request: dict) -> dict:
        """Register a new player account"""
        from server.database_server import hash_password
        
        username = request.get('username', '').strip()
        password = request.get('password', '').strip()
        
        if not username or not password:
            return {'success': False, 'error': 'Username and password required'}
        
        # Check if exists
        check = self._db_request({
            'action': 'find_one',
            'collection': 'User',
            'data': {'query': {'username': username, 'account_type': 'player'}}
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
                'account_type': 'player'
            }
        })
        
        if result.get('success'):
            return {'success': True, 'message': 'Player account created'}
        return {'success': False, 'error': 'Registration failed'}
    
    def _handle_login(self, protocol: Protocol, session: dict, request: dict) -> dict:
        """Login a player"""
        from server.database_server import hash_password
        
        username = request.get('username', '').strip()
        password = request.get('password', '').strip()
        
        if not username or not password:
            return {'success': False, 'error': 'Username and password required'}
        
        # Find user
        result = self._db_request({
            'action': 'find_one',
            'collection': 'User',
            'data': {'query': {'username': username, 'account_type': 'player'}}
        })
        
        if not result.get('success'):
            return {'success': False, 'error': 'Invalid username or password'}
        
        user = result['result']
        if user['password_hash'] != hash_password(password):
            return {'success': False, 'error': 'Invalid username or password'}
        
        # Check if already logged in
        with self.lock:
            if user['_id'] in self.sessions:
                return {'success': False, 'error': 'Account already logged in'}
        
        # Set session
        session['logged_in'] = True
        session['user_id'] = user['_id']
        session['username'] = user['username']
        
        with self.lock:
            self.sessions[user['_id']] = {
                'username': username,
                'protocol': protocol
            }
        
        return {'success': True, 'message': f'Welcome {username}!'}
    
    def _handle_list_games(self) -> dict:
        """List all active games"""
        result = self._db_request({
            'action': 'find',
            'collection': 'Game',
            'data': {'query': {'status': 'active'}}
        })
        
        if result.get('success'):
            return {'success': True, 'games': result['results']}
        return {'success': False, 'error': 'Failed to fetch games'}
    
    def _handle_game_info(self, request: dict) -> dict:
        """Get detailed game info"""
        game_name = request.get('game_name')
        
        if not game_name:
            return {'success': False, 'error': 'Game name required'}
        
        # Get game
        game_result = self._db_request({
            'action': 'find_one',
            'collection': 'Game',
            'data': {'query': {'name': game_name, 'status': 'active'}}
        })
        
        if not game_result.get('success'):
            return {'success': False, 'error': 'Game not found'}
        
        game = game_result['result']
        
        # Get reviews
        reviews_result = self._db_request({
            'action': 'find',
            'collection': 'Review',
            'data': {'query': {'game_id': game['_id']}}
        })
        
        reviews = reviews_result.get('results', []) if reviews_result.get('success') else []
        
        # Calculate average rating
        avg_rating = 0
        if reviews:
            avg_rating = sum(r['rating'] for r in reviews) / len(reviews)
        
        return {
            'success': True,
            'game': game,
            'reviews': reviews[:10],  # Return first 10 reviews
            'avg_rating': round(avg_rating, 1),
            'review_count': len(reviews)
        }
    
    def _handle_download_game(self, protocol: Protocol, request: dict) -> dict:
        """Send game files to player"""
        game_name = request.get('game_name')
        
        if not game_name:
            return {'success': False, 'error': 'Game name required'}
        
        # Get game
        game_result = self._db_request({
            'action': 'find_one',
            'collection': 'Game',
            'data': {'query': {'name': game_name, 'status': 'active'}}
        })
        
        if not game_result.get('success'):
            return {'success': False, 'error': 'Game not found'}
        
        game = game_result['result']
        version = game['latest_version']
        
        # Get version info
        version_result = self._db_request({
            'action': 'find_one',
            'collection': 'Version',
            'data': {'query': {'game_id': game['_id'], 'version': version}}
        })
        
        if not version_result.get('success'):
            return {'success': False, 'error': 'Version not found'}
        
        version_info = version_result['result']
        game_dir = os.path.join(self.upload_dir, version_info['file_path'])
        
        if not os.path.exists(game_dir):
            return {'success': False, 'error': 'Game files not found'}
        
        # Get all files
        files = get_game_files(game_dir)
        
        # Send initial response
        protocol.send_message({
            'success': True,
            'version': version,
            'message': f'Sending {len(files)} files...'
        })
        
        # Send file count
        protocol.send_message({'file_count': len(files)})
        
        # Send each file
        for rel_path in files:
            full_path = os.path.join(game_dir, rel_path)
            file_size = os.path.getsize(full_path)
            
            # Send file info
            protocol.send_message({
                'path': rel_path,
                'size': file_size
            })
            
            # Send file data
            if not protocol.send_file(full_path):
                return None
        
        return None  # Already sent response
    
    def _handle_list_rooms(self) -> dict:
        """List all active rooms"""
        with self.lock:
            rooms_list = []
            for room_id, room in self.rooms.items():
                rooms_list.append({
                    'room_id': room_id,
                    'game_name': room['game_name'],
                    'version': room.get('version', '1.0'),
                    'host': room['host_name'],
                    'players': len(room['players']),
                    'max_players': room['max_players'],
                    'status': room['status']
                })
            return {'success': True, 'rooms': rooms_list}
    
    def _handle_create_room(self, session: dict, request: dict) -> dict:
        """Create a new game room"""
        game_name = request.get('game_name')
        
        if not game_name:
            return {'success': False, 'error': 'Game name required'}
        
        # Remove from any existing rooms (enforce one room per player)
        with self.lock:
            self._remove_user_from_all_rooms(session['user_id'])
        
        # Get game info
        game_result = self._db_request({
            'action': 'find_one',
            'collection': 'Game',
            'data': {'query': {'name': game_name, 'status': 'active'}}
        })
        
        if not game_result.get('success'):
            return {'success': False, 'error': 'Game not found'}
        
        game = game_result['result']
        
        # Create room
        import uuid
        room_id = str(uuid.uuid4())[:8]
        
        with self.lock:
            self.rooms[room_id] = {
                'room_id': room_id,
                'game_name': game_name,
                'game_id': game['_id'],
                'version': game['latest_version'],
                'host_id': session['user_id'],
                'host_name': session['username'],
                'players': [session['user_id']],
                'max_players': game['max_players'],
                'status': 'waiting',
                'game_process': None,
                'game_port': None
            }
        
        return {
            'success': True,
            'room_id': room_id,
            'message': f'Room created for {game_name}',
            'is_host': True
        }
    
    def _handle_join_room(self, session: dict, request: dict) -> dict:
        """Join an existing room"""
        room_id = request.get('room_id')
        
        if not room_id:
            return {'success': False, 'error': 'Room ID required'}
        
        with self.lock:
            # Remove from any existing rooms (enforce one room per player)
            self._remove_user_from_all_rooms(session['user_id'])
            
            if room_id not in self.rooms:
                return {'success': False, 'error': 'Room not found'}
            
            room = self.rooms[room_id]
            
            if room['status'] != 'waiting':
                return {'success': False, 'error': 'Room is not accepting players'}
            
            if len(room['players']) >= room['max_players']:
                return {'success': False, 'error': 'Room is full'}
            
            if session['user_id'] in room['players']:
                return {'success': False, 'error': 'Already in room'}
            
            room['players'].append(session['user_id'])
        
        return {
            'success': True,
            'room_id': room_id,
            'game_name': room['game_name'],
            'is_host': False
        }
    
    def _handle_leave_room(self, session: dict) -> dict:
        """Leave current room"""
        with self.lock:
            for room_id, room in list(self.rooms.items()):
                if session['user_id'] in room['players']:
                    room['players'].remove(session['user_id'])
                    
                    if len(room['players']) == 0:
                        # Empty room, delete it
                        if room.get('game_process'):
                            room['game_process'].terminate()
                        
                        # Close log file if open
                        if room.get('game_log_file'):
                            try:
                                room['game_log_file'].close()
                            except:
                                pass
                        
                        del self.rooms[room_id]
                    elif session['user_id'] == room['host_id']:
                        # Host left, assign new host
                        room['host_id'] = room['players'][0]
                        room['host_name'] = self.sessions[room['players'][0]]['username']
                        
                        # Reset game status if game ended (prevents new host from being stuck)
                        if room['status'] == 'in_game':
                            process_ended = False
                            if room.get('game_process'):
                                try:
                                    if room['game_process'].poll() is not None:
                                        process_ended = True
                                except:
                                    process_ended = True
                            else:
                                process_ended = True
                            
                            if process_ended:
                                print(f"[Lobby] Room {room_id} game ended (host left), resetting to waiting")
                                
                                # Close log file if open
                                if room.get('game_log_file'):
                                    try:
                                        room['game_log_file'].close()
                                    except:
                                        pass
                                
                                room['status'] = 'waiting'
                                room['game_process'] = None
                                room['game_port'] = None
                                room['game_log_file'] = None
                    
                    return {'success': True, 'message': 'Left room'}
        
        return {'success': False, 'error': 'Not in any room'}
    
    def _handle_start_game(self, session: dict) -> dict:
        """Start the game (host only)"""
        with self.lock:
            room = None
            for r in self.rooms.values():
                if session['user_id'] in r['players']:
                    room = r
                    break
            
            if not room:
                return {'success': False, 'error': 'Not in any room'}
            
            if room['host_id'] != session['user_id']:
                return {'success': False, 'error': 'Only host can start game'}
            
            # Check if game ended but status not reset (prevents limbo)
            if room['status'] == 'in_game':
                process_ended = False
                if room.get('game_process'):
                    try:
                        # Fix 2: Retry poll up to 2 seconds to catch recent exits
                        for retry in range(10):  # 10 * 0.2s = 2s max
                            if room['game_process'].poll() is not None:
                                process_ended = True
                                break
                            if retry < 9:
                                time.sleep(0.2)
                    except:
                        # Process reference invalid, assume ended
                        process_ended = True
                else:
                    # No process reference, assume ended
                    process_ended = True
                
                if process_ended:
                    # Game ended, reset to waiting
                    print(f"[Lobby] Room {room['room_id']} game ended, resetting to waiting")
                    
                    # Close log file if open
                    if room.get('game_log_file'):
                        try:
                            room['game_log_file'].close()
                        except:
                            pass
                    
                    room['status'] = 'waiting'
                    room['game_process'] = None
                    room['game_port'] = None
                    room['game_log_file'] = None
                else:
                    # Still running after retries
                    return {'success': False, 'error': 'Game already started'}
            
            # Re-fetch latest version (float to latest)
            game_result = self._db_request({
                'action': 'find_one',
                'collection': 'Game',
                'data': {'query': {'_id': room['game_id'], 'status': 'active'}}
            })
            
            if not game_result.get('success'):
                return {'success': False, 'error': 'Game not found'}
            
            game = game_result['result']
            latest_version = game['latest_version']
            room['version'] = latest_version  # Update room to latest
            
            # Get game version info
            version_result = self._db_request({
                'action': 'find_one',
                'collection': 'Version',
                'data': {'query': {'game_id': room['game_id'], 'version': latest_version}}
            })
            
            if not version_result.get('success'):
                return {'success': False, 'error': 'Game version not found'}
            
            version_info = version_result['result']
            game_dir = os.path.join(self.upload_dir, version_info['file_path'])
            game_info_path = os.path.join(game_dir, 'game_info.json')
            
            with open(game_info_path, 'r', encoding='utf-8') as f:
                game_info = json.load(f)
            
            # Allocate port - find next available port
            try:
                game_port = self._find_available_port()
            except Exception as e:
                return {'success': False, 'error': f'No available ports: {e}'}
            
            # Build server command
            server_config = game_info['server']
            server_script = os.path.join(game_dir, server_config['entry_point'])
            
            command = [server_config.get('start_command', 'python')]
            command.append(server_script)
            
            # Add arguments
            if 'arguments' in server_config:
                for arg in server_config['arguments']:
                    arg = arg.replace('{PORT}', str(game_port))
                    arg = arg.replace('{NUM_PLAYERS}', str(len(room['players'])))
                    command.append(arg)
            
            # Start game server
            try:
                # Redirect stderr to log file for debugging
                log_file_path = os.path.join(self.logs_dir, f"game_{game_port}_{room.get('room_id', 'unknown')}.log")
                log_file = open(log_file_path, 'w')
                
                process = subprocess.Popen(
                    command,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,  # Merge stderr into stdout
                    stdin=subprocess.DEVNULL
                )
                
                # Early crash detection: wait briefly to see if process dies immediately
                time.sleep(0.3)
                exit_code = process.poll()
                
                if exit_code is not None:
                    # Game server crashed immediately
                    log_file.close()
                    print(f"[Lobby] Game server crashed immediately (exit code {exit_code})")
                    print(f"[Lobby] Check log: {log_file_path}")
                    
                    # Reset room to waiting
                    room['status'] = 'waiting'
                    room['game_process'] = None
                    room['game_port'] = None
                    
                    return {
                        'success': False, 
                        'error': f'Game server crashed on startup (exit {exit_code}). Check server logs.'
                    }
                
                # Game server started successfully
                room['game_process'] = process
                room['game_port'] = game_port
                room['game_log_file'] = log_file  # Keep file handle open
                room['status'] = 'in_game'
                
                print(f"[Lobby] Game server started on port {game_port}, logging to {log_file_path}")
                
                return {
                    'success': True,
                    'game_server': {
                        'host': self.advertise_host,
                        'port': game_port
                    },
                    'game_name': room['game_name'],
                    'version': room['version']
                }
            except Exception as e:
                return {'success': False, 'error': f'Failed to start server: {e}'}
    
    def _handle_check_game_status(self, session: dict) -> dict:
        """Check if game has been started by host (for non-host players)"""
        with self.lock:
            room = None
            for r in self.rooms.values():
                if session['user_id'] in r['players']:
                    room = r
                    break
            
            if not room:
                return {'success': True, 'game_started': False}
            
            # Fix 1A: Always include room identity and host info for migration support
            is_host = (session['user_id'] == room['host_id'])
            
            # Check if game process has ended and reset room status
            if room['status'] == 'in_game':
                process_ended = False
                if room.get('game_process'):
                    try:
                        if room['game_process'].poll() is not None:
                            process_ended = True
                    except:
                        process_ended = True
                else:
                    process_ended = True
                
                if process_ended:
                    # Game process has exited, reset room to waiting
                    print(f"[Lobby] Room {room.get('room_id', '?')} game ended (check_status), resetting to waiting")
                    
                    # Close log file if open
                    if room.get('game_log_file'):
                        try:
                            room['game_log_file'].close()
                        except:
                            pass
                    
                    room['status'] = 'waiting'
                    room['game_process'] = None
                    room['game_port'] = None
                    room['game_log_file'] = None
                    # Still return False since game just ended
                    return {'success': True, 'game_started': False}
                
                # Game is still running
                return {
                    'success': True,
                    'game_started': True,
                    'game_server': {
                        'host': self.advertise_host,
                        'port': room['game_port']
                    },
                    'game_name': room['game_name'],
                    'version': room['version'],
                    'room_id': room['room_id'],
                    'host_id': room['host_id'],
                    'host_name': room['host_name'],
                    'is_host': is_host,
                    'status': room['status']
                }
            else:
                # Still waiting
                return {
                    'success': True,
                    'game_started': False,
                    'room_id': room['room_id'],
                    'host_id': room['host_id'],
                    'host_name': room['host_name'],
                    'is_host': is_host,
                    'status': room['status']
                }
    
    def _handle_end_game(self, session: dict) -> dict:
        """Explicitly end game and reset room to waiting (Fix 1: best solution)"""
        with self.lock:
            room = None
            for r in self.rooms.values():
                if session['user_id'] in r['players']:
                    room = r
                    break
            
            if not room:
                return {'success': True, 'message': 'Not in any room'}
            
            if room['status'] != 'in_game':
                return {'success': True, 'message': 'Game not in progress'}
            
            # Reset room to waiting
            print(f"[Lobby] Room {room['room_id']} game ended (explicit end_game), resetting to waiting")
            
            # Terminate game process if still running
            if room.get('game_process'):
                try:
                    if room['game_process'].poll() is None:
                        room['game_process'].terminate()
                except:
                    pass
            
            # Close log file if open
            if room.get('game_log_file'):
                try:
                    room['game_log_file'].close()
                except:
                    pass
            
            room['status'] = 'waiting'
            room['game_process'] = None
            room['game_port'] = None
            room['game_log_file'] = None
            
            return {'success': True, 'message': 'Game ended, room reset to waiting'}
    
    def _handle_submit_review(self, session: dict, request: dict) -> dict:
        """Submit a game review"""
        game_name = request.get('game_name')
        rating = request.get('rating')
        comment = request.get('comment', '')
        
        if not game_name or rating is None:
            return {'success': False, 'error': 'Game name and rating required'}
        
        if not (1 <= rating <= 5):
            return {'success': False, 'error': 'Rating must be 1-5'}
        
        # Get game
        game_result = self._db_request({
            'action': 'find_one',
            'collection': 'Game',
            'data': {'query': {'name': game_name}}
        })
        
        if not game_result.get('success'):
            return {'success': False, 'error': 'Game not found'}
        
        game = game_result['result']
        
        # Save review
        result = self._db_request({
            'action': 'insert',
            'collection': 'Review',
            'data': {
                'game_id': game['_id'],
                'player_id': session['user_id'],
                'player_name': session['username'],
                'rating': rating,
                'comment': comment
            }
        })
        
        if result.get('success'):
            return {'success': True, 'message': 'Review submitted'}
        return {'success': False, 'error': 'Failed to submit review'}


if __name__ == '__main__':
    import sys
    # Usage: python lobby_server.py [advertise_host]
    # Example: python lobby_server.py linux4.cs.nycu.edu.tw
    advertise_host = sys.argv[1] if len(sys.argv) > 1 else 'linux4.cs.nycu.edu.tw'
    server = LobbyServer(advertise_host=advertise_host)
    server.start()
