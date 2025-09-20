#!/usr/bin/env python3
"""
Google Photos to Immich Migration Script

A high-performance script for migrating Google Photos Takeout to Immich.
Optimized for processing 50,000+ images and videos.

Dependencies:
- Python 3.8+
- requests (for HTTP requests)
- hashlib (built-in, for SHA-1)
- json (built-in)
- os, pathlib (built-in)
- concurrent.futures (built-in, for parallelization)
- time (built-in, for performance monitoring)
"""

import os
import json
import hashlib
import time
import logging
import threading
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


# Configuration
@dataclass
class Config:
    """Configuration for the migration"""
    immich_url: str = "http://localhost:2283"
    immich_api_key: str = ""
    takeout_path: str = ""
    max_workers: int = 10
    batch_size: int = 100
    retry_attempts: int = 3
    timeout: int = 300
    dry_run: bool = False


# Logging Setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('gphoto_migration.log'),
        logging.StreamHandler()
    ]
)

# Separate loggers for specific operations
album_creation_logger = logging.getLogger('album_creation')
album_creation_handler = logging.FileHandler('album_creation.log')
album_creation_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
album_creation_logger.addHandler(album_creation_handler)
album_creation_logger.setLevel(logging.INFO)

asset_album_logger = logging.getLogger('asset_album')
asset_album_handler = logging.FileHandler('asset_album_assignment.log')
asset_album_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
asset_album_logger.addHandler(asset_album_handler)
asset_album_logger.setLevel(logging.INFO)

logger = logging.getLogger(__name__)


class ImmichClient:
    """Client for interacting with Immich API"""
    
    def __init__(self, config: Config):
        self.config = config
        self.session = self._create_session()
        self._album_cache = {}
        self._album_creation_lock = threading.Lock()
    
    def _create_session(self):
        """Create HTTP session with retry logic"""
        session = requests.Session()
        
        # Retry strategy
        retry_strategy = Retry(
            total=self.config.retry_attempts,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # Set headers
        session.headers.update({
            'X-API-Key': self.config.immich_api_key
            # Content-Type wird automatisch für multipart/form-data gesetzt
        })
        
        return session
    
    def upload_asset(self, file_path: Path, metadata: Dict, album_title: Optional[str] = None) -> Optional[Dict]:
        """Upload an asset to Immich"""
        if self.config.dry_run:
            logger.info(f"[DRY RUN] Would upload: {file_path}")
            return {
                'asset_id': f'dry_run_{hash(str(file_path))}',
                'is_duplicate': False,
                'metadata_updated': False
            }
        
        try:
            # Calculate file hash for duplicate detection
            file_hash = self._calculate_file_hash(file_path)
            
            # Prepare upload data
            upload_data = {
                'fileCreatedAt': metadata.get('fileCreatedAt'),
                'fileModifiedAt': metadata.get('fileModifiedAt'),
                'filename': file_path.name,
                'deviceAssetId': f"gphoto_1",
                'deviceId': 'gphoto-migration-tool',
                'metadata': [{'key': 'mobile-app', 'value': {'source': 'gphoto-import'}}]
            }
            
            # Add checksum header
            headers = {'x-immich-checksum': file_hash}
            
            # Prepare files for upload
            files = {'assetData': open(file_path, 'rb')}
            
            # Debug: Log request details
            logger.info(f"Uploading {file_path.name} with deviceAssetId: {upload_data['deviceAssetId']}")
            
            # Upload asset
            response = self.session.post(
                f"{self.config.immich_url}/api/assets",
                data=upload_data,
                files=files,
                headers=headers,
                timeout=self.config.timeout
            )
            
            files['assetData'].close()
            
            # Debug: Log response details
            if response.status_code not in [200, 201]:
                logger.error(f"Upload failed: {response.status_code} - {response.text}")
            
            if response.status_code in [200, 201]:
                asset_data = response.json()
                asset_id = asset_data['id']
                
                # Check if it's a duplicate
                if response.status_code == 200 and asset_data.get('status') == 'duplicate':
                    logger.info(f"Asset already exists (duplicate): {file_path} -> {asset_id}")
                    # Check and update metadata for duplicates
                    metadata_updated = self._check_and_update_metadata(asset_id, metadata)
                    if metadata_updated:
                        if hasattr(self, '_processor') and hasattr(self._processor, 'stats'):
                            self._processor.stats['metadata_updates'] += 1
                    else:
                        if hasattr(self, '_processor') and hasattr(self._processor, 'stats'):
                            self._processor.stats['metadata_already_correct'] += 1
                else:
                    logger.info(f"Asset successfully uploaded: {file_path} -> {asset_id}")
                    # Check and update metadata for new uploads
                    metadata_updated = self._check_and_update_metadata(asset_id, metadata)
                    if metadata_updated:
                        if hasattr(self, '_processor') and hasattr(self._processor, 'stats'):
                            self._processor.stats['metadata_updates'] += 1
                    else:
                        if hasattr(self, '_processor') and hasattr(self._processor, 'stats'):
                            self._processor.stats['metadata_already_correct'] += 1
                
                # Add to album if present
                if album_title:
                    self._add_to_album(asset_id, album_title)
                
                return {
                    'asset_id': asset_id,
                    'is_duplicate': response.status_code == 200 and asset_data.get('status') == 'duplicate',
                    'metadata_updated': metadata_updated
                }
            else:
                return None
                
        except Exception as e:
            logger.error(f"Error uploading {file_path}: {e}")
            return None
    
    def _calculate_file_hash(self, file_path: Path) -> str:
        """Calculate SHA-1 hash of file"""
        hash_sha1 = hashlib.sha1()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha1.update(chunk)
        return hash_sha1.hexdigest()
    
    def _check_and_update_metadata(self, asset_id: str, metadata: Dict) -> bool:
        """Check and update metadata of an existing asset
        
        Returns:
            bool: True if metadata was updated, False if already correct
        """
        try:
            # Get asset information
            response = self.session.get(
                f"{self.config.immich_url}/api/assets/{asset_id}",
                timeout=30
            )
            
            if response.status_code != 200:
                logger.warning(f"Could not retrieve asset information for {asset_id}")
                return False
            
            asset_info = response.json()
            needs_update = False
            update_data = {'ids': [asset_id]}
            
            # Check creation date (fileCreatedAt vs. exifInfo.dateTimeOriginal)
            expected_created_at = metadata.get('fileCreatedAt')
            if expected_created_at:
                # Current EXIF date from asset info
                current_exif_date = asset_info.get('exifInfo', {}).get('dateTimeOriginal')
                current_file_created = asset_info.get('fileCreatedAt')
                
                logger.info(f"Asset {asset_id}: Expected date: {expected_created_at}")
                logger.info(f"Asset {asset_id}: Current EXIF date: {current_exif_date}")
                logger.info(f"Asset {asset_id}: Current fileCreatedAt: {current_file_created}")
                
                # Check if EXIF date needs to be updated
                if current_exif_date != expected_created_at:
                    logger.info(f"Asset {asset_id}: EXIF date differs - update required")
                    update_data['dateTimeOriginal'] = expected_created_at
                    needs_update = True
                
                # Check if fileCreatedAt needs to be updated
                if current_file_created != expected_created_at:
                    logger.info(f"Asset {asset_id}: fileCreatedAt differs - update required")
                    # For fileCreatedAt we use dateTimeOriginal (this is the correct parameter)
                    if 'dateTimeOriginal' not in update_data:
                        update_data['dateTimeOriginal'] = expected_created_at
                    needs_update = True
            
            # Check geo data
            geo_data = metadata.get('geoData')
            if geo_data and geo_data.get('latitude') != 0.0 and geo_data.get('longitude') != 0.0:
                current_lat = asset_info.get('exifInfo', {}).get('latitude')
                current_lon = asset_info.get('exifInfo', {}).get('longitude')
                
                expected_lat = geo_data.get('latitude')
                expected_lon = geo_data.get('longitude')
                
                logger.info(f"Asset {asset_id}: Expected geo data: {expected_lat}, {expected_lon}")
                logger.info(f"Asset {asset_id}: Current geo data: {current_lat}, {current_lon}")
                
                # Check if geo data is missing or differs
                if (current_lat is None or current_lon is None or 
                    abs(current_lat - expected_lat) > 0.0001 or 
                    abs(current_lon - expected_lon) > 0.0001):
                    logger.info(f"Asset {asset_id}: Geo data differs or missing - update required")
                    update_data['latitude'] = expected_lat
                    update_data['longitude'] = expected_lon
                    needs_update = True
            
            # Perform update if required
            if needs_update:
                logger.info(f"Asset {asset_id}: Updating metadata with: {update_data}")
                self._update_asset_metadata(update_data)
                return True
            else:
                logger.info(f"Asset {asset_id}: Metadata is already correct")
                return False
                
        except Exception as e:
            logger.warning(f"Error checking metadata for asset {asset_id}: {e}")
            return False
    
    def _update_asset_metadata(self, update_data: Dict):
        """Update asset metadata"""
        try:
            response = self.session.put(
                f"{self.config.immich_url}/api/assets",
                json=update_data,
                timeout=30
            )
            
            if response.status_code == 204:
                logger.info(f"Asset metadata successfully updated for Asset {update_data['ids'][0]}")
            else:
                logger.warning(f"Asset metadata update failed: {response.status_code} - {response.text}")
                
        except Exception as e:
            logger.warning(f"Error updating asset metadata: {e}")
    
    def _add_to_album(self, asset_id: str, album_title: str):
        """Add asset to album"""
        try:
            album_id = self._get_or_create_album(album_title)
            if not album_id:
                return
            
            response = self.session.put(
                f"{self.config.immich_url}/api/albums/{album_id}/assets",
                json={'ids': [asset_id]},
                timeout=30
            )
            
            if response.status_code == 200:
                logger.info(f"Asset {asset_id} successfully added to album {album_title}")
                # Write to separate asset-album assignment log
                asset_album_logger.info(f"Asset added to album: Asset {asset_id} -> Album '{album_title}'")
            else:
                logger.warning(f"Asset {asset_id} could not be added to album {album_title}: {response.status_code} - {response.text}")
                # Log failed assignment as well
                asset_album_logger.warning(f"ERROR: Asset {asset_id} could not be added to album '{album_title}': {response.status_code} - {response.text}")
                
        except Exception as e:
            logger.warning(f"Error adding asset {asset_id} to album {album_title}: {e}")
    
    def _get_or_create_album(self, album_title: str) -> str:
        """Get album ID from cache or create new album (thread-safe)"""
        # First check if album is already in cache
        if album_title in self._album_cache:
            # Album already exists - log it
            album_creation_logger.info(f"Album already exists: '{album_title}' (ID: {self._album_cache[album_title]})")
            # Update statistics (only once per album)
            if not hasattr(self, '_album_stats_tracked'):
                self._album_stats_tracked = set()
            if album_title not in self._album_stats_tracked:
                self._album_stats_tracked.add(album_title)
                # Update statistics via processor
                if hasattr(self, '_processor') and hasattr(self._processor, 'stats'):
                    self._processor.stats['albums_existing'] += 1
                # Add album to list (only once per album)
                if album_title not in [album['name'] for album in self._processor.existing_albums]:
                    self._processor.existing_albums.append({
                        'name': album_title,
                        'id': self._album_cache[album_title]
                    })
            return self._album_cache[album_title]
        
        # Thread-safe album creation
        with self._album_creation_lock:
            # Check again (Double-Checked Locking Pattern)
            if album_title in self._album_cache:
                album_creation_logger.info(f"Album already exists (after lock): '{album_title}' (ID: {self._album_cache[album_title]})")
                return self._album_cache[album_title]
            
            try:
                # Create new album
                response = self.session.post(
                    f"{self.config.immich_url}/api/albums",
                    json={'albumName': album_title},
                    timeout=30
                )
                
                if response.status_code == 201:
                    album_data = response.json()
                    album_id = album_data['id']
                    # Update cache immediately to prevent multiple creation
                    self._album_cache[album_title] = album_id
                    logger.info(f"New album created: {album_title}")
                    # Write to separate album creation log
                    album_creation_logger.info(f"Album created: '{album_title}' (ID: {album_id})")
                    # Update statistics
                    if hasattr(self, '_processor') and hasattr(self._processor, 'stats'):
                        self._processor.stats['albums_created'] += 1
                        # Add album to list of created albums
                        self._processor.created_albums.append({
                            'name': album_title,
                            'id': album_id
                        })
                    return album_id
                else:
                    logger.error(f"Album creation failed: {response.text}")
                    return ""
                    
            except Exception as e:
                logger.error(f"Error creating album {album_title}: {e}")
                return ""
    
    def load_existing_albums(self):
        """Load existing albums from Immich"""
        try:
            response = self.session.get(
                f"{self.config.immich_url}/api/albums",
                timeout=30
            )
            
            if response.status_code == 200:
                albums = response.json()
                for album in albums:
                    self._album_cache[album['albumName']] = album['id']
                logger.info(f"Loaded: {len(albums)} existing albums")
            else:
                logger.warning(f"Could not load existing albums: {response.status_code}")
                
        except Exception as e:
            logger.warning(f"Error loading existing albums: {e}")


class GooglePhotosProcessor:
    """Main processor for Google Photos migration"""
    
    def __init__(self, config: Config):
        self.config = config
        self.immich_client = ImmichClient(config)
        # Link client with processor for statistics
        self.immich_client._processor = self
        self.processed_files: Set[str] = set()
        self.stats = {
            'total_files': 0,
            'processed_files': 0,
            'failed_files': 0,
            'new_uploads': 0,
            'duplicates_found': 0,
            'albums_created': 0,
            'albums_existing': 0,
            'metadata_updates': 0,
            'metadata_already_correct': 0,
            'start_time': time.time()
        }
        # List of created albums for detailed output
        self.created_albums = []
        self.existing_albums = []
    
    def process_takeout(self, takeout_path: str):
        """Process Google Photos Takeout data"""
        takeout_dir = Path(takeout_path)
        
        if not takeout_dir.exists():
            logger.error(f"Takeout directory does not exist: {takeout_path}")
            return
        
        logger.info(f"Starting processing of: {takeout_path}")
        
        # Load existing albums
        self.immich_client.load_existing_albums()
        
        # Find all media files
        media_files = self._find_media_files(takeout_dir)
        self.stats['total_files'] = len(media_files)
        
        logger.info(f"Found: {len(media_files)} media files")
        
        if not media_files:
            logger.warning("No media files found!")
            return
        
        # Process files in batches
        self._process_files_in_batches(media_files)
        
        # Print final statistics
        self._print_statistics()
    
    def _find_media_files(self, directory: Path) -> List[Tuple[Path, Path, Optional[str]]]:
        """Find all media files and their metadata"""
        media_files = []
        
        for root, dirs, files in os.walk(directory):
            root_path = Path(root)
            
            # Check if this is an album directory
            album_title = None
            metadata_file = root_path / "Metadaten.json"
            if metadata_file.exists():
                try:
                    with open(metadata_file, 'r', encoding='utf-8') as f:
                        album_data = json.load(f)
                        album_title = album_data.get('title', '')
                        logger.info(f"Found album: {album_title}")
                except Exception as e:
                    logger.warning(f"Could not read album metadata {metadata_file}: {e}")
            
            # Find media files
            for file in files:
                if self._is_media_file(file):
                    file_path = root_path / file
                    metadata_path = self._find_metadata_file(file_path)
                    
                    if metadata_path:
                        media_files.append((file_path, metadata_path, album_title))
                    else:
                        logger.warning(f"No metadata found for: {file_path}")
        
        return media_files
    
    def _is_media_file(self, filename: str) -> bool:
        """Check if file is a supported media file"""
        media_extensions = {
            '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif',
            '.heic', '.heif', '.mp4', '.mov', '.avi', '.mkv', '.webm'
        }
        return Path(filename).suffix.lower() in media_extensions
    
    def _find_metadata_file(self, file_path: Path) -> Optional[Path]:
        """Find metadata file for a media file"""
        possible_names = [
            f"{file_path.name}.supplemental-metadata.json",
            f"{file_path.name}.supplemental-metadata copy.json"
        ]
        
        for name in possible_names:
            metadata_path = file_path.parent / name
            if metadata_path.exists():
                return metadata_path
        
        return None
    
    def _process_files_in_batches(self, media_files: List[Tuple[Path, Path, Optional[str]]]):
        """Process files in batches with parallel execution"""
        total_batches = (len(media_files) + self.config.batch_size - 1) // self.config.batch_size
        
        with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            for i in range(0, len(media_files), self.config.batch_size):
                batch = media_files[i:i + self.config.batch_size]
                batch_num = i // self.config.batch_size + 1
                
                logger.info(f"Processing batch {batch_num}/{total_batches}")
                
                # Submit batch tasks
                future_to_file = {
                    executor.submit(self._process_single_file, file_path, metadata_path, album_title): file_path
                    for file_path, metadata_path, album_title in batch
                }
                
                # Process completed tasks
                for future in as_completed(future_to_file):
                    file_path = future_to_file[future]
                    try:
                        result = future.result()
                        if result:
                            self.stats['processed_files'] += 1
                            # Distinguish between new uploads and duplicates
                            if result.get('is_duplicate'):
                                self.stats['duplicates_found'] += 1
                            else:
                                self.stats['new_uploads'] += 1
                        else:
                            self.stats['failed_files'] += 1
                    except Exception as e:
                        logger.error(f"Unexpected error for {file_path}: {e}")
                        self.stats['failed_files'] += 1
    
    def _process_single_file(self, file_path: Path, metadata_path: Path, album_title: Optional[str]) -> Optional[Dict]:
        """Process a single media file"""
        try:
            # Load metadata
            metadata = self._load_metadata(metadata_path)
            if not metadata:
                return None
            
            # Prepare upload metadata
            upload_metadata = self._prepare_upload_metadata(file_path, metadata)
            
            # Upload asset
            result = self.immich_client.upload_asset(file_path, upload_metadata, album_title)
            
            if result:
                self.processed_files.add(str(file_path))
                return result
            else:
                return None
                
        except Exception as e:
            logger.error(f"Error processing {file_path}: {e}")
            return None
    
    def _load_metadata(self, metadata_path: Path) -> Optional[Dict]:
        """Load metadata from JSON file"""
        try:
            with open(metadata_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Extract relevant metadata
            metadata = {}
            
            # Photo taken time
            if 'photoTakenTime' in data:
                timestamp = data['photoTakenTime'].get('timestamp')
                if timestamp:
                    # Convert to ISO format
                    dt = time.strftime('%Y-%m-%dT%H:%M:%S.000Z', time.gmtime(int(timestamp)))
                    metadata['fileCreatedAt'] = dt
                    metadata['fileModifiedAt'] = dt
            
            # Geo data
            if 'geoDataExif' in data:
                geo = data['geoDataExif']
                if geo.get('latitude') != 0.0 and geo.get('longitude') != 0.0:
                    metadata['geoData'] = {
                        'latitude': geo.get('latitude'),
                        'longitude': geo.get('longitude'),
                        'altitude': geo.get('altitude', 0)
                    }
            
            return metadata
            
        except Exception as e:
            logger.warning(f"Could not load metadata from {metadata_path}: {e}")
            return None
    
    def _prepare_upload_metadata(self, file_path: Path, metadata: Dict) -> Dict:
        """Prepare metadata for upload"""
        upload_metadata = {}
        
        # File creation time
        if 'fileCreatedAt' in metadata:
            upload_metadata['fileCreatedAt'] = metadata['fileCreatedAt']
            upload_metadata['fileModifiedAt'] = metadata['fileModifiedAt']
        
        # Geo data
        if 'geoData' in metadata:
            upload_metadata['geoData'] = metadata['geoData']
        
        return upload_metadata
    
    def _print_statistics(self):
        """Print detailed processing statistics"""
        elapsed_time = time.time() - self.stats['start_time']
        
        logger.info("")
        logger.info("=" * 70)
        logger.info("🎉 MIGRATION SUCCESSFULLY COMPLETED")
        logger.info("=" * 70)
        logger.info(f"⏱️  Total time: {elapsed_time:.2f} seconds ({elapsed_time/60:.1f} minutes)")
        logger.info(f"⏱️  Average time per file: {elapsed_time/self.stats['total_files']:.2f} seconds")
        logger.info("")
        logger.info("📊 UPLOAD STATISTICS:")
        logger.info(f"   📁 Total files found: {self.stats['total_files']}")
        logger.info(f"   ✅ Successfully processed: {self.stats['processed_files']}")
        logger.info(f"   ❌ Failed: {self.stats['failed_files']}")
        logger.info(f"   📈 Success rate: {(self.stats['processed_files'] / self.stats['total_files'] * 100):.1f}%")
        logger.info("")
        logger.info("🔄 UPLOAD DETAILS:")
        logger.info(f"   🆕 New uploads: {self.stats['new_uploads']}")
        logger.info(f"   🔄 Duplicates found: {self.stats['duplicates_found']}")
        logger.info("")
        logger.info("📚 ALBUM STATISTICS:")
        logger.info(f"   🆕 New albums created: {self.stats['albums_created']}")
        logger.info(f"   📁 Already existing albums: {self.stats['albums_existing']}")
        logger.info(f"   📊 Total albums: {self.stats['albums_created'] + self.stats['albums_existing']}")
        logger.info("")
        logger.info("🔧 METADATA STATISTICS:")
        logger.info(f"   🔄 Metadata updated: {self.stats['metadata_updates']}")
        logger.info(f"   ✅ Metadata already correct: {self.stats['metadata_already_correct']}")
        logger.info("")
        logger.info("=" * 70)
        logger.info("🎯 SUMMARY:")
        logger.info(f"   • {self.stats['new_uploads']} new images/videos uploaded")
        logger.info(f"   • {self.stats['duplicates_found']} duplicates detected and processed")
        logger.info(f"   • {self.stats['albums_created']} new albums created")
        logger.info(f"   • {self.stats['metadata_updates']} metadata corrected")
        logger.info("=" * 70)
        
        # Print detailed album lists
        self._print_album_details()
    
    def _print_album_details(self):
        """Print detailed information about all albums"""
        logger.info("")
        logger.info("=" * 70)
        logger.info("📚 NEW ALBUMS CREATED")
        logger.info("=" * 70)
        
        # New albums
        if self.created_albums:
            for i, album in enumerate(self.created_albums, 1):
                logger.info(f"   {i:2d}. {album['name']}")
                logger.info(f"       ID: {album['id']}")
        else:
            logger.info("   No new albums created")
        
        logger.info("=" * 70)


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Google Photos to Immich Migration')
    parser.add_argument('--immich-url', default='http://localhost:2283', 
                       help='Immich Server URL')
    parser.add_argument('--api-key', required=True, 
                       help='Immich API Key')
    parser.add_argument('--takeout-path', required=True, 
                       help='Path to Google Photos Takeout folder')
    parser.add_argument('--max-workers', type=int, default=10, 
                       help='Number of parallel workers')
    parser.add_argument('--batch-size', type=int, default=100, 
                       help='Batch size for processing')
    parser.add_argument('--timeout', type=int, default=300, 
                       help='Timeout for HTTP requests in seconds')
    
    args = parser.parse_args()
    
    # Create configuration
    config = Config(
        immich_url=args.immich_url,
        immich_api_key=args.api_key,
        takeout_path=args.takeout_path,
        max_workers=args.max_workers,
        batch_size=args.batch_size,
        timeout=args.timeout,
        dry_run=False
    )
    
    # Validation
    if not os.path.exists(config.takeout_path):
        logger.error(f"Takeout path does not exist: {config.takeout_path}")
        return 1
    
    if not config.immich_api_key:
        logger.error("API key is required")
        return 1
    
    # Start migration
    try:
        processor = GooglePhotosProcessor(config)
        processor.process_takeout(config.takeout_path)
        return 0
    except KeyboardInterrupt:
        logger.info("Migration cancelled by user")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
