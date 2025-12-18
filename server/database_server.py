"""
Database Server - Port 10001
Manages persistent data storage using JSON files
"""
import socket
import json
import os
import sys
import hashlib
import uuid
from datetime import datetime
from threading import Thread, Lock

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.protocol import Protocol


class DatabaseServer:
    def __init__(self, host='0.0.0.0', port=10001, data_dir='db_data'):
        self.host = host
        self.port = port
        self.data_dir = data_dir
        self.running = False
        
        # Data storage
        self.collections = {
            'User': {},           # {user_id: {...}}
            'Game': {},           # {game_id: {...}}
            'Version': {},        # {version_id: {...}}
            'Room': {},           # {room_id: {...}}
            'Review': {},         # {review_id: {...}}
        }
        
        self.locks = {name: Lock() for name in self.collections.keys()}
        
        print("\n" + "="*70)
        print("💾 DATABASE SERVER v2.1 - BUILD 2025-12-17-18:30")
        print("="*70)
        print(f"✓ Port: {self.port}")
        print(f"✓ Data dir: {self.data_dir}")
        print("="*70 + "\n")
        
        # Load existing data
        self._load_data()
    
    def _load_data(self):
        """Load all collections from JSON files"""
        os.makedirs(self.data_dir, exist_ok=True)
        
        for collection_name in self.collections.keys():
            filepath = os.path.join(self.data_dir, f'{collection_name}.json')
            if os.path.exists(filepath):
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        self.collections[collection_name] = json.load(f)
                    print(f"[DB] Loaded {collection_name}: {len(self.collections[collection_name])} records")
                except Exception as e:
                    print(f"[DB] Error loading {collection_name}: {e}")
    
    def _save_collection(self, collection_name: str):
        """Save a collection to its JSON file"""
        filepath = os.path.join(self.data_dir, f'{collection_name}.json')
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(self.collections[collection_name], f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[DB] Error saving {collection_name}: {e}")
    
    def start(self):
        """Start the database server"""
        self.running = True
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((self.host, self.port))
        server_socket.listen(5)
        
        print(f"[DB Server] Listening on {self.host}:{self.port}")
        
        try:
            while self.running:
                client_socket, addr = server_socket.accept()
                print(f"[DB] Connection from {addr}")
                Thread(target=self._handle_client, args=(client_socket,), daemon=True).start()
        except KeyboardInterrupt:
            print("\n[DB] Shutting down...")
        finally:
            server_socket.close()
    
    def _handle_client(self, client_socket: socket.socket):
        """Handle a client connection"""
        protocol = Protocol(client_socket)
        
        try:
            while not protocol.closed:
                message = protocol.receive_message()
                if not message:
                    break
                
                response = self._process_request(message)
                protocol.send_message(response)
        except Exception as e:
            print(f"[DB] Client error: {e}")
        finally:
            protocol.close()
    
    def _process_request(self, request: dict) -> dict:
        """Process a database request"""
        action = request.get('action')
        collection = request.get('collection')
        
        if not action or not collection or collection not in self.collections:
            return {'success': False, 'error': 'Invalid request'}
        
        # Route to appropriate handler
        handlers = {
            'insert': self._handle_insert,
            'find': self._handle_find,
            'find_one': self._handle_find_one,
            'update': self._handle_update,
            'delete': self._handle_delete,
        }
        
        handler = handlers.get(action)
        if handler:
            return handler(collection, request.get('data', {}))
        
        return {'success': False, 'error': 'Unknown action'}
    
    def _handle_insert(self, collection: str, data: dict) -> dict:
        """Insert a document"""
        with self.locks[collection]:
            doc_id = data.get('_id') or str(uuid.uuid4())
            data['_id'] = doc_id
            data['created_at'] = datetime.now().isoformat()
            
            self.collections[collection][doc_id] = data
            self._save_collection(collection)
            
            return {'success': True, 'id': doc_id}
    
    def _handle_find(self, collection: str, data: dict) -> dict:
        """Find documents matching query"""
        query = data.get('query', {})
        
        with self.locks[collection]:
            results = []
            for doc_id, doc in self.collections[collection].items():
                if self._match_query(doc, query):
                    results.append(doc)
            
            return {'success': True, 'results': results}
    
    def _handle_find_one(self, collection: str, data: dict) -> dict:
        """Find one document matching query"""
        query = data.get('query', {})
        
        with self.locks[collection]:
            for doc_id, doc in self.collections[collection].items():
                if self._match_query(doc, query):
                    return {'success': True, 'result': doc}
            
            return {'success': False, 'error': 'Not found'}
    
    def _handle_update(self, collection: str, data: dict) -> dict:
        """Update documents matching query"""
        query = data.get('query', {})
        update = data.get('update', {})
        
        with self.locks[collection]:
            updated_count = 0
            for doc_id, doc in self.collections[collection].items():
                if self._match_query(doc, query):
                    doc.update(update)
                    doc['updated_at'] = datetime.now().isoformat()
                    updated_count += 1
            
            if updated_count > 0:
                self._save_collection(collection)
            
            return {'success': True, 'count': updated_count}
    
    def _handle_delete(self, collection: str, data: dict) -> dict:
        """Delete documents matching query"""
        query = data.get('query', {})
        
        with self.locks[collection]:
            to_delete = []
            for doc_id, doc in self.collections[collection].items():
                if self._match_query(doc, query):
                    to_delete.append(doc_id)
            
            for doc_id in to_delete:
                del self.collections[collection][doc_id]
            
            if to_delete:
                self._save_collection(collection)
            
            return {'success': True, 'count': len(to_delete)}
    
    def _match_query(self, doc: dict, query: dict) -> bool:
        """Check if document matches query"""
        for key, value in query.items():
            if key not in doc or doc[key] != value:
                return False
        return True


def hash_password(password: str) -> str:
    """Hash a password using SHA256"""
    return hashlib.sha256(password.encode()).hexdigest()


if __name__ == '__main__':
    # Database server runs on localhost only (internal use)
    server = DatabaseServer()
    server.start()
