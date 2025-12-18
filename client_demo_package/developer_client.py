"""
Developer Client
Allows developers to upload, update, and manage games
"""
import socket
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.protocol import Protocol
from common.validate_game import validate_game_package, get_game_files


class DeveloperClient:
    def __init__(self, host='linux4.cs.nycu.edu.tw', port=10003):
        self.host = host
        self.port = port
        self.protocol = None
        self.logged_in = False
        self.username = None
    
    def connect(self):
        """Connect to developer server"""
        try:
            print(f"\n🔌 Connecting to developer server {self.host}:{self.port}...")
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((self.host, self.port))
            self.protocol = Protocol(sock)
            print(f"✓ Connected to {self.host}:{self.port}\n")
            return True
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            return False
    
    def send_request(self, request: dict) -> dict:
        """Send a request and get response"""
        if not self.protocol or self.protocol.closed:
            return {'success': False, 'error': 'Not connected'}
        
        if not self.protocol.send_message(request):
            return {'success': False, 'error': 'Failed to send request'}
        
        response = self.protocol.receive_message()
        if not response:
            return {'success': False, 'error': 'No response from server'}
        
        return response
    
    def register(self):
        """Register a new developer account"""
        print("\n=== Developer Registration ===")
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
        """Login to developer account"""
        print("\n=== Developer Login ===")
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
            print(f"✓ {response.get('message', 'Login successful')}")
        else:
            print(f"❌ {response.get('error', 'Login failed')}")
    
    def my_games(self):
        """List my games"""
        response = self.send_request({'action': 'my_games'})
        
        if not response.get('success'):
            print(f"❌ {response.get('error', 'Failed to fetch games')}")
            return
        
        games = response.get('games', [])
        
        if not games:
            print("\n📦 You have no games uploaded yet")
            return
        
        print("\n=== Your Games ===")
        for i, game in enumerate(games, 1):
            status_icon = "✓" if game.get('status') == 'active' else "✗"
            print(f"{i}. {status_icon} {game['name']} (v{game['latest_version']})")
            print(f"   {game.get('description', 'No description')}")
            print(f"   Status: {game.get('status', 'unknown')}")
            print()
    
    def upload_game(self):
        """Upload a new game"""
        print("\n=== Upload New Game ===")
        
        # Get games directory (relative to developer_client.py)
        client_dir = os.path.dirname(os.path.abspath(__file__))
        games_dir = os.path.join(client_dir, 'games')
        
        if not os.path.exists(games_dir):
            print("❌ Games directory not found (developer/games/)")
            return
        
        # List available games
        game_folders = [d for d in os.listdir(games_dir) 
                       if os.path.isdir(os.path.join(games_dir, d)) and not d.startswith('.')]
        
        if not game_folders:
            print("❌ No games found in developer/games/")
            print("   Create a game folder with game_info.json first")
            return
        
        print("\nAvailable games in developer/games/:")
        for i, folder in enumerate(game_folders, 1):
            game_info_path = os.path.join(games_dir, folder, 'game_info.json')
            if os.path.exists(game_info_path):
                try:
                    with open(game_info_path, 'r', encoding='utf-8') as f:
                        info = json.load(f)
                    print(f"{i}. {folder}/ - {info.get('name', 'N/A')} v{info.get('version', 'N/A')}")
                except:
                    print(f"{i}. {folder}/ - (invalid game_info.json)")
            else:
                print(f"{i}. {folder}/ - (no game_info.json)")
        
        # Select game
        try:
            choice = int(input("\nSelect game folder (number): ").strip())
            if choice < 1 or choice > len(game_folders):
                print("❌ Invalid choice")
                return
            game_dir = os.path.join(games_dir, game_folders[choice - 1])
        except ValueError:
            print("❌ Invalid input")
            return
        
        # Validate game package
        success, error, game_info = validate_game_package(game_dir)
        if not success:
            print(f"❌ Invalid game package: {error}")
            return
        
        # Display game info
        print(f"\n📦 Game: {game_info['name']}")
        print(f"   Version: {game_info['version']}")
        print(f"   Description: {game_info.get('description', 'N/A')}")
        print(f"   Players: {game_info.get('min_players', 'N/A')}-{game_info.get('max_players', 'N/A')}")
        
        confirm = input("\nProceed with upload? (y/n): ").strip().lower()
        if confirm != 'y':
            print("Upload cancelled")
            return
        
        # Send upload request
        response = self.send_request({
            'action': 'upload_game',
            'game_name': game_info['name']
        })
        
        if not response.get('success'):
            print(f"❌ {response.get('error', 'Upload failed')}")
            return
        
        # Get files to upload
        files = get_game_files(game_dir)
        print(f"\n📤 Uploading {len(files)} files...")
        
        # Send file count
        self.protocol.send_message({'file_count': len(files)})
        
        # Send each file
        for i, rel_path in enumerate(files, 1):
            full_path = os.path.join(game_dir, rel_path)
            file_size = os.path.getsize(full_path)
            
            print(f"   [{i}/{len(files)}] {rel_path} ({file_size} bytes)")
            
            # Send file info
            self.protocol.send_message({
                'path': rel_path,
                'size': file_size
            })
            
            # Send file data
            if not self.protocol.send_file(full_path):
                print("❌ Failed to upload file")
                return
        
        # Get final response
        final_response = self.protocol.receive_message()
        if final_response and final_response.get('success'):
            print(f"\n✓ {final_response.get('message', 'Upload successful')}")
        else:
            print(f"❌ {final_response.get('error', 'Upload failed')}")
    
    def update_game(self):
        """Update an existing game"""
        print("\n=== Update Game ===")
        
        # First, show current games
        response = self.send_request({'action': 'my_games'})
        if not response.get('success'):
            print("❌ Failed to fetch games")
            return
        
        games = response.get('games', [])
        if not games:
            print("❌ You have no games to update")
            return
        
        print("\nYour games:")
        for i, game in enumerate(games, 1):
            print(f"{i}. {game['name']} (v{game['latest_version']})")
        
        # Select game
        try:
            choice = int(input("\nSelect game (number): ").strip())
            if choice < 1 or choice > len(games):
                print("❌ Invalid choice")
                return
            game_name = games[choice - 1]['name']
        except ValueError:
            print("❌ Invalid input")
            return
        
        # Get games directory
        client_dir = os.path.dirname(os.path.abspath(__file__))
        games_dir = os.path.join(client_dir, 'games')
        
        if not os.path.exists(games_dir):
            print("❌ Games directory not found (developer/games/)")
            return
        
        # List available game versions
        game_folders = [d for d in os.listdir(games_dir) 
                       if os.path.isdir(os.path.join(games_dir, d)) and not d.startswith('.')]
        
        if not game_folders:
            print("❌ No games found in developer/games/")
            return
        
        print(f"\nSelect new version for '{game_name}' from developer/games/:")
        for i, folder in enumerate(game_folders, 1):
            game_info_path = os.path.join(games_dir, folder, 'game_info.json')
            if os.path.exists(game_info_path):
                try:
                    with open(game_info_path, 'r', encoding='utf-8') as f:
                        info = json.load(f)
                    print(f"{i}. {folder}/ - {info.get('name', 'N/A')} v{info.get('version', 'N/A')}")
                except:
                    print(f"{i}. {folder}/ - (invalid game_info.json)")
            else:
                print(f"{i}. {folder}/ - (no game_info.json)")
        
        # Select version
        try:
            choice = int(input("\nSelect game folder (number): ").strip())
            if choice < 1 or choice > len(game_folders):
                print("❌ Invalid choice")
                return
            game_dir = os.path.join(games_dir, game_folders[choice - 1])
        except ValueError:
            print("❌ Invalid input")
            return
        
        # Validate
        success, error, game_info = validate_game_package(game_dir)
        if not success:
            print(f"❌ Invalid game package: {error}")
            return
        
        print(f"\n📦 Updating to version {game_info['version']}")
        
        # Send update request
        response = self.send_request({
            'action': 'update_game',
            'game_name': game_name
        })
        
        if not response.get('success'):
            print(f"❌ {response.get('error', 'Update failed')}")
            return
        
        # Upload files
        files = get_game_files(game_dir)
        print(f"\n📤 Uploading {len(files)} files...")
        
        self.protocol.send_message({'file_count': len(files)})
        
        for i, rel_path in enumerate(files, 1):
            full_path = os.path.join(game_dir, rel_path)
            file_size = os.path.getsize(full_path)
            
            print(f"   [{i}/{len(files)}] {rel_path}")
            
            self.protocol.send_message({
                'path': rel_path,
                'size': file_size
            })
            
            if not self.protocol.send_file(full_path):
                print("❌ Failed to upload file")
                return
        
        # Get final response
        final_response = self.protocol.receive_message()
        if final_response and final_response.get('success'):
            print(f"\n✓ {final_response.get('message', 'Update successful')}")
        else:
            print(f"❌ {final_response.get('error', 'Update failed')}")
    
    def remove_game(self):
        """Remove a game"""
        print("\n=== Remove Game ===")
        
        # Show games
        response = self.send_request({'action': 'my_games'})
        if not response.get('success'):
            print("❌ Failed to fetch games")
            return
        
        games = response.get('games', [])
        if not games:
            print("❌ You have no games to remove")
            return
        
        print("\nYour games:")
        for i, game in enumerate(games, 1):
            print(f"{i}. {game['name']} (v{game['latest_version']})")
        
        # Select game
        try:
            choice = int(input("\nSelect game (number): ").strip())
            if choice < 1 or choice > len(games):
                print("❌ Invalid choice")
                return
            game_name = games[choice - 1]['name']
        except ValueError:
            print("❌ Invalid input")
            return
        
        confirm = input(f"\n⚠️  Remove '{game_name}' from store? (y/n): ").strip().lower()
        if confirm != 'y':
            print("Cancelled")
            return
        
        response = self.send_request({
            'action': 'remove_game',
            'game_name': game_name
        })
        
        if response.get('success'):
            print(f"✓ {response.get('message', 'Game removed')}")
        else:
            print(f"❌ {response.get('error', 'Failed to remove game')}")
    
    def main_menu(self):
        """Main menu for logged-in developers"""
        while self.logged_in:
            print("\n" + "="*50)
            print("🎮 Developer Portal")
            print("="*50)
            print(f"Logged in as: {self.username}")
            print("\n1. My Games")
            print("2. Upload New Game")
            print("3. Update Game")
            print("4. Remove Game")
            print("5. Logout")
            print("="*50)
            
            choice = input("\nSelect option (1-5): ").strip()
            
            if choice == '1':
                self.my_games()
            elif choice == '2':
                self.upload_game()
            elif choice == '3':
                self.update_game()
            elif choice == '4':
                self.remove_game()
            elif choice == '5':
                self.logged_in = False
                print("✓ Logged out")
            else:
                print("❌ Invalid option")
            
            if self.logged_in:
                input("\nPress Enter to continue...")
    
    def run(self):
        """Run the client"""
        print("="*50)
        print("🎮 Game Store - Developer Client")
        print("="*50)
        
        if not self.connect():
            return
        
        print("✓ Connected to developer server")
        
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
                        print("\nGoodbye!")
                        break
                    else:
                        print("❌ Invalid option")
        except KeyboardInterrupt:
            print("\n\nGoodbye!")
        finally:
            if self.protocol:
                self.protocol.close()


if __name__ == '__main__':
    # Allow overriding host/port via command line
    host = sys.argv[1] if len(sys.argv) > 1 else 'linux4.cs.nycu.edu.tw'
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 10003
    
    client = DeveloperClient(host, port)
    client.run()
