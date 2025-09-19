#!/bin/bash

# PK3 Builder for RealmChasers-PK3
# This script creates a PK3 file from the contents of the source/ directory

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_DIR="$SCRIPT_DIR/in"
OUTPUT_DIR="$SCRIPT_DIR/out"
PK3_OUTPUT="$OUTPUT_DIR/realmchasers.ipk3"
README_PATH="$SCRIPT_DIR/README.maps.md"

echo -e "${GREEN}=== RealmChasers PK3 Builder ===${NC}"
echo "Building from: $SOURCE_DIR"
echo "Output to: $OUTPUT_DIR"
echo ""

# Check if source directory exists
if [ ! -d "$SOURCE_DIR" ]; then
    echo -e "${RED}Error: Source directory not found at $SOURCE_DIR${NC}"
    echo "Please ensure the in/ directory exists with PK3 contents"
    exit 1
fi

# Check if source directory has content
if [ -z "$(ls -A "$SOURCE_DIR" 2>/dev/null)" ]; then
    echo -e "${YELLOW}Warning: Source directory is empty${NC}"
    echo "No files to package into PK3"
    exit 1
fi

# Create output directory if it doesn't exist
mkdir -p "$OUTPUT_DIR"

# Remove old PK3 if it exists
if [ -f "$PK3_OUTPUT" ]; then
    echo "Removing existing PK3..."
    rm -f "$PK3_OUTPUT"
fi

# Count source files
FILE_COUNT=$(find "$SOURCE_DIR" -type f ! -name ".*" ! -name "*.meta" ! -name "*.json" | wc -l | xargs)
echo -e "${BLUE}Found $FILE_COUNT files to package${NC}"

# Create PK3 (ZIP archive)
echo -e "${YELLOW}Creating PK3 archive...${NC}"

cd "$SOURCE_DIR"
if command -v zip &> /dev/null; then
    # Create ZIP excluding unwanted files
    zip -r "$PK3_OUTPUT" . \
        -x "*.json" \
        -x "*.meta" \
        -x ".DS_Store" \
        -x ".*" \
        -x "Thumbs.db" \
        >/dev/null 2>&1
    
    if [ $? -eq 0 ]; then
        # Get file size
        PK3_SIZE=$(ls -lh "$PK3_OUTPUT" | awk '{print $5}')
        echo -e "${GREEN}✓ Successfully created PK3${NC}"
        echo ""
        echo "  File: $PK3_OUTPUT"
        echo "  Size: $PK3_SIZE"
        echo "  Files: $FILE_COUNT"
    else
        echo -e "${RED}Error: Failed to create PK3 archive${NC}"
        exit 1
    fi
else
    echo -e "${RED}Error: 'zip' command not found${NC}"
    echo "Please install zip to create PK3 archives"
    echo "  macOS: Should be pre-installed"
    echo "  Linux: sudo apt-get install zip"
    exit 1
fi

cd "$SCRIPT_DIR"

echo ""
echo -e "${GREEN}=== Build Complete ===${NC}"
echo ""
echo "Next steps:"
echo "  1. Test in GZDoom: gzdoom -file $PK3_OUTPUT"
echo "  2. Load in Ultimate Doom Builder as resource"
echo "  3. Commit and push: git add -A && git commit -m 'Updated PK3' && git push"