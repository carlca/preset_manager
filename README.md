# Plugin Metadata Reader

A cross-platform Python library for reading metadata from audio plugin formats including VST, VST3, AU (Audio Units), and CLAP plugins. Works on macOS and Windows.

## Features

- **Multi-format support**: Read metadata from VST2, VST3, AU, and CLAP plugins
- **Cross-platform**: Works on macOS, Windows, and Linux
- **Comprehensive metadata extraction**: Plugin name, version, manufacturer, type, category, and more
- **Batch scanning**: Scan directories or default plugin locations
- **Export capabilities**: Export metadata to JSON or CSV formats
- **Pure Python**: Core functionality uses only Python standard library

## Installation

### Basic Installation

Clone the repository and install:

```bash
git clone <repository-url>
cd preset_manager
python -m pip install -r requirements.txt
```

### Minimal Installation (Standard Library Only)

The core functionality works with Python standard library only:

```bash
python example_usage.py --help
```

### Optional Dependencies

For enhanced Windows DLL parsing:
```bash
pip install pefile
```

## Quick Start

### Scan a Single Plugin

```python
from src.plugin_metadata_reader import PluginScanner

scanner = PluginScanner()
metadata = scanner.read_plugin("/Library/Audio/Plug-Ins/VST3/MyPlugin.vst3")

if metadata:
    print(f"Plugin: {metadata.name}")
    print(f"Version: {metadata.version}")
    print(f"Manufacturer: {metadata.manufacturer}")
```

### Scan Default Plugin Locations

```python
scanner = PluginScanner()
all_plugins = scanner.scan_default_locations()

for format_type, plugins in all_plugins.items():
    print(f"\n{format_type.value} Plugins: {len(plugins)}")
    for plugin in plugins:
        print(f"  - {plugin.name} v{plugin.version}")
```

## Command Line Usage

### Scan a Single Plugin
```bash
python example_usage.py scan --path /path/to/plugin.vst3
```

### Scan a Directory
```bash
python example_usage.py scan-dir --path /Library/Audio/Plug-Ins/VST3
```

### Scan with Format Filter
```bash
python example_usage.py scan-dir --path /path/to/plugins --format VST3
```

### Scan All Default Locations
```bash
python example_usage.py scan-default
```

### Export Results
```bash
# Export to JSON
python example_usage.py scan-default --export-json plugins.json

# Export to CSV
python example_usage.py scan-default --export-csv plugins.csv

# Verbose output
python example_usage.py scan-default --verbose
```

## Default Plugin Locations

### macOS
- **VST**: `~/Library/Audio/Plug-Ins/VST`, `/Library/Audio/Plug-Ins/VST`
- **VST3**: `~/Library/Audio/Plug-Ins/VST3`, `/Library/Audio/Plug-Ins/VST3`
- **AU**: `~/Library/Audio/Plug-Ins/Components`, `/Library/Audio/Plug-Ins/Components`
- **CLAP**: `~/Library/Audio/Plug-Ins/CLAP`, `/Library/Audio/Plug-Ins/CLAP`

### Windows
- **VST**: `C:\Program Files\VSTPlugins`, `C:\Program Files\Steinberg\VSTPlugins`
- **VST3**: `C:\Program Files\Common Files\VST3`
- **CLAP**: `C:\Program Files\Common Files\CLAP`

### Linux
- **VST**: `~/.vst`, `/usr/lib/vst`, `/usr/local/lib/vst`
- **VST3**: `~/.vst3`, `/usr/lib/vst3`, `/usr/local/lib/vst3`
- **CLAP**: `~/.clap`, `/usr/lib/clap`, `/usr/local/lib/clap`

## API Reference

### PluginMetadata Class

Container for plugin metadata with the following fields:

- `name`: Plugin name
- `format`: Plugin format (VST, VST3, AU, CLAP)
- `path`: File system path to the plugin
- `version`: Plugin version
- `manufacturer`: Plugin manufacturer/vendor
- `unique_id`: Unique plugin identifier
- `plugin_type`: Type (Effect, Instrument, MIDI Effect)
- `category`: Plugin category
- `description`: Plugin description
- `is_64bit`: Whether plugin is 64-bit
- `bundle_id`: Bundle identifier (macOS)
- `supported_architectures`: List of supported CPU architectures
- `additional_info`: Dictionary for extra metadata

### PluginScanner Class

Main class for scanning plugins:

```python
scanner = PluginScanner()

# Read a single plugin
metadata = scanner.read_plugin(plugin_path)

# Scan a directory
plugins = scanner.scan_directory(directory, format_filter=None)

# Get default plugin paths for the OS
paths = scanner.get_default_plugin_paths()

# Scan all default locations
all_plugins = scanner.scan_default_locations()

# Detect plugin format from file
format = scanner.detect_format(plugin_path)
```

## Metadata Extraction Details

### VST3 Plugins
- Reads `Info.plist` on macOS
- Parses `moduleinfo.json` when available
- Extracts bundle information
- Determines plugin type from category

### VST2 Plugins
- Reads bundle `Info.plist` on macOS
- Basic DLL parsing on Windows
- Attempts to detect VST signatures in binary

### Audio Units (macOS only)
- Reads `Info.plist` from component bundle
- Extracts AU-specific metadata
- Determines type from AU type codes
- Gets manufacturer and description from AudioComponents

### CLAP Plugins
- Reads `clap.json` manifest files
- Parses bundle information on macOS
- Supports both bundle and DLL formats

## Advanced Usage

### Custom Plugin Paths

```python
scanner = PluginScanner()

# Add custom paths to scan
custom_paths = [
    "/custom/path/to/plugins",
    "~/Documents/MyPlugins"
]

for path in custom_paths:
    plugins = scanner.scan_directory(path)
    print(f"Found {len(plugins)} plugins in {path}")
```

### Filter by Plugin Type

```python
# After scanning
all_plugins = scanner.scan_default_locations()

# Filter only instruments
instruments = []
for format_plugins in all_plugins.values():
    instruments.extend([
        p for p in format_plugins 
        if p.plugin_type == PluginType.INSTRUMENT
    ])

print(f"Found {len(instruments)} instrument plugins")
```

### Windows DLL Analysis

For detailed Windows VST2 DLL analysis:

```python
from src.dll_reader import VST2DllReader

reader = VST2DllReader("C:\\Program Files\\VSTPlugins\\MyPlugin.dll")
metadata = reader.read_metadata()

print(f"Is 64-bit: {metadata.get('is_64bit')}")
print(f"Is VST: {metadata.get('is_vst')}")
print(f"Version Info: {metadata.get('version_info')}")
```

## Limitations

1. **VST2 Metadata**: VST2 plugins don't have standardized metadata storage, so extraction is limited
2. **Binary Parsing**: Full binary parsing of plugins requires loading them, which this library doesn't do for safety
3. **Plugin Validation**: The library identifies plugins by file extension and basic signatures, not by loading them
4. **AU on Windows/Linux**: Audio Units are macOS-only
5. **CLAP Support**: CLAP is a newer format, metadata extraction depends on manifest files

## Contributing

Contributions are welcome! Areas for improvement:

- Enhanced Windows PE/DLL parsing
- Better VST2 metadata extraction
- Linux-specific enhancements
- Additional plugin format support
- GUI interface
- Plugin validation

## License

[Specify your license here]

## Acknowledgments

- VST is a trademark of Steinberg Media Technologies GmbH
- Audio Units is a technology by Apple Inc.
- CLAP (CLever Audio Plugin) is an open standard by Bitwig and u-he

## Troubleshooting

### Permission Errors
Some system plugin directories require elevated permissions. Run with appropriate permissions or scan user directories.

### Missing Plugins
Ensure plugins are installed in standard locations or specify custom paths.

### Windows DLL Errors
Install `pefile` for better Windows DLL support:
```bash
pip install pefile
```

### macOS Security
On macOS 10.15+, you may need to grant terminal/Python disk access permissions in System Preferences > Security & Privacy.