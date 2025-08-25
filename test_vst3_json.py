#!/usr/bin/env python3
"""
Test script for VST3 moduleinfo.json parsing
Handles common issues in VST3 metadata files including:
- Trailing commas
- Spaces in JSON keys
- Control characters
- Mixed formatting
"""

import sys
import json
import re
from pathlib import Path
from typing import Dict, Any, Optional

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from plugin_metadata_reader import PluginScanner, PluginFormat
from json_utils import JSONParser, read_plugin_json


def fix_vst3_json(content: str) -> str:
    """
    Fix common issues in VST3 moduleinfo.json files
    
    Args:
        content: Raw JSON string content
        
    Returns:
        Fixed JSON string
    """
    # Remove trailing commas before } or ]
    # Multiple passes to handle nested cases
    prev_content = None
    while prev_content != content:
        prev_content = content
        content = re.sub(r',(\s*[}\]])', r'\1', content)
    
    # Remove C-style comments
    content = re.sub(r'//.*?$', '', content, flags=re.MULTILINE)
    content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
    
    # Handle control characters in string values
    # This is tricky because we need to preserve the JSON structure
    lines = content.split('\n')
    fixed_lines = []
    
    for line in lines:
        # Check if line contains a string value
        if '": "' in line or '":"' in line:
            # Try to fix potential control character issues
            # by ensuring proper escaping
            line = line.replace('\t', '\\t')
            line = line.replace('\r', '\\r')
            # Don't replace \n as it's our line separator
        fixed_lines.append(line)
    
    content = '\n'.join(fixed_lines)
    
    return content


def parse_vst3_json(file_path: Path) -> Optional[Dict[str, Any]]:
    """
    Parse a VST3 moduleinfo.json file with enhanced error handling
    
    Args:
        file_path: Path to the moduleinfo.json file
        
    Returns:
        Parsed JSON data or None if parsing fails
    """
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading file {file_path}: {e}")
        return None
    
    # Try standard JSON first
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass
    
    # Try fixing common issues
    fixed_content = fix_vst3_json(content)
    
    try:
        return json.loads(fixed_content)
    except json.JSONDecodeError as e:
        # Show the specific issue for debugging
        lines = fixed_content.split('\n')
        if e.lineno and e.lineno <= len(lines):
            print(f"  Problem at line {e.lineno}: {lines[e.lineno-1][:80]}")
            print(f"  Error: {e.msg}")
        return None


def test_specific_plugin(plugin_path: Path):
    """Test a specific VST3 plugin"""
    print(f"\nTesting: {plugin_path.name}")
    print("-" * 40)
    
    if not plugin_path.exists():
        print(f"  ✗ Plugin not found")
        return False
    
    # Look for moduleinfo.json
    moduleinfo_paths = [
        plugin_path / "Contents" / "Resources" / "moduleinfo.json",
        plugin_path / "Contents" / "moduleinfo.json"
    ]
    
    moduleinfo_found = False
    parse_success = False
    
    for moduleinfo_path in moduleinfo_paths:
        if moduleinfo_path.exists():
            moduleinfo_found = True
            print(f"  ℹ Found moduleinfo.json at: {moduleinfo_path.relative_to(plugin_path)}")
            
            # Try our custom parser
            data = parse_vst3_json(moduleinfo_path)
            
            if data:
                parse_success = True
                print(f"  ✓ Successfully parsed JSON")
                
                # Extract key information
                name = data.get("Name", "Unknown")
                version = data.get("Version", "Unknown")
                
                # Handle nested vendor info
                vendor = "Unknown"
                if "Factory Info" in data and isinstance(data["Factory Info"], dict):
                    vendor = data["Factory Info"].get("Vendor", vendor)
                elif "Vendor" in data:
                    vendor = data["Vendor"]
                
                print(f"    Name: {name}")
                print(f"    Version: {version}")
                print(f"    Vendor: {vendor}")
                
                # Check for classes
                if "Classes" in data and isinstance(data["Classes"], list):
                    print(f"    Classes: {len(data['Classes'])} defined")
            else:
                print(f"  ✗ Failed to parse JSON")
                
                # Try to show a sample of the problematic content
                try:
                    with open(moduleinfo_path, 'r', encoding='utf-8', errors='replace') as f:
                        content = f.read()
                        # Show first few lines
                        lines = content.split('\n')[:10]
                        print("  First 10 lines of file:")
                        for i, line in enumerate(lines, 1):
                            print(f"    {i:2}: {line[:70]}")
                except:
                    pass
            break
    
    if not moduleinfo_found:
        print(f"  ℹ No moduleinfo.json found")
        return True  # Not an error, some VST3s don't have it
    
    return parse_success


def scan_vst3_plugins():
    """Scan all VST3 plugins and test JSON parsing"""
    
    print("=" * 60)
    print("VST3 moduleinfo.json Parser Test")
    print("=" * 60)
    
    # VST3 plugin directories
    vst3_dirs = [
        Path("/Library/Audio/Plug-Ins/VST3"),
        Path.home() / "Library/Audio/Plug-Ins/VST3"
    ]
    
    # Problematic plugins from the error messages
    problematic_plugins = [
        "Bark of Dog 3.vst3",
        "Airwindows Consolidated.vst3",
        "Ripple Phaser.vst3",
        "MoonEcho.vst3",
        "OneShot.vst3",
        "Current.vst3",
        "Lines.vst3",
        "Cluster Delay.vst3",
        "Hybrid Filter.vst3",
        "Tomofon.vst3",
        "FKFX Influx 15.vst3"
    ]
    
    # First test the problematic ones
    print("\nTesting Known Problematic Plugins:")
    print("=" * 60)
    
    problematic_found = 0
    problematic_success = 0
    
    for vst3_dir in vst3_dirs:
        if not vst3_dir.exists():
            continue
            
        for plugin_name in problematic_plugins:
            plugin_path = vst3_dir / plugin_name
            if plugin_path.exists():
                problematic_found += 1
                if test_specific_plugin(plugin_path):
                    problematic_success += 1
    
    # Then do a full scan
    print("\n" + "=" * 60)
    print("Full VST3 Directory Scan:")
    print("=" * 60)
    
    total_vst3 = 0
    total_with_json = 0
    total_parsed = 0
    failed_plugins = []
    
    for vst3_dir in vst3_dirs:
        if not vst3_dir.exists():
            print(f"\n✗ Directory not found: {vst3_dir}")
            continue
        
        print(f"\n✓ Scanning: {vst3_dir}")
        vst3_files = list(vst3_dir.glob("*.vst3"))
        
        if not vst3_files:
            print("  No VST3 plugins found")
            continue
        
        print(f"  Found {len(vst3_files)} VST3 plugin(s)")
        
        for vst3_file in vst3_files:
            total_vst3 += 1
            
            # Check for moduleinfo.json
            moduleinfo_paths = [
                vst3_file / "Contents" / "Resources" / "moduleinfo.json",
                vst3_file / "Contents" / "moduleinfo.json"
            ]
            
            has_json = False
            for path in moduleinfo_paths:
                if path.exists():
                    has_json = True
                    total_with_json += 1
                    
                    # Try to parse it
                    data = parse_vst3_json(path)
                    if data:
                        total_parsed += 1
                    else:
                        failed_plugins.append(vst3_file.name)
                    break
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total VST3 plugins found: {total_vst3}")
    print(f"Plugins with moduleinfo.json: {total_with_json}")
    print(f"Successfully parsed: {total_parsed}")
    print(f"Failed to parse: {total_with_json - total_parsed}")
    
    if problematic_found > 0:
        print(f"\nProblematic plugins tested: {problematic_found}")
        print(f"Successfully fixed: {problematic_success}")
    
    if failed_plugins:
        print(f"\nFailed plugins ({len(failed_plugins)}):")
        for plugin in failed_plugins[:10]:  # Show first 10
            print(f"  - {plugin}")
        if len(failed_plugins) > 10:
            print(f"  ... and {len(failed_plugins) - 10} more")
    
    success_rate = (total_parsed / total_with_json * 100) if total_with_json > 0 else 0
    print(f"\nSuccess rate: {success_rate:.1f}%")
    
    if success_rate == 100:
        print("\n✓ All VST3 moduleinfo.json files parsed successfully!")
    elif success_rate >= 90:
        print("\n⚠ Most VST3 files parsed successfully, some issues remain")
    else:
        print("\n✗ Significant parsing issues detected")
    
    return total_parsed, total_with_json - total_parsed


def main():
    """Main test function"""
    
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Test VST3 moduleinfo.json parsing'
    )
    parser.add_argument(
        '--plugin',
        help='Test a specific plugin by name or path'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Show detailed output'
    )
    
    args = parser.parse_args()
    
    if args.plugin:
        # Test specific plugin
        plugin_path = Path(args.plugin)
        if not plugin_path.exists():
            # Try to find it in standard locations
            for base_dir in ["/Library/Audio/Plug-Ins/VST3", 
                           str(Path.home() / "Library/Audio/Plug-Ins/VST3")]:
                test_path = Path(base_dir) / args.plugin
                if test_path.exists():
                    plugin_path = test_path
                    break
        
        if plugin_path.exists():
            success = test_specific_plugin(plugin_path)
            sys.exit(0 if success else 1)
        else:
            print(f"Plugin not found: {args.plugin}")
            sys.exit(1)
    else:
        # Run full scan
        parsed, failed = scan_vst3_plugins()
        
        # Also test with the main scanner
        print("\n" + "=" * 60)
        print("Testing with Main Plugin Scanner")
        print("=" * 60)
        
        scanner = PluginScanner()
        vst3_plugins = scanner.scan_directory("/Library/Audio/Plug-Ins/VST3", PluginFormat.VST3)
        
        print(f"Main scanner found {len(vst3_plugins)} VST3 plugins")
        
        # Return appropriate exit code
        sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()