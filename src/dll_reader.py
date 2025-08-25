"""
Windows DLL Reader for VST2 Plugins
Provides functionality to read metadata from Windows DLL files for VST2 plugins.
"""

import struct
import os
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime


class PEHeader:
    """Parser for Windows Portable Executable (PE) headers"""
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.file_size = os.path.getsize(file_path)
        self.pe_header_offset = None
        self.is_64bit = False
        self.sections = []
        self.version_info = {}
        
    def read(self) -> Dict[str, Any]:
        """Read PE headers and extract metadata"""
        try:
            with open(self.file_path, 'rb') as f:
                # Check DOS header
                dos_header = f.read(2)
                if dos_header != b'MZ':
                    return None
                    
                # Get PE header offset
                f.seek(0x3C)
                self.pe_header_offset = struct.unpack('<I', f.read(4))[0]
                
                # Read PE signature
                f.seek(self.pe_header_offset)
                pe_sig = f.read(4)
                if pe_sig != b'PE\x00\x00':
                    return None
                    
                # Read COFF header
                machine_type = struct.unpack('<H', f.read(2))[0]
                self.is_64bit = machine_type == 0x8664  # AMD64
                
                num_sections = struct.unpack('<H', f.read(2))[0]
                timestamp = struct.unpack('<I', f.read(4))[0]
                
                # Skip to optional header
                f.seek(self.pe_header_offset + 24)
                magic = struct.unpack('<H', f.read(2))[0]
                
                if magic == 0x10b:  # PE32
                    self.is_64bit = False
                elif magic == 0x20b:  # PE32+
                    self.is_64bit = True
                    
                # Try to find version info in resources
                self._read_version_resources(f)
                
                return {
                    'is_64bit': self.is_64bit,
                    'machine_type': self._get_machine_name(machine_type),
                    'timestamp': datetime.fromtimestamp(timestamp).isoformat() if timestamp else None,
                    'file_size': self.file_size,
                    'version_info': self.version_info
                }
                
        except Exception as e:
            print(f"Error reading PE headers: {e}")
            return None
            
    def _get_machine_name(self, machine_type: int) -> str:
        """Convert machine type to readable name"""
        machines = {
            0x014c: 'x86',
            0x0200: 'Intel Itanium',
            0x8664: 'x64 (AMD64)',
            0xAA64: 'ARM64',
            0x01c0: 'ARM',
            0x01c4: 'ARMv7'
        }
        return machines.get(machine_type, f'Unknown ({hex(machine_type)})')
        
    def _read_version_resources(self, f):
        """Attempt to read version information from resources"""
        # This is a simplified version - full resource parsing is complex
        try:
            # Search for version info patterns in the file
            f.seek(0)
            data = f.read()
            
            # Look for common version patterns
            patterns = [
                b'FileVersion\x00',
                b'ProductVersion\x00',
                b'CompanyName\x00',
                b'FileDescription\x00',
                b'ProductName\x00'
            ]
            
            for pattern in patterns:
                index = data.find(pattern)
                if index != -1:
                    # Try to extract the string value after the pattern
                    start = index + len(pattern)
                    # Skip null bytes
                    while start < len(data) and data[start] == 0:
                        start += 1
                    # Read until next null byte sequence
                    end = start
                    while end < len(data) - 1:
                        if data[end] == 0 and data[end + 1] == 0:
                            break
                        end += 1
                    
                    if end > start:
                        try:
                            value = data[start:end].decode('utf-16-le', errors='ignore').strip('\x00')
                            if value and len(value) < 256:  # Sanity check
                                key = pattern.decode('ascii', errors='ignore').strip('\x00')
                                self.version_info[key] = value
                        except:
                            pass
                            
        except Exception as e:
            print(f"Error reading version resources: {e}")


class VST2DllReader:
    """Specialized reader for VST2 DLL files"""
    
    VST_MAGIC = 0x56737450  # 'VstP' in little-endian
    
    def __init__(self, dll_path: str):
        self.dll_path = dll_path
        self.pe_reader = PEHeader(dll_path)
        
    def read_metadata(self) -> Dict[str, Any]:
        """Read VST2-specific metadata from DLL"""
        metadata = {
            'path': self.dll_path,
            'filename': Path(self.dll_path).name,
            'is_vst': False
        }
        
        # Read PE headers
        pe_info = self.pe_reader.read()
        if pe_info:
            metadata.update(pe_info)
            
        # Try to detect VST2 signature
        if self._check_vst_signature():
            metadata['is_vst'] = True
            metadata['plugin_type'] = 'VST2'
            
        # Extract additional VST info if possible
        vst_info = self._extract_vst_info()
        if vst_info:
            metadata.update(vst_info)
            
        return metadata
        
    def _check_vst_signature(self) -> bool:
        """Check if DLL contains VST2 signature"""
        try:
            with open(self.dll_path, 'rb') as f:
                data = f.read()
                
                # Look for VST-specific exports
                vst_exports = [
                    b'VSTPluginMain',
                    b'main',
                    b'GetPluginFactory'  # Some VST2.4 plugins
                ]
                
                for export in vst_exports:
                    if export in data:
                        return True
                        
                # Look for VST magic number
                if struct.pack('<I', self.VST_MAGIC) in data:
                    return True
                    
        except Exception as e:
            print(f"Error checking VST signature: {e}")
            
        return False
        
    def _extract_vst_info(self) -> Dict[str, Any]:
        """Extract VST-specific information"""
        info = {}
        
        try:
            with open(self.dll_path, 'rb') as f:
                data = f.read()
                
                # Look for common VST2 effect categories
                categories = {
                    b'kPlugCategEffect': 'Effect',
                    b'kPlugCategSynth': 'Synth',
                    b'kPlugCategAnalysis': 'Analysis',
                    b'kPlugCategMastering': 'Mastering',
                    b'kPlugCategRoomFx': 'Room Effect',
                    b'kPlugCategRestoration': 'Restoration',
                    b'kPlugCategGenerator': 'Generator'
                }
                
                for cat_bytes, cat_name in categories.items():
                    if cat_bytes in data:
                        info['category'] = cat_name
                        break
                        
                # Try to find plugin name in strings
                # This is heuristic-based and may not always work
                name_patterns = [
                    b'effGetEffectName',
                    b'effGetProductString',
                    b'effGetVendorString'
                ]
                
                for pattern in name_patterns:
                    index = data.find(pattern)
                    if index != -1:
                        # Look for readable strings near this pattern
                        window_start = max(0, index - 1000)
                        window_end = min(len(data), index + 1000)
                        window = data[window_start:window_end]
                        
                        # Extract potential strings
                        strings = self._extract_strings(window, min_length=4, max_length=64)
                        if strings:
                            # Filter for likely plugin names
                            for s in strings:
                                if not s.startswith('eff') and not s.startswith('kPlug'):
                                    if 'plugin_name' not in info:
                                        info['plugin_name'] = s
                                    break
                                    
        except Exception as e:
            print(f"Error extracting VST info: {e}")
            
        return info
        
    def _extract_strings(self, data: bytes, min_length: int = 4, max_length: int = 256) -> List[str]:
        """Extract ASCII strings from binary data"""
        strings = []
        current = []
        
        for byte in data:
            if 32 <= byte <= 126:  # Printable ASCII
                current.append(chr(byte))
                if len(current) > max_length:
                    current = []
            else:
                if len(current) >= min_length:
                    strings.append(''.join(current))
                current = []
                
        if len(current) >= min_length:
            strings.append(''.join(current))
            
        return strings


def scan_vst_dlls(directory: str) -> List[Dict[str, Any]]:
    """Scan a directory for VST2 DLL files"""
    results = []
    path = Path(directory)
    
    if not path.exists():
        print(f"Directory does not exist: {directory}")
        return results
        
    for dll_path in path.glob("**/*.dll"):
        try:
            reader = VST2DllReader(str(dll_path))
            metadata = reader.read_metadata()
            
            if metadata.get('is_vst'):
                results.append(metadata)
                print(f"Found VST: {dll_path.name}")
                
        except Exception as e:
            print(f"Error reading {dll_path}: {e}")
            
    return results


def main():
    """Example usage"""
    import json
    
    # Example: Read a specific VST2 DLL
    dll_path = "C:\\Program Files\\VSTPlugins\\MyPlugin.dll"
    if Path(dll_path).exists():
        reader = VST2DllReader(dll_path)
        metadata = reader.read_metadata()
        
        print("DLL Metadata:")
        print(json.dumps(metadata, indent=2, default=str))
        
    # Example: Scan a directory
    vst_dir = "C:\\Program Files\\VSTPlugins"
    if Path(vst_dir).exists():
        print(f"\nScanning {vst_dir}...")
        plugins = scan_vst_dlls(vst_dir)
        
        print(f"\nFound {len(plugins)} VST plugins:")
        for plugin in plugins:
            name = plugin.get('plugin_name', plugin['filename'])
            arch = 'x64' if plugin.get('is_64bit') else 'x86'
            print(f"  - {name} ({arch})")
            
        # Save to JSON
        with open('vst_plugins.json', 'w') as f:
            json.dump(plugins, f, indent=2, default=str)
            

if __name__ == "__main__":
    main()