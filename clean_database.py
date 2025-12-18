#!/usr/bin/env python3
"""
Clean Database Script
Removes all data from the database for a fresh start
"""
import os
import shutil
import sys

def clean_database():
    """Remove all database files"""
    db_dir = 'db_data'
    
    if os.path.exists(db_dir):
        print(f"🗑️  Removing database directory: {db_dir}")
        shutil.rmtree(db_dir)
        print("✓ Database cleaned")
    else:
        print("ℹ️  Database directory not found (already clean)")
    
    # Create fresh directory
    os.makedirs(db_dir, exist_ok=True)
    print(f"✓ Created fresh database directory")

def clean_uploads():
    """Remove all uploaded games"""
    upload_dir = 'uploaded_games'
    
    if os.path.exists(upload_dir):
        print(f"🗑️  Removing uploaded games directory: {upload_dir}")
        shutil.rmtree(upload_dir)
        print("✓ Uploaded games cleaned")
    else:
        print("ℹ️  Upload directory not found (already clean)")
    
    # Create fresh directory
    os.makedirs(upload_dir, exist_ok=True)
    print(f"✓ Created fresh upload directory")

def clean_logs():
    """Remove all game server logs"""
    logs_dir = 'game_server_logs'
    
    if os.path.exists(logs_dir):
        print(f"🗑️  Removing game server logs: {logs_dir}")
        # Force remove all files first, then directory
        for root, dirs, files in os.walk(logs_dir, topdown=False):
            for name in files:
                file_path = os.path.join(root, name)
                try:
                    os.chmod(file_path, 0o777)  # Ensure writable
                    os.remove(file_path)
                except Exception as e:
                    print(f"⚠️  Could not remove {file_path}: {e}")
            for name in dirs:
                dir_path = os.path.join(root, name)
                try:
                    os.rmdir(dir_path)
                except Exception as e:
                    print(f"⚠️  Could not remove {dir_path}: {e}")
        # Remove the main directory
        try:
            os.rmdir(logs_dir)
            print("✓ Logs cleaned")
        except Exception as e:
            print(f"⚠️  Could not remove {logs_dir}: {e}")
            # Try shutil as fallback
            try:
                shutil.rmtree(logs_dir, ignore_errors=True)
                print("✓ Logs cleaned (forced)")
            except:
                print("❌ Failed to clean logs - manual cleanup required")
    else:
        print("ℹ️  Logs directory not found (already clean)")
    
    # Create fresh directory
    os.makedirs(logs_dir, exist_ok=True)
    print(f"✓ Created fresh logs directory")

if __name__ == '__main__':
    print("="*60)
    print("🧹 Database Cleanup Script")
    print("="*60)
    print("\n⚠️  WARNING: This will delete ALL data!")
    print("   - All user accounts")
    print("   - All uploaded games")
    print("   - All reviews")
    print("   - All game server logs")
    
    if '--force' not in sys.argv:
        confirm = input("\nAre you sure? Type 'yes' to confirm: ").strip().lower()
        if confirm != 'yes':
            print("❌ Cleanup cancelled")
            sys.exit(0)
    
    print("\n🧹 Starting cleanup...\n")
    
    clean_database()
    clean_uploads()
    clean_logs()
    
    print("\n" + "="*60)
    print("✅ Cleanup complete! Database is now fresh.")
    print("="*60)
    print("\n💡 Next steps:")
    print("   1. Start the servers: python server/database_server.py &")
    print("   2. Upload games as developer")
    print("   3. Play games as player")
