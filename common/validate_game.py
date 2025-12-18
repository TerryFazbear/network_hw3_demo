"""
Game Package Validation
Ensures uploaded games follow the required structure
"""
import json
import os
from typing import Dict, Tuple, Optional


def validate_game_package(game_dir: str) -> Tuple[bool, Optional[str], Optional[Dict]]:
    """
    Validate a game package structure
    
    Returns:
        (success, error_message, game_info_dict)
    """
    # Check if game_info.json exists
    info_path = os.path.join(game_dir, 'game_info.json')
    if not os.path.exists(info_path):
        return False, "Missing game_info.json", None
    
    # Parse game_info.json
    try:
        with open(info_path, 'r', encoding='utf-8') as f:
            game_info = json.load(f)
    except json.JSONDecodeError as e:
        return False, f"Invalid JSON in game_info.json: {e}", None
    except Exception as e:
        return False, f"Cannot read game_info.json: {e}", None
    
    # Validate required fields
    required_fields = ['name', 'version', 'description', 'min_players', 'max_players']
    for field in required_fields:
        if field not in game_info:
            return False, f"Missing required field: {field}", None
    
    # Validate server configuration
    if 'server' not in game_info:
        return False, "Missing 'server' configuration", None
    
    server_config = game_info['server']
    if 'entry_point' not in server_config:
        return False, "Missing server.entry_point", None
    
    # Check if server entry point exists
    server_entry = os.path.join(game_dir, server_config['entry_point'])
    if not os.path.exists(server_entry):
        return False, f"Server entry point not found: {server_config['entry_point']}", None
    
    # Validate client configuration
    if 'client' not in game_info:
        return False, "Missing 'client' configuration", None
    
    client_config = game_info['client']
    if 'entry_point' not in client_config:
        return False, "Missing client.entry_point", None
    
    # Check if client entry point exists
    client_entry = os.path.join(game_dir, client_config['entry_point'])
    if not os.path.exists(client_entry):
        return False, f"Client entry point not found: {client_config['entry_point']}", None
    
    return True, None, game_info


def get_game_files(game_dir: str) -> list:
    """Get all files in a game directory (relative paths)"""
    files = []
    for root, dirs, filenames in os.walk(game_dir):
        for filename in filenames:
            full_path = os.path.join(root, filename)
            rel_path = os.path.relpath(full_path, game_dir)
            files.append(rel_path)
    return files
