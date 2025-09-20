#!/usr/bin/env python3
"""
Test script for Google Photos to Immich Migration

Tests the migration with sample files in the examples/ folder.
"""

import os
import sys
from pathlib import Path
from typing import Optional

# Add script directory to Python path
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir))

from gphoto_to_immich import Config, GooglePhotosProcessor


def test_migration():
    """Test migration with sample files"""
    
    # Configuration for test
    config = Config(
        immich_url="http://localhost:2283",
        immich_api_key="test-api-key",  # Replace with real API key
        takeout_path=str(script_dir / "examples" / "Takeout"),
        max_workers=2,
        batch_size=5,
        dry_run=True,  # Only simulate
        timeout=30
    )
    
    print("=" * 60)
    print("GOOGLE PHOTOS TO IMMICH MIGRATION - TEST")
    print("=" * 60)
    print(f"Takeout path: {config.takeout_path}")
    print(f"Dry Run: {config.dry_run}")
    print(f"Max Workers: {config.max_workers}")
    print(f"Batch Size: {config.batch_size}")
    print("=" * 60)
    
    # Check if takeout path exists
    if not os.path.exists(config.takeout_path):
        print(f"ERROR: Takeout path does not exist: {config.takeout_path}")
        return False
    
    try:
        # Start migration
        processor = GooglePhotosProcessor(config)
        processor.process_takeout(config.takeout_path)
        
        print("=" * 60)
        print("TEST SUCCESSFULLY COMPLETED")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"ERROR during test: {e}")
        return False


def analyze_examples(takeout_path: Optional[str] = None):
    """Analyze sample files and show their structure"""
    
    if takeout_path:
        takeout_dir = Path(takeout_path)
    else:
        examples_dir = script_dir / "examples"
        takeout_dir = examples_dir / "Takeout"
    
    print("=" * 60)
    print("SAMPLE FILES ANALYSIS")
    print("=" * 60)
    
    if not takeout_dir.exists():
        print(f"Takeout directory not found: {takeout_dir}")
        return
    
    print(f"Analyzing: {takeout_dir}")
    print()
    
    # Find all directories
    directories = []
    for root, dirs, files in os.walk(takeout_dir):
        root_path = Path(root)
        if root_path != takeout_dir:  # Skip root directory
            directories.append(root_path)
    
    print(f"Found {len(directories)} directories:")
    print()
    
    for i, dir_path in enumerate(directories, 1):
        relative_path = dir_path.relative_to(takeout_dir)
        print(f"{i:2d}. {relative_path}")
        
        # Check if it's an album (has Metadaten.json)
        metadata_file = dir_path / "Metadaten.json"
        if metadata_file.exists():
            try:
                import json
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    album_data = json.load(f)
                    album_title = album_data.get('title', 'Unknown')
                    print(f"    📁 Album: {album_title}")
            except Exception as e:
                print(f"    📁 Album: (could not read metadata: {e})")
        else:
            print(f"    📂 Folder")
        
        # Count media files
        media_files = []
        for file in dir_path.iterdir():
            if file.is_file() and file.suffix.lower() in {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif', '.heic', '.heif', '.mp4', '.mov', '.avi', '.mkv', '.webm'}:
                media_files.append(file)
        
        print(f"    📷 Media files: {len(media_files)}")
        
        # Show first few files
        if media_files:
            print(f"    📄 Sample files:")
            for file in media_files[:3]:
                print(f"        - {file.name}")
            if len(media_files) > 3:
                print(f"        ... and {len(media_files) - 3} more")
        
        print()
    
    print("=" * 60)
    print("ANALYSIS COMPLETED")
    print("=" * 60)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Test script for Google Photos Migration')
    parser.add_argument('--analyze', action='store_true', 
                       help='Only analyze sample files')
    parser.add_argument('--test', action='store_true', 
                       help='Run migration test')
    parser.add_argument('--takeout-path', 
                       help='Path to Google Photos Takeout folder')
    
    args = parser.parse_args()
    
    if args.analyze:
        analyze_examples(args.takeout_path)
    elif args.test:
        success = test_migration()
        sys.exit(0 if success else 1)
    else:
        # Default: run both
        analyze_examples(args.takeout_path)
        print("\n" + "=" * 60)
        print("STARTING MIGRATION TEST")
        print("=" * 60)
        success = test_migration()
        sys.exit(0 if success else 1)