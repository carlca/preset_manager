#!/usr/bin/env python3
"""
Example usage script for the Plugin Metadata Reader
Demonstrates how to scan for and read metadata from audio plugins.
"""

import json
import sys
from pathlib import Path
from typing import Optional, List, Dict
import argparse

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from plugin_metadata_reader import (
    PluginScanner,
    PluginMetadata,
    PluginFormat,
    PluginType
)

# Import Windows-specific DLL reader if on Windows
if sys.platform == 'win32':
    from dll_reader import VST2DllReader, scan_vst_dlls


def print_plugin_info(metadata: PluginMetadata, verbose: bool = False):
    """Pretty print plugin metadata"""
    print(f"\n{'='*60}")
    print(f"Plugin: {metadata.name}")
    print(f"Format: {metadata.format.value}")
    print(f"Path: {metadata.path}")
    
    if metadata.version:
        print(f"Version: {metadata.version}")
    if metadata.manufacturer:
        print(f"Manufacturer: {metadata.manufacturer}")
    if metadata.plugin_type:
        print(f"Type: {metadata.plugin_type.value}")
    if metadata.category:
        print(f"Category: {metadata.category}")
    
    if verbose:
        if metadata.description:
            print(f"Description: {metadata.description}")
        if metadata.unique_id:
            print(f"Unique ID: {metadata.unique_id}")
        if metadata.bundle_id:
            print(f"Bundle ID: {metadata.bundle_id}")
        if metadata.is_64bit is not None:
            print(f"64-bit: {metadata.is_64bit}")
        if metadata.supported_architectures:
            print(f"Architectures: {', '.join(metadata.supported_architectures)}")
        if metadata.additional_info:
            print(f"Additional Info: {json.dumps(metadata.additional_info, indent=2)}")


def scan_single_plugin(path: str, verbose: bool = False):
    """Scan a single plugin file or bundle"""
    scanner = PluginScanner()
    
    print(f"Scanning plugin: {path}")
    metadata = scanner.read_plugin(path)
    
    if metadata:
        print_plugin_info(metadata, verbose)
        return metadata
    else:
        print(f"Could not read metadata from: {path}")
        return None


def scan_directory(directory: str, format_filter: Optional[str] = None, verbose: bool = False):
    """Scan a directory for plugins"""
    scanner = PluginScanner()
    
    # Convert format string to enum if provided
    plugin_format = None
    if format_filter:
        try:
            plugin_format = PluginFormat[format_filter.upper()]
        except KeyError:
            print(f"Invalid format: {format_filter}")
            print(f"Valid formats: {', '.join([f.value for f in PluginFormat if f != PluginFormat.UNKNOWN])}")
            return []
    
    print(f"Scanning directory: {directory}")
    if plugin_format:
        print(f"Filter: {plugin_format.value} plugins only")
    
    plugins = scanner.scan_directory(directory, plugin_format)
    
    print(f"\nFound {len(plugins)} plugin(s)")
    
    for plugin in plugins:
        print_plugin_info(plugin, verbose)
    
    return plugins


def scan_default_locations(verbose: bool = False):
    """Scan all default plugin locations on the system"""
    scanner = PluginScanner()
    
    print("Scanning default plugin locations...")
    print(f"Operating System: {sys.platform}")
    
    default_paths = scanner.get_default_plugin_paths()
    
    print("\nDefault paths being scanned:")
    for format_type, paths in default_paths.items():
        if paths:  # Skip None values (e.g., AU on Windows)
            print(f"\n{format_type.value}:")
            for path in paths:
                exists = Path(path).exists()
                status = "✓" if exists else "✗"
                print(f"  {status} {path}")
    
    print("\n" + "="*60)
    
    all_plugins = scanner.scan_default_locations()
    
    total_count = 0
    for format_type, plugins in all_plugins.items():
        if plugins:
            print(f"\n{format_type.value} Plugins: {len(plugins)}")
            total_count += len(plugins)
            
            # Show first few plugins of each type
            for plugin in plugins[:3 if not verbose else None]:
                print_plugin_info(plugin, verbose)
            
            if len(plugins) > 3 and not verbose:
                print(f"  ... and {len(plugins) - 3} more")
    
    print(f"\n{'='*60}")
    print(f"Total plugins found: {total_count}")
    
    return all_plugins


def export_to_json(plugins: List[PluginMetadata], output_file: str):
    """Export plugin metadata to JSON file"""
    data = [plugin.to_dict() for plugin in plugins]
    
    with open(output_file, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"\nExported {len(plugins)} plugin(s) to: {output_file}")


def export_to_csv(plugins: List[PluginMetadata], output_file: str):
    """Export plugin metadata to CSV file"""
    import csv
    
    if not plugins:
        print("No plugins to export")
        return
    
    # Define CSV columns
    fieldnames = [
        'name', 'format', 'path', 'version', 'manufacturer',
        'plugin_type', 'category', 'description', 'unique_id',
        'bundle_id', 'is_64bit'
    ]
    
    with open(output_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for plugin in plugins:
            row = plugin.to_dict()
            # Flatten nested values
            for key in fieldnames:
                if key not in row:
                    row[key] = ''
            writer.writerow(row)
    
    print(f"\nExported {len(plugins)} plugin(s) to: {output_file}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Scan and read metadata from audio plugins (VST, VST3, AU, CLAP)'
    )
    
    parser.add_argument(
        'action',
        choices=['scan', 'scan-dir', 'scan-default', 'test'],
        help='Action to perform'
    )
    
    parser.add_argument(
        '--path', '-p',
        help='Path to plugin file or directory'
    )
    
    parser.add_argument(
        '--format', '-f',
        choices=['VST', 'VST3', 'AU', 'CLAP'],
        help='Filter by plugin format'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Show detailed information'
    )
    
    parser.add_argument(
        '--export-json',
        help='Export results to JSON file'
    )
    
    parser.add_argument(
        '--export-csv',
        help='Export results to CSV file'
    )
    
    args = parser.parse_args()
    
    plugins = []
    
    if args.action == 'scan':
        if not args.path:
            print("Error: --path is required for 'scan' action")
            sys.exit(1)
        
        metadata = scan_single_plugin(args.path, args.verbose)
        if metadata:
            plugins = [metadata]
    
    elif args.action == 'scan-dir':
        if not args.path:
            print("Error: --path is required for 'scan-dir' action")
            sys.exit(1)
        
        plugins = scan_directory(args.path, args.format, args.verbose)
    
    elif args.action == 'scan-default':
        all_plugins = scan_default_locations(args.verbose)
        # Flatten the results
        for format_plugins in all_plugins.values():
            plugins.extend(format_plugins)
    
    elif args.action == 'test':
        # Run test scan with sample paths
        print("Running test scan...")
        scanner = PluginScanner()
        
        # Test with some common plugin paths
        test_paths = []
        
        if sys.platform == 'darwin':  # macOS
            test_paths = [
                "/Library/Audio/Plug-Ins/VST3/",
                "/Library/Audio/Plug-Ins/Components/",
                "~/Library/Audio/Plug-Ins/VST3/"
            ]
        elif sys.platform == 'win32':  # Windows
            test_paths = [
                "C:\\Program Files\\Common Files\\VST3",
                "C:\\Program Files\\VSTPlugins"
            ]
        
        for test_path in test_paths:
            expanded_path = Path(test_path).expanduser()
            if expanded_path.exists():
                print(f"\nTesting: {test_path}")
                test_plugins = scanner.scan_directory(str(expanded_path))
                plugins.extend(test_plugins)
                print(f"Found {len(test_plugins)} plugin(s)")
    
    # Export results if requested
    if args.export_json and plugins:
        export_to_json(plugins, args.export_json)
    
    if args.export_csv and plugins:
        export_to_csv(plugins, args.export_csv)
    
    if not plugins:
        print("\nNo plugins found.")
    else:
        print(f"\nTotal plugins processed: {len(plugins)}")


if __name__ == "__main__":
    # If no arguments provided, show help
    if len(sys.argv) == 1:
        print("Plugin Metadata Reader - Example Usage\n")
        print("Examples:")
        print("  # Scan a single plugin:")
        print("  python example_usage.py scan --path /path/to/plugin.vst3")
        print()
        print("  # Scan a directory for all plugins:")
        print("  python example_usage.py scan-dir --path /Library/Audio/Plug-Ins/VST3")
        print()
        print("  # Scan only VST3 plugins in a directory:")
        print("  python example_usage.py scan-dir --path /path/to/plugins --format VST3")
        print()
        print("  # Scan all default plugin locations:")
        print("  python example_usage.py scan-default")
        print()
        print("  # Export results to JSON:")
        print("  python example_usage.py scan-default --export-json plugins.json")
        print()
        print("  # Show detailed information:")
        print("  python example_usage.py scan-default --verbose")
        print()
        print("Run 'python example_usage.py -h' for full help")
    else:
        main()