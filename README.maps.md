# UDMF Map Support
*Auto-generated on 2026-05-03*

## Supported Properties

### Vertices
- `x`
- `y`

### Linedefs
- `v1`
- `v2`
- `sidefront`
- `sideback`
- `blocking`
- `twosided`
- `special`
- `arg0`
- `arg1`
- `arg2`
- `arg3`
- `arg4`

### Sidedefs
- `sector`
- `texturemiddle`
- `texturebottom`
- `offsetx_top`
- `offsety_top`
- `offsetx_middle`
- `offsety_middle`
- `offsetx_bottom`
- `offsety_bottom`
- `scalex_top`
- `scaley_top`
- `scalex_middle`
- `scaley_middle`
- `scalex_bottom`
- `scaley_bottom`

### Sectors
- `heightfloor`
- `texturefloor`
- `heightceiling`
- `xscalefloor`
- `yscalefloor`
- `xscaleceiling`
- `yscaleceiling`
- `xpanningfloor`
- `ypanningfloor`
- `xpanningceiling`
- `ypanningceiling`
- `rotationfloor`
- `rotationceiling`
- `id`
- `textureceiling`

### Things
- `x`
- `y`
- `height`
- `z`
- `angle`
- `type`
- `id`

## Supported Linedef Specials

| Number | Name | Description |
|--------|------|-------------|
| 9 | Line_Horizon | Extends sector floor/ceiling to visual infinity for outdoor/skybox areas |
| 160 | Sector_Set3DFloor | Creates a 3D floor from a control sector |

## Notes
- Properties not listed above are not supported
- Position values are scaled by `RendererMain.MasterScale`
- Linedef specials not listed above will generate a warning
