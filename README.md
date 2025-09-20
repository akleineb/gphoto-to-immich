# Google Photos to Immich Migration

A simple Python script that migrates your Google Photos Takeout data to Immich. The tool is vibe coded and designed to efficiently process large amounts of images and videos.

## What the tool does

The script goes through your Google Photos Takeout data (unpacked) and:
- Uploads all images and videos to Immich
- Creates albums from your Google Photos albums
- Transfers metadata like capture date and geo data
- Automatically detects duplicates
- Shows a detailed summary at the end

## Installation

```bash
# Install dependencies
make install
```

## Usage

### 1. Analyze the data
```bash
# See what would be migrated
make analyze
```

### 2. Start migration
```bash
# Perform actual migration
IMMICH_API_KEY="your-api-key" \
IMMICH_URL="http://your-immich-server:port" \
TAKEOUT_PATH="/path/to/your/takeout" \
make run
```

## What you need

- **API-Key**: With permissions for `asset.read`, `asset.update`, `asset.upload`, `album.create`, `album.read`, `album.update`, `albumAsset.create`
- **Google Photos Takeout**: Your exported Google Photos data (unzipped). Point the tool to the folder containing all the extracted files.

## Supported file formats

**Images:** JPG, JPEG, PNG, GIF, BMP, TIFF, HEIC, HEIF  
**Videos:** MP4, MOV, AVI, MKV, WEBM

## Metadata

The tool transfers:
- **Capture date** from Google Photos metadata
- **Geo data** (GPS coordinates) if available
- **Original filenames**
- **Album assignments**

## Log files

The script creates three log files:
- `gphoto_migration.log` - Main log with all details
- `album_creation.log` - Which albums were created
- `asset_album_assignment.log` - Which images were assigned to which albums

## Example output

```
======================================================================
🎉 MIGRATION SUCCESSFULLY COMPLETED
======================================================================
⏱️  Total time: 45.2 seconds (0.8 minutes)
📊 UPLOAD STATISTICS:
   📁 Total files found: 1250
   ✅ Successfully processed: 1250
   ❌ Failed: 0
   📈 Success rate: 100.0%

🔄 UPLOAD DETAILS:
   🆕 New uploads: 1200
   🔄 Duplicates found: 50

📚 ALBUM STATISTICS:
   🆕 New albums created: 3
   📁 Already existing albums: 0

🔧 METADATA STATISTICS:
   🔄 Metadata updated: 25
   ✅ Metadata already correct: 1225

======================================================================
📚 NEW ALBUMS CREATED
======================================================================
   1. Example Album
      ID: abc123-def456-ghi789
   2. 2022 - Another Album
      ID: xyz789-uvw456-rst123
   3. 2023 - Important Album
      ID: mno345-pqr678-stu901
======================================================================
```

## Common problems
**API errors:** Check if your API key has the correct permissions.

**Slow uploads:** The script uses 10 parallel workers. For very large collections, you can adjust this in `gphoto_to_immich.py`.

## Technical details

- **Dependencies:** Only `requests` and `urllib3`
- **Performance:** Efficiently processes 50,000+ files
- **Thread-safe:** Multiple workers without conflicts