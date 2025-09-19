# PK3 Texture Export Directory

This directory contains textures exported from Realm Chasers for use in Ultimate Doom Builder and GZDoom.

## Directory Structure

```
PK3/
├── textures/       # All textures (walls, floors, ceilings for UDMF maps)
├── TEXTURES.txt    # Texture definitions (auto-generated)
└── texture_manifest.json  # Export manifest (not included in PK3)
```

## Usage

### Building the PK3

From the project root, run:
```bash
./build_pk3_textures.sh
```

This will:
1. Export texture list from Unity Addressables
2. Copy textures to this folder structure
3. Create a `realmchasers.pk3` file

### In Ultimate Doom Builder

1. Go to Edit → Game Configurations
2. Select your configuration
3. Go to Resources tab
4. Add Resource → From PK3/PK7
5. Browse to `realmchasers.pk3`
6. Click OK

Now all Realm Chasers textures will be available in the texture browser when mapping.

## Texture Naming

- **Textures**: All textures use their original names and are available in the texture browser
- Can be used for walls, floors, and ceilings in UDMF maps

## Notes

- Textures are copied from Unity project, preserving original resolution
- The `texture_manifest.json` contains metadata but is not included in the PK3
- PK3 files are just renamed ZIP archives
- Maximum texture name length in classic Doom is 8 characters, but UDMF supports longer names