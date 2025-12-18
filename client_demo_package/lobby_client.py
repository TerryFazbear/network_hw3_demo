"""
Lobby Client (Player) with State Management
Handles player authentication, game browsing, downloading, and playing
"""
import socket
import os
import sys
import subprocess
import json
from enum import Enum

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.protocol import Protocol


class ClientState(Enum):
    """Client states to prevent input buffering issues"""
    MENU = "menu"
    IN_LOBBY = "in_lobby"
    IN_ROOM = "in_room"
    WAITING_FOR_HOST = "waiting_for_host"
    CONNECTING = "connecting"
    IN_GAME = "in_game"


class LobbyClient:
    def __init__(self, host='linux4.cs.nycu.edu.tw', port=10002):
        self.host = host
        self.port = port
        self.protocol = None
        self.logged_in = False
        self.username = None
        self.downloads_dir = None
        
        # State management
        self.state = ClientState.MENU
        self.current_room = None
        self.current_game_name = None
        self.current_game_version = None
        self.is_host = False
        self.game_process = None
        
        # For error rate limiting
        self.last_error_time = 0
    
    def connect(self):
        """Connect to lobby server"""
        try:
            print(f"\n🔌 Connecting to lobby {self.host}:{self.port}...")
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((self.host, self.port))
            self.protocol = Protocol(sock)
            print(f"✓ Connected to {self.host}:{self.port}\n")
            return True
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            return False
    
    def send_request(self, request: dict) -> dict:
        """Send request and get response"""
        if not self.protocol or self.protocol.closed:
            return {'success': False, 'error': 'Not connected'}
        
        if not self.protocol.send_message(request):
            return {'success': False, 'error': 'Failed to send request'}
        
        response = self.protocol.receive_message()
        if not response:
            return {'success': False, 'error': 'No response'}
        
        return response
    
    def register(self):
        """Register new player account"""
        print("\n=== Player Registration ===")
        username = input("Username: ").strip()
        password = input("Password: ").strip()
        
        if not username or not password:
            print("❌ Username and password required")
            return
        
        response = self.send_request({
            'action': 'register',
            'username': username,
            'password': password
        })
        
        if response.get('success'):
            print(f"✓ {response.get('message', 'Registration successful')}")
        else:
            print(f"❌ {response.get('error', 'Registration failed')}")
    
    def login(self):
        """Login to player account"""
        print("\n=== Player Login ===")
        username = input("Username: ").strip()
        password = input("Password: ").strip()
        
        if not username or not password:
            print("❌ Username and password required")
            return
        
        response = self.send_request({
            'action': 'login',
            'username': username,
            'password': password
        })
        
        if response.get('success'):
            self.logged_in = True
            self.username = username
            # Use absolute path to avoid duplication
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.downloads_dir = os.path.join(base_dir, 'player', 'downloads', username)
            os.makedirs(self.downloads_dir, exist_ok=True)
            self.state = ClientState.IN_LOBBY
            print(f"✓ {response.get('message', 'Login successful')}")
        else:
            print(f"❌ {response.get('error', 'Login failed')}")
    
    def list_games(self):
        """Browse available games"""
        response = self.send_request({'action': 'list_games'})
        
        if not response.get('success'):
            print(f"❌ {response.get('error', 'Failed to fetch games')}")
            return
        
        games = response.get('games', [])
        
        if not games:
            print("\n📦 No games available")
            return
        
        print("\n=== Available Games ===")
        for i, game in enumerate(games, 1):
            print(f"{i}. {game['name']} (v{game['latest_version']})")
            print(f"   By: {game.get('developer_name', 'Unknown')}")
            print(f"   {game.get('description', 'No description')}")
            print(f"   Players: {game.get('min_players', '?')}-{game.get('max_players', '?')}")
            print()
    
    def game_details(self):
        """View detailed game information"""
        response = self.send_request({'action': 'list_games'})
        
        if not response.get('success'):
            print("❌ Failed to fetch games")
            return
        
        games = response.get('games', [])
        if not games:
            print("❌ No games available")
            return
        
        print("\nSelect a game:")
        for i, game in enumerate(games, 1):
            print(f"{i}. {game['name']}")
        
        try:
            choice = int(input("\nGame number (0 to cancel): ").strip())
            if choice == 0:
                return
            if choice < 1 or choice > len(games):
                print("❌ Invalid choice")
                return
            
            game_name = games[choice - 1]['name']
        except ValueError:
            print("❌ Invalid input")
            return
        
        # Get detailed info
        response = self.send_request({
            'action': 'game_info',
            'game_name': game_name
        })
        
        if not response.get('success'):
            print(f"❌ {response.get('error')}")
            return
        
        game = response['game']
        reviews = response.get('reviews', [])
        avg_rating = response.get('avg_rating', 0)
        review_count = response.get('review_count', 0)
        
        print(f"\n=== {game['name']} ===")
        print(f"Version: {game['latest_version']}")
        print(f"Developer: {game.get('developer_name', 'Unknown')}")
        print(f"Description: {game.get('description', 'N/A')}")
        print(f"Players: {game.get('min_players', '?')}-{game.get('max_players', '?')}")
        print(f"Rating: {'⭐' * int(avg_rating)} ({avg_rating}/5.0 from {review_count} reviews)")
        
        if reviews:
            print("\nRecent Reviews:")
            for review in reviews[:3]:
                print(f"  {'⭐' * review['rating']} - {review.get('player_name', 'Anonymous')}")
                if review.get('comment'):
                    print(f"  \"{review['comment']}\"")
                print()
    
    def download_game(self):
        """Download a game"""
        response = self.send_request({'action': 'list_games'})
        
        if not response.get('success'):
            print("❌ Failed to fetch games")
            return
        
        games = response.get('games', [])
        if not games:
            print("❌ No games available")
            return
        
        print("\nSelect a game to download:")
        for i, game in enumerate(games, 1):
            print(f"{i}. {game['name']} (v{game['latest_version']})")
        
        try:
            choice = int(input("\nGame number (0 to cancel): ").strip())
            if choice == 0:
                return
            if choice < 1 or choice > len(games):
                print("❌ Invalid choice")
                return
            
            game_name = games[choice - 1]['name']
        except ValueError:
            print("❌ Invalid input")
            return
        
        print(f"\n📥 Downloading {game_name}...")
        
        # Send download request
        response = self.send_request({
            'action': 'download_game',
            'game_name': game_name
        })
        
        if not response.get('success'):
            print(f"❌ {response.get('error', 'Download failed')}")
            return
        
        version = response['version']
        
        # Receive file count
        file_msg = self.protocol.receive_message()
        if not file_msg:
            print("❌ Failed to receive file count")
            return
        
        file_count = file_msg.get('file_count', 0)
        print(f"   Receiving {file_count} files...")
        
        # Create game directory
        game_dir = os.path.join(self.downloads_dir, f"{game_name}_{version}")
        os.makedirs(game_dir, exist_ok=True)
        
        # Receive files
        for i in range(file_count):
            file_info = self.protocol.receive_message()
            if not file_info:
                print("❌ Failed to receive file info")
                return
            
            rel_path = file_info['path']
            file_path = os.path.join(game_dir, rel_path)
            
            # Create directory
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # Receive file
            if not self.protocol.receive_file(file_path):
                print(f"❌ Failed to receive {rel_path}")
                return
            
            print(f"   [{i+1}/{file_count}] {rel_path}")
        
        print(f"\n✓ Downloaded {game_name} v{version}")
    
    def _receive_game_files(self, game_name: str, version: str):
        """Helper method to receive game files from server"""
        # Receive file count
        file_msg = self.protocol.receive_message()
        if not file_msg:
            print("❌ Failed to receive file count")
            return False
        
        file_count = file_msg.get('file_count', 0)
        print(f"   Receiving {file_count} files...")
        
        # Create game directory
        game_dir = os.path.join(self.downloads_dir, f"{game_name}_{version}")
        os.makedirs(game_dir, exist_ok=True)
        
        # Receive files
        for i in range(file_count):
            file_info = self.protocol.receive_message()
            if not file_info:
                print("❌ Failed to receive file info")
                return False
            
            rel_path = file_info['path']
            file_path = os.path.join(game_dir, rel_path)
            
            # Create directory
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # Receive file
            if not self.protocol.receive_file(file_path):
                print(f"❌ Failed to receive {rel_path}")
                return False
            
            print(f"   [{i+1}/{file_count}] {rel_path}")
        
        print(f"\n✓ Downloaded {game_name} v{version}")
        return True
    
    def list_rooms(self):
        """List active rooms"""
        response = self.send_request({'action': 'list_rooms'})
        
        if not response.get('success'):
            print(f"❌ {response.get('error')}")
            return
        
        rooms = response.get('rooms', [])
        
        if not rooms:
            print("\n🚪 No active rooms")
            return
        
        print("\n=== Active Rooms ===")
        for i, room in enumerate(rooms, 1):
            status = "🟢" if room['status'] == 'waiting' else "🔴"
            version = room.get('version', '?')
            print(f"{status} {i}. {room['game_name']} v{version} - Host: {room['host']}")
            print(f"   Room ID: {room['room_id']}")
            print(f"   Players: {room['players']}/{room['max_players']}")
            print()
    
    def create_room(self):
        """Create a new room"""
        response = self.send_request({'action': 'list_games'})
        
        if not response.get('success'):
            print("❌ Failed to fetch games")
            return
        
        games = response.get('games', [])
        if not games:
            print("❌ No games available")
            return
        
        print("\nSelect a game:")
        for i, game in enumerate(games, 1):
            print(f"{i}. {game['name']}")
        
        try:
            choice = int(input("\nGame number (0 to cancel): ").strip())
            if choice == 0:
                return
            if choice < 1 or choice > len(games):
                print("❌ Invalid choice")
                return
            
            game_name = games[choice - 1]['name']
            game_version = games[choice - 1]['latest_version']
        except ValueError:
            print("❌ Invalid input")
            return
        
        # Store game info BEFORE creating room
        self.current_game_name = game_name
        self.current_game_version = game_version
        
        # Check if game is downloaded
        game_dir = os.path.join(self.downloads_dir, f"{game_name}_{game_version}")
        if not os.path.exists(game_dir):
            print(f"\n⚠️  Game not downloaded. Download first? (y/n): ", end='')
            if input().strip().lower() == 'y':
                # Trigger download
                response = self.send_request({
                    'action': 'download_game',
                    'game_name': game_name
                })
                
                if not response.get('success'):
                    print(f"❌ Download failed")
                    return
                
                # Receive files (same as download_game)
                file_msg = self.protocol.receive_message()
                if not file_msg:
                    return
                
                file_count = file_msg.get('file_count', 0)
                os.makedirs(game_dir, exist_ok=True)
                
                for i in range(file_count):
                    file_info = self.protocol.receive_message()
                    if not file_info:
                        return
                    
                    rel_path = file_info['path']
                    file_path = os.path.join(game_dir, rel_path)
                    os.makedirs(os.path.dirname(file_path), exist_ok=True)
                    
                    if not self.protocol.receive_file(file_path):
                        return
                
                print("✓ Download complete")
            else:
                print("❌ Cannot create room without game")
                return
        
        # Create room
        response = self.send_request({
            'action': 'create_room',
            'game_name': game_name
        })
        
        if response.get('success'):
            self.current_room = response['room_id']
            self.is_host = response.get('is_host', False)
            self.state = ClientState.IN_ROOM
            print(f"\n✓ Room created: {self.current_room}")
            print("You are the host")
        else:
            print(f"❌ {response.get('error', 'Failed to create room')}")
    
    def join_room(self):
        """Join an existing room"""
        response = self.send_request({'action': 'list_rooms'})
        
        if not response.get('success'):
            print("❌ Failed to fetch rooms")
            return
        
        rooms = response.get('rooms', [])
        if not rooms:
            print("❌ No rooms available")
            return
        
        print("\nSelect a room:")
        for i, room in enumerate(rooms, 1):
            status = "Open" if room['status'] == 'waiting' else "In Game"
            version = room.get('version', '?')
            print(f"{i}. {room['game_name']} v{version} - {room['host']} ({room['players']}/{room['max_players']}) [{status}]")
        
        try:
            choice = int(input("\nRoom number (0 to cancel): ").strip())
            if choice == 0:
                return
            if choice < 1 or choice > len(rooms):
                print("❌ Invalid choice")
                return
            
            room = rooms[choice - 1]
        except ValueError:
            print("❌ Invalid input")
            return
        
        # Join room
        response = self.send_request({
            'action': 'join_room',
            'room_id': room['room_id']
        })
        
        if response.get('success'):
            self.current_room = room['room_id']
            self.current_game_name = room['game_name']
            self.current_game_version = room.get('version', '1.0')
            self.is_host = False
            self.state = ClientState.WAITING_FOR_HOST
            print(f"\n✓ Joined room {room['room_id']}")
            print("Waiting for host to start game...")
        else:
            print(f"❌ {response.get('error', 'Failed to join room')}")
    
    def room_menu(self):
        """Room menu (for host)"""
        while self.state == ClientState.IN_ROOM:
            print("\n" + "="*50)
            print(f"🚪 Room: {self.current_room}")
            print("="*50)
            print("\n1. Start Game")
            print("2. Leave Room")
            print("="*50)
            
            choice = input("\nSelect option (1-2): ").strip()
            
            if choice == '1':
                self.start_game()
            elif choice == '2':
                self.leave_room()
                break
            else:
                print("❌ Invalid option")
    
    def waiting_menu(self):
        """Waiting menu (for non-host)"""
        print("\n" + "="*50)
        print(f"🚺 Room: {self.current_room}")
        print("="*50)
        print("\nWaiting for host to start game...")
        print("Type 'leave' to leave room, or wait for host to start...")
        print("="*50)
        
        import select
        import time
        
        # Poll for game start while allowing user to leave
        while self.state == ClientState.WAITING_FOR_HOST:
            # Check if host started the game (poll server)
            try:
                response = self.send_request({'action': 'check_game_status'})
                
                # Fix 1B: Check if we became host (host migration)
                if response.get('is_host'):
                    print("\n👑 You are now the host! (Previous host left)")
                    self.is_host = True
                    self.state = ClientState.IN_ROOM
                    return  # Return to room_menu()
                
            except Exception as e:
                # Fix 2A: Rate-limited error printing
                current_time = time.time()
                if current_time - self.last_error_time > 5.0:
                    print(f"\n⚠️  Poll error: {e}")
                    self.last_error_time = current_time
                time.sleep(2)
                continue
            
            if not response.get('success'):
                # Fix 2A: Rate-limited error printing
                current_time = time.time()
                if current_time - self.last_error_time > 5.0:
                    print(f"\n⚠️  Server error: {response.get('error', 'Unknown')}")
                    self.last_error_time = current_time
                time.sleep(2)
                continue
            
            if response.get('game_started'):
                # Host started the game!
                game_server = response['game_server']
                game_name = response['game_name']
                version = response['version']
                
                print(f"\n🎮 Host started the game!")
                print(f"✓ Game server at {game_server['host']}:{game_server['port']}")
                
                # Check if we have the game downloaded
                game_dir = os.path.join(self.downloads_dir, f"{game_name}_{version}")
                if not os.path.exists(game_dir):
                    print(f"\n⚠️  You don't have {game_name} v{version} installed.")
                    choice = input("Download now? (y/n): ").strip().lower()
                    if choice != 'y':
                        print("❌ Cannot join without game. Leaving room...")
                        self.leave_room()
                        return
                    
                    # Download the game
                    print(f"\n📥 Downloading {game_name} v{version}...")
                    download_response = self.send_request({
                        'action': 'download_game',
                        'game_name': game_name
                    })
                    
                    if not download_response.get('success'):
                        print(f"❌ Download failed: {download_response.get('error')}")
                        self.leave_room()
                        return
                    
                    # Receive files
                    self._receive_game_files(game_name, version)
                
                print(f"🎮 Launching {game_name} client...\n")
                
                # Launch game client and wait for it to finish
                self.launch_game_client(game_name, version, game_server['host'], game_server['port'])
                
                # After game ends, leave room and return to lobby
                # This prevents stuck state and ensures clean server-side cleanup
                self.leave_room()
                return
            
            # Check for user input (non-blocking on Unix, polling on Windows)
            if sys.platform == 'win32':
                # Windows: use msvcrt
                import msvcrt
                if msvcrt.kbhit():
                    user_input = input().strip().lower()
                    if user_input == 'leave':
                        self.leave_room()
                        break
            else:
                # Unix: use select
                ready, _, _ = select.select([sys.stdin], [], [], 0.5)
                if ready:
                    user_input = sys.stdin.readline().strip().lower()
                    if user_input == 'leave':
                        self.leave_room()
                        break
            
            # Wait before next poll
            time.sleep(1)
    
    def _stop_game_process(self):
        """Stop the running game process if any"""
        if self.game_process and self.game_process.poll() is None:
            print("\n🛑 Stopping game process...")
            self.game_process.terminate()
            try:
                self.game_process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                print("⚠ Forcefully killing game process...")
                self.game_process.kill()
        self.game_process = None
    
    def start_game(self):
        """Start the game (host only)"""
        if not self.is_host:
            print("❌ Only host can start the game")
            return
        
        print("\n🎮 Preparing to start game...")
        
        # Debug: Check if we have the game name
        if not self.current_game_name:
            print("❌ Error: No game name stored. Please leave and create room again.")
            return
        
        # CRITICAL: Check if we have the game BEFORE calling server start_game
        # Re-fetch latest version in case developer updated
        game_info_response = self.send_request({'action': 'game_info', 'game_name': self.current_game_name})
        if not game_info_response.get('success'):
            print(f"❌ Failed to get game info: {game_info_response.get('error', 'Unknown error')}")
            print(f"   Game name: {self.current_game_name}")
            return
        
        latest_version = game_info_response['game']['latest_version']
        self.current_game_version = latest_version  # Update to latest
        
        game_dir = os.path.join(self.downloads_dir, f"{self.current_game_name}_{latest_version}")
        if not os.path.exists(game_dir):
            print(f"\n⚠️  You don't have {self.current_game_name} v{latest_version} installed.")
            choice = input("Download now? (y/n): ").strip().lower()
            if choice != 'y':
                print("❌ Cannot start without game. Staying in room...")
                return
            
            # Download the game
            print(f"\n📥 Downloading {self.current_game_name} v{latest_version}...")
            download_response = self.send_request({
                'action': 'download_game',
                'game_name': self.current_game_name
            })
            
            if not download_response.get('success'):
                print(f"❌ Download failed: {download_response.get('error')}")
                return
            
            # Receive files
            if not self._receive_game_files(self.current_game_name, latest_version):
                print("❌ Download failed")
                return
        
        # NOW send start_game to server (only after we have the game)
        self.state = ClientState.CONNECTING
        response = self.send_request({'action': 'start_game'})
        
        if not response.get('success'):
            print(f"❌ {response.get('error', 'Failed to start game')}")
            self.state = ClientState.IN_ROOM
            return
        
        # Get game server info
        game_server = response['game_server']
        game_name = response['game_name']
        version = response['version']
        
        print(f"✓ Game server started at {game_server['host']}:{game_server['port']}")
        print(f"🎮 Launching {game_name} client...")
        
        # Launch game client (we already have it downloaded)
        self.launch_game_client(game_name, version, game_server['host'], game_server['port'])
    
    def launch_game_client(self, game_name: str, version: str, host: str, port: int):
        """Launch the game client process"""
        game_dir = os.path.join(self.downloads_dir, f"{game_name}_{version}")
        game_info_path = os.path.join(game_dir, 'game_info.json')
        
        if not os.path.exists(game_info_path):
            print(f"❌ Game not found: {game_dir}")
            return
        
        # Read game info
        with open(game_info_path, 'r', encoding='utf-8') as f:
            game_info = json.load(f)
        
        client_config = game_info['client']
        entry_point = os.path.join(game_dir, client_config['entry_point'])
        
        # Build command
        command = [client_config.get('start_command', 'python')]
        command.append(entry_point)
        
        # Add arguments
        if 'arguments' in client_config:
            for arg in client_config['arguments']:
                arg = arg.replace('{HOST}', host)
                arg = arg.replace('{PORT}', str(port))
                arg = arg.replace('{USERNAME}', self.username)
                command.append(arg)
        
        # Launch process
        try:
            self.state = ClientState.IN_GAME
            
            # Fix 2B: Track start time for immediate-exit detection
            import time
            start_time = time.time()
            
            self.game_process = subprocess.Popen(command, cwd=game_dir)
            print(f"✓ Game client launched (PID: {self.game_process.pid})")
            print("\n" + "="*60)
            print("   GAME STARTED - Terminal control passed to game")
            print("="*60 + "\n")
            
            # Block and wait for game to exit (give terminal fully to the game)
            exit_code = self.game_process.wait()
            
            # Fix 2B: Detect immediate exit (connection failure)
            runtime = time.time() - start_time
            
            # Game ended - clean up
            self.game_process = None
            self.state = ClientState.IN_ROOM
            
            if runtime < 1.0:
                print("\n" + "="*60)
                print("⚠️  Game client exited immediately (<1s)")
                print("    Likely cause: Connection failed (host/port unreachable)")
                print(f"    Tried to connect to: {host}:{port}")
                print("="*60)
            else:
                print("\n" + "="*60)
                print(f"✓ Game exited (code={exit_code}, runtime={runtime:.1f}s). Returning to room menu...")
                print("="*60)
            
            # Fix 1: Tell server game ended so room becomes immediately reusable
            try:
                self.send_request({'action': 'end_game'})
            except:
                pass  # Best effort, don't block on errors
        except Exception as e:
            print(f"❌ Failed to launch game: {e}")
            self.game_process = None
            self.state = ClientState.IN_ROOM
    
    def leave_room(self):
        """Leave current room"""
        # Stop game process if running
        self._stop_game_process()
        
        response = self.send_request({'action': 'leave_room'})
        
        if response.get('success'):
            print("✓ Left room")
            self.current_room = None
            self.current_game_name = None
            self.current_game_version = None
            self.is_host = False
            self.state = ClientState.IN_LOBBY
        else:
            print(f"❌ {response.get('error', 'Failed to leave room')}")
    
    def submit_review(self):
        """Submit a review for a game"""
        response = self.send_request({'action': 'list_games'})
        
        if not response.get('success'):
            print("❌ Failed to fetch games")
            return
        
        games = response.get('games', [])
        if not games:
            print("❌ No games available")
            return
        
        print("\nSelect a game to review:")
        for i, game in enumerate(games, 1):
            print(f"{i}. {game['name']}")
        
        try:
            choice = int(input("\nGame number (0 to cancel): ").strip())
            if choice == 0:
                return
            if choice < 1 or choice > len(games):
                print("❌ Invalid choice")
                return
            
            game_name = games[choice - 1]['name']
        except ValueError:
            print("❌ Invalid input")
            return
        
        # Get rating
        try:
            rating = int(input("Rating (1-5 stars): ").strip())
            if rating < 1 or rating > 5:
                print("❌ Rating must be 1-5")
                return
        except ValueError:
            print("❌ Invalid rating")
            return
        
        # Get comment
        comment = input("Comment (optional): ").strip()
        
        # Submit
        response = self.send_request({
            'action': 'submit_review',
            'game_name': game_name,
            'rating': rating,
            'comment': comment
        })
        
        if response.get('success'):
            print(f"✓ {response.get('message', 'Review submitted')}")
        else:
            print(f"❌ {response.get('error', 'Failed to submit review')}")
    
    def main_menu(self):
        """Main lobby menu"""
        while self.logged_in and self.state == ClientState.IN_LOBBY:
            print("\n" + "="*50)
            print("🎮 Game Store Lobby")
            print("="*50)
            print(f"Player: {self.username}")
            print("\n1. Browse Games")
            print("2. Game Details & Reviews")
            print("3. Download Game")
            print("4. Create Room")
            print("5. Join Room")
            print("6. List Rooms")
            print("7. Submit Review")
            print("8. Logout")
            print("="*50)
            
            choice = input("\nSelect option (1-8): ").strip()
            
            if choice == '1':
                self.list_games()
            elif choice == '2':
                self.game_details()
            elif choice == '3':
                self.download_game()
            elif choice == '4':
                self.create_room()
                if self.state == ClientState.IN_ROOM:
                    self.room_menu()
            elif choice == '5':
                self.join_room()
                if self.state == ClientState.WAITING_FOR_HOST:
                    self.waiting_menu()
            elif choice == '6':
                self.list_rooms()
            elif choice == '7':
                self.submit_review()
            elif choice == '8':
                self._stop_game_process()  # Clean up any running game
                self.send_request({'action': 'logout'})
                self.logged_in = False
                self.state = ClientState.MENU
                print("✓ Logged out")
            else:
                print("❌ Invalid option")
            
            if self.state == ClientState.IN_LOBBY:
                input("\nPress Enter to continue...")
    
    def run(self):
        """Run the client"""
        print("="*50)
        print("🎮 Game Store - Player Lobby")
        print("="*50)
        
        if not self.connect():
            return
        
        print("✓ Connected to lobby server")
        
        try:
            while True:
                if self.logged_in:
                    self.main_menu()
                else:
                    print("\n" + "="*50)
                    print("1. Login")
                    print("2. Register")
                    print("3. Exit")
                    print("="*50)
                    
                    choice = input("\nSelect option (1-3): ").strip()
                    
                    if choice == '1':
                        self.login()
                    elif choice == '2':
                        self.register()
                    elif choice == '3':
                        self._stop_game_process()  # Clean up any running game
                        print("\nGoodbye!")
                        break
                    else:
                        print("❌ Invalid option")
        except KeyboardInterrupt:
            print("\n\nGoodbye!")
        finally:
            self._stop_game_process()  # Always clean up game process
            if self.protocol:
                self.protocol.close()


if __name__ == '__main__':
    host = sys.argv[1] if len(sys.argv) > 1 else 'linux4.cs.nycu.edu.tw'
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 10002
    
    client = LobbyClient(host, port)
    client.run()
