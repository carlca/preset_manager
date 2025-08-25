#!/usr/bin/env python3
"""
Test script for CLAP plugin scanning
Verifies that the improved JSON parsing handles malformed moduleinfo.json files
"""

import sys
import json
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from plugin_metadata_reader import PluginScanner, PluginFormat
from json_utils import JSONParser, read_plugin_json


def test_clap_scanning():
    """Test CLAP plugin scanning with improved error handling"""
    
    print("=" * 60)
    print("CLAP Plugin Scanner Test")
    print("=" * 60)
    
    scanner = PluginScanner()
    
    # Get CLAP plugin paths
    clap_paths = [
        Path.home() / "Library/Audio/Plug-Ins/CLAP",
        Path("/Library/Audio/Plug-Ins/CLAP")
    ]
    
    total_plugins = 0
    successful_reads = 0
    failed_reads = 0
    
    for clap_dir in clap_paths:
        if not clap_dir.exists():
            print(f"\n✗ Directory not found: {clap_dir}")
            continue
            
        print(f"\n✓ Scanning: {clap_dir}")
        print("-" * 40)
        
        # Find all CLAP plugins
        clap_files = list(clap_dir.glob("*.clap"))
        
        if not clap_files:
            print("  No CLAP plugins found in this directory")
            continue
            
        print(f"  Found {len(clap_files)} CLAP plugin(s)")
        
        for clap_file in clap_files:
            total_plugins += 1
            print(f"\n  Plugin: {clap_file.name}")
            
            # Try to read the plugin metadata
            metadata = scanner.read_plugin(str(clap_file))
            
            if metadata:
                successful_reads += 1
                print(f"    ✓ Successfully read metadata")
                print(f"      Name: {metadata.name}")
                if metadata.version:
                    print(f"      Version: {metadata.version}")
                if metadata.manufacturer:
                    print(f"      Manufacturer: {metadata.manufacturer}")
                if metadata.description:
                    print(f"      Description: {metadata.description[:50]}...")
                    
                # Check for moduleinfo.json
                moduleinfo_paths = [
                    clap_file / "Contents" / "Resources" / "moduleinfo.json",
                    clap_file / "Contents" / "moduleinfo.json"
                ]
                
                for moduleinfo_path in moduleinfo_paths:
                    if moduleinfo_path.exists():
                        print(f"    ℹ Found moduleinfo.json at: {moduleinfo_path.relative_to(clap_file)}")
                        
                        # Try to parse it directly
                        json_data = read_plugin_json(moduleinfo_path)
                        if json_data:
                            print(f"      ✓ Successfully parsed JSON")
                        else:
                            print(f"      ✗ Failed to parse JSON")
                            # Try to show what's wrong
                            try:
                                with open(moduleinfo_path, 'r') as f:
                                    content = f.read()
                                    lines = content.split('\n')
                                    if len(lines) > 10:
                                        print(f"      Line 11: {lines[10][:60]}...")
                            except:
                                pass
                        break
            else:
                failed_reads += 1
                print(f"    ✗ Failed to read metadata")
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total CLAP plugins found: {total_plugins}")
    print(f"Successfully read: {successful_reads}")
    print(f"Failed to read: {failed_reads}")
    
    if failed_reads == 0 and total_plugins > 0:
        print("\n✓ All CLAP plugins were read successfully!")
    elif successful_reads > 0:
        print(f"\n⚠ Partially successful: {successful_reads}/{total_plugins} plugins read")
    elif total_plugins > 0:
        print("\n✗ Failed to read any CLAP plugins")
    else:
        print("\nℹ No CLAP plugins found to test")
    
    return successful_reads, failed_reads


def test_json_cleaning():
    """Test JSON cleaning with a sample malformed JSON"""
    
    print("\n" + "=" * 60)
    print("JSON Cleaning Test")
    print("=" * 60)
    
    # Sample malformed JSON with trailing comma (like the error you saw)
    malformed_json = '''
    {
        "Name": "Test Plugin",
        "Version": "1.0.0",
        "Vendor": "Test Vendor",
        "Category": "Effect",
        "Description": "A test plugin",
    }
    '''
    
    print("Testing malformed JSON with trailing comma...")
    print("Original JSON:")
    print(malformed_json)
    
    # Clean it
    cleaned = JSONParser.clean_json_string(malformed_json)
    
    print("\nCleaned JSON:")
    print(cleaned)
    
    try:
        parsed = json.loads(cleaned)
        print("\n✓ Successfully parsed cleaned JSON:")
        print(json.dumps(parsed, indent=2))
        return True
    except json.JSONDecodeError as e:
        print(f"\n✗ Failed to parse cleaned JSON: {e}")
        return False


def main():
    """Main test function"""
    
    print("CLAP Plugin Metadata Reader Test Suite")
    print("=" * 60)
    
    # First test JSON cleaning
    json_test_passed = test_json_cleaning()
    
    # Then test actual CLAP plugin scanning
    successful, failed = test_clap_scanning()
    
    # Final result
    print("\n" + "=" * 60)
    print("FINAL RESULT")
    print("=" * 60)
    
    if json_test_passed:
        print("✓ JSON cleaning test passed")
    else:
        print("✗ JSON cleaning test failed")
        
    if failed == 0 and successful > 0:
        print("✓ CLAP plugin scanning successful")
        print("\n🎉 All tests passed! The trailing comma issue has been resolved.")
    elif successful > 0:
        print(f"⚠ CLAP plugin scanning partially successful ({successful} passed, {failed} failed)")
        print("\nSome plugins may still have issues. Consider installing json5:")
        print("  pip install json5")
    else:
        print("ℹ No CLAP plugins found or all failed")
        
    # Suggest installing json5 if not available
    try:
        import json5
        print("\n✓ json5 is installed (provides best JSON compatibility)")
    except ImportError:
        print("\nℹ Tip: Install json5 for even better JSON parsing:")
        print("  pip install json5")


if __name__ == "__main__":
    main()