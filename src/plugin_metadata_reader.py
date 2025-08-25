"""
Plugin Metadata Reader
A cross-platform Python module for reading metadata from VST, VST3, AU, and CLAP audio plugins.
"""

import os
import sys
import struct
import platform
import json
import plistlib
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional, Union, Any
from dataclasses import dataclass, asdict
from enum import Enum
import re

# Try to import our JSON utilities for better parsing
try:
    from json_utils import JSONParser, read_plugin_json
    HAS_JSON_UTILS = True
except ImportError:
    try:
        from .json_utils import JSONParser, read_plugin_json
        HAS_JSON_UTILS = True
    except ImportError:
        HAS_JSON_UTILS = False

# Try to import VST3-specific JSON fixer
try:
    from vst3_json_fixer import VST3JSONFixer, read_vst3_json
    HAS_VST3_FIXER = True
except ImportError:
    try:
        from .vst3_json_fixer import VST3JSONFixer, read_vst3_json
        HAS_VST3_FIXER = True
    except ImportError:
        HAS_VST3_FIXER = False


class PluginFormat(Enum):
    """Supported plugin formats"""
    VST = "VST"
    VST3 = "VST3"
    AU = "AU"
    CLAP = "CLAP"
    UNKNOWN = "UNKNOWN"


class PluginType(Enum):
    """Plugin types/categories"""
    EFFECT = "Effect"
    INSTRUMENT = "Instrument"
    MIDI_EFFECT = "MIDI Effect"
    UNKNOWN = "Unknown"


@dataclass
class PluginMetadata:
    """Container for plugin metadata"""
    name: str
    format: PluginFormat
    path: str
    version: Optional[str] = None
    manufacturer: Optional[str] = None
    unique_id: Optional[str] = None
    plugin_type: Optional[PluginType] = None
    category: Optional[str] = None
    description: Optional[str] = None
    is_64bit: Optional[bool] = None
    bundle_id: Optional[str] = None
    supported_architectures: Optional[List[str]] = None
    additional_info: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary representation"""
        result = asdict(self)
        result['format'] = self.format.value
        if self.plugin_type:
            result['plugin_type'] = self.plugin_type.value
        return result


class PluginMetadataReader:
    """Base class for plugin metadata readers"""
    
    def __init__(self):
        self.system = platform.system()
        
    def read(self, plugin_path: str) -> Optional[PluginMetadata]:
        """Read metadata from a plugin file or bundle"""
        raise NotImplementedError("Subclasses must implement read()")
    
    def _read_plist(self, plist_path: str) -> Optional[Dict]:
        """Read a plist file (macOS)"""
        try:
            with open(plist_path, 'rb') as f:
                return plistlib.load(f)
        except Exception as e:
            print(f"Error reading plist {plist_path}: {e}")
            return None
    
    def _read_xml(self, xml_path: str) -> Optional[ET.Element]:
        """Read an XML file"""
        try:
            tree = ET.parse(xml_path)
            return tree.getroot()
        except Exception as e:
            print(f"Error reading XML {xml_path}: {e}")
            return None
    
    def _read_json_lenient(self, json_path: str) -> Optional[Dict]:
        """Read a JSON file with lenient parsing (handles trailing commas, comments, etc.)"""
        # Use VST3-specific fixer for moduleinfo.json files
        if HAS_VST3_FIXER and "moduleinfo.json" in json_path:
            result = read_vst3_json(json_path)
            if result:
                return result
        
        # Use advanced JSON parser if available
        if HAS_JSON_UTILS:
            result = read_plugin_json(json_path)
            if result:
                return result
        
        # Fallback to built-in lenient parser
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Remove trailing commas before } or ]
            # This regex finds commas followed by optional whitespace and a closing brace/bracket
            content = re.sub(r',(\s*[}\]])', r'\1', content)
            
            # Remove C-style comments (// and /* */)
            content = re.sub(r'//.*?$', '', content, flags=re.MULTILINE)
            content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
            
            # Try to parse the cleaned JSON
            return json.loads(content)
        except json.JSONDecodeError as e:
            # If it still fails, try more aggressive cleaning
            try:
                # Remove all trailing commas more aggressively
                content = re.sub(r',(\s*[}\]])', r'\1', content)
                # Remove any remaining comments
                lines = content.split('\n')
                cleaned_lines = []
                for line in lines:
                    if '//' in line:
                        line = line[:line.index('//')]
                    cleaned_lines.append(line)
                content = '\n'.join(cleaned_lines)
                return json.loads(content)
            except:
                # Suppress error messages for VST3 moduleinfo.json files since they're handled by VST3 fixer
                if not (HAS_VST3_FIXER and "moduleinfo.json" in json_path):
                    # Also suppress if we have json_utils
                    if not HAS_JSON_UTILS:
                        print(f"Error reading JSON {json_path}: {e}")
                return None
        except Exception as e:
            # Suppress for VST3 files that are handled elsewhere
            if not (HAS_VST3_FIXER and "moduleinfo.json" in json_path):
                if not HAS_JSON_UTILS:
                    print(f"Error reading JSON file {json_path}: {e}")
            return None


class VST3Reader(PluginMetadataReader):
    """Reader for VST3 plugins"""
    
    def read(self, plugin_path: str) -> Optional[PluginMetadata]:
        """Read VST3 plugin metadata"""
        path = Path(plugin_path)
        
        if not path.exists():
            return None
            
        metadata = PluginMetadata(
            name=path.stem,
            format=PluginFormat.VST3,
            path=str(path)
        )
        
        # VST3 plugins are bundles on both macOS and Windows
        if self.system == "Darwin":  # macOS
            # Read Info.plist
            info_plist_path = path / "Contents" / "Info.plist"
            if info_plist_path.exists():
                plist_data = self._read_plist(str(info_plist_path))
                if plist_data:
                    metadata.bundle_id = plist_data.get("CFBundleIdentifier")
                    metadata.version = plist_data.get("CFBundleVersion")
                    metadata.manufacturer = plist_data.get("CFBundleGetInfoString", "").split(",")[0].strip() if plist_data.get("CFBundleGetInfoString") else None
                    
            # Check for moduleinfo.json (VST3 SDK)
            moduleinfo_path = path / "Contents" / "Resources" / "moduleinfo.json"
            if moduleinfo_path.exists():
                # Always use _read_json_lenient which now handles VST3 files properly
                module_info = self._read_json_lenient(str(moduleinfo_path))
                if module_info:
                    metadata.name = module_info.get("Name", metadata.name)
                    metadata.version = module_info.get("Version", metadata.version)
                    # Handle nested Factory Info
                    if "Factory Info" in module_info and isinstance(module_info["Factory Info"], dict):
                        metadata.manufacturer = module_info["Factory Info"].get("Vendor", metadata.manufacturer)
                    else:
                        metadata.manufacturer = module_info.get("Vendor", metadata.manufacturer)
                    metadata.category = module_info.get("Category")
                    metadata.description = module_info.get("Description")
                    
        elif self.system == "Windows":
            # On Windows, check for Desktop.ini or moduleinfo.json
            moduleinfo_path = path / "Contents" / "x86_64-win" / "moduleinfo.json"
            if not moduleinfo_path.exists():
                moduleinfo_path = path / "Contents" / "Resources" / "moduleinfo.json"
                
            if moduleinfo_path.exists():
                # Always use _read_json_lenient which now handles VST3 files properly
                module_info = self._read_json_lenient(str(moduleinfo_path))
                if module_info:
                    metadata.name = module_info.get("Name", metadata.name)
                    metadata.version = module_info.get("Version", metadata.version)
                    # Handle nested Factory Info
                    if "Factory Info" in module_info and isinstance(module_info["Factory Info"], dict):
                        metadata.manufacturer = module_info["Factory Info"].get("Vendor", metadata.manufacturer)
                    else:
                        metadata.manufacturer = module_info.get("Vendor", metadata.manufacturer)
                    metadata.category = module_info.get("Category")
        
        # Determine plugin type from category or file structure
        if metadata.category:
            if "Instrument" in metadata.category or "Synth" in metadata.category:
                metadata.plugin_type = PluginType.INSTRUMENT
            else:
                metadata.plugin_type = PluginType.EFFECT
                
        return metadata


class VSTReader(PluginMetadataReader):
    """Reader for VST2 plugins"""
    
    def read(self, plugin_path: str) -> Optional[PluginMetadata]:
        """Read VST2 plugin metadata"""
        path = Path(plugin_path)
        
        if not path.exists():
            return None
            
        metadata = PluginMetadata(
            name=path.stem,
            format=PluginFormat.VST,
            path=str(path)
        )
        
        if self.system == "Darwin":  # macOS
            # VST2 on macOS is usually a bundle
            if path.suffix == ".vst":
                info_plist_path = path / "Contents" / "Info.plist"
                if info_plist_path.exists():
                    plist_data = self._read_plist(str(info_plist_path))
                    if plist_data:
                        metadata.bundle_id = plist_data.get("CFBundleIdentifier")
                        metadata.version = plist_data.get("CFBundleVersion")
                        metadata.manufacturer = plist_data.get("CFBundleGetInfoString", "").split(",")[0].strip() if plist_data.get("CFBundleGetInfoString") else None
                        
        elif self.system == "Windows":
            # VST2 on Windows is a DLL
            # Reading DLL metadata requires parsing PE headers
            # This is a simplified version - for full metadata, you'd need to parse the DLL
            metadata.is_64bit = "x64" in str(path) or "64" in str(path)
            
        return metadata


class AUReader(PluginMetadataReader):
    """Reader for Audio Unit plugins (macOS only)"""
    
    def read(self, plugin_path: str) -> Optional[PluginMetadata]:
        """Read AU plugin metadata"""
        if self.system != "Darwin":
            print("Audio Units are only supported on macOS")
            return None
            
        path = Path(plugin_path)
        
        if not path.exists():
            return None
            
        metadata = PluginMetadata(
            name=path.stem,
            format=PluginFormat.AU,
            path=str(path)
        )
        
        # AU plugins are bundles with .component extension
        info_plist_path = path / "Contents" / "Info.plist"
        if info_plist_path.exists():
            plist_data = self._read_plist(str(info_plist_path))
            if plist_data:
                metadata.bundle_id = plist_data.get("CFBundleIdentifier")
                metadata.version = plist_data.get("CFBundleVersion")
                metadata.manufacturer = plist_data.get("CFBundleGetInfoString", "").split(",")[0].strip() if plist_data.get("CFBundleGetInfoString") else None
                
                # Get AU specific info
                audio_components = plist_data.get("AudioComponents")
                if audio_components and len(audio_components) > 0:
                    component = audio_components[0]
                    metadata.name = component.get("name", metadata.name)
                    metadata.manufacturer = component.get("manufacturer", metadata.manufacturer)
                    metadata.description = component.get("description")
                    
                    # Determine type from AU type code
                    type_code = component.get("type")
                    if type_code:
                        if type_code in ["aumu", "aumf"]:  # Music Device, MIDI-controlled Effect
                            metadata.plugin_type = PluginType.INSTRUMENT
                        elif type_code == "aumx":  # Mixer
                            metadata.plugin_type = PluginType.EFFECT
                            metadata.category = "Mixer"
                        elif type_code == "aufx":  # Effect
                            metadata.plugin_type = PluginType.EFFECT
                        elif type_code == "aumi":  # MIDI Processor
                            metadata.plugin_type = PluginType.MIDI_EFFECT
                            
                # Get supported architectures
                if "CFBundleSupportedPlatforms" in plist_data:
                    metadata.supported_architectures = plist_data["CFBundleSupportedPlatforms"]
                    
        return metadata


class CLAPReader(PluginMetadataReader):
    """Reader for CLAP plugins"""
    
    def read(self, plugin_path: str) -> Optional[PluginMetadata]:
        """Read CLAP plugin metadata"""
        path = Path(plugin_path)
        
        if not path.exists():
            return None
            
        metadata = PluginMetadata(
            name=path.stem,
            format=PluginFormat.CLAP,
            path=str(path)
        )
        
        # CLAP plugins can have a descriptor file
        if self.system == "Darwin":  # macOS
            # CLAP on macOS might be a bundle
            if path.is_dir():
                info_plist_path = path / "Contents" / "Info.plist"
                if info_plist_path.exists():
                    plist_data = self._read_plist(str(info_plist_path))
                    if plist_data:
                        metadata.bundle_id = plist_data.get("CFBundleIdentifier")
                        metadata.version = plist_data.get("CFBundleVersion")
                        
                # Look for CLAP manifest
                manifest_path = path / "Contents" / "Resources" / "clap.json"
                if manifest_path.exists():
                    manifest = self._read_json_lenient(str(manifest_path))
                    if manifest:
                        metadata.name = manifest.get("name", metadata.name)
                        metadata.version = manifest.get("version", metadata.version)
                        metadata.manufacturer = manifest.get("vendor")
                        metadata.description = manifest.get("description")
                        metadata.unique_id = manifest.get("id")
                        
        elif self.system == "Windows":
            # CLAP on Windows is typically a DLL
            # Check for accompanying manifest file
            manifest_path = path.with_suffix(".json")
            if manifest_path.exists():
                manifest = self._read_json_lenient(str(manifest_path))
                if manifest:
                    metadata.name = manifest.get("name", metadata.name)
                    metadata.version = manifest.get("version", metadata.version)
                    metadata.manufacturer = manifest.get("vendor")
                    
        return metadata


class PluginScanner:
    """Main class for scanning and reading plugin metadata"""
    
    def __init__(self):
        self.system = platform.system()
        self.readers = {
            PluginFormat.VST: VSTReader(),
            PluginFormat.VST3: VST3Reader(),
            PluginFormat.AU: AUReader() if self.system == "Darwin" else None,
            PluginFormat.CLAP: CLAPReader()
        }
        
    def get_default_plugin_paths(self) -> Dict[PluginFormat, List[str]]:
        """Get default plugin installation paths for the current OS"""
        paths = {}
        
        if self.system == "Darwin":  # macOS
            home = Path.home()
            paths[PluginFormat.VST] = [
                str(home / "Library/Audio/Plug-Ins/VST"),
                "/Library/Audio/Plug-Ins/VST"
            ]
            paths[PluginFormat.VST3] = [
                str(home / "Library/Audio/Plug-Ins/VST3"),
                "/Library/Audio/Plug-Ins/VST3"
            ]
            paths[PluginFormat.AU] = [
                str(home / "Library/Audio/Plug-Ins/Components"),
                "/Library/Audio/Plug-Ins/Components"
            ]
            paths[PluginFormat.CLAP] = [
                str(home / "Library/Audio/Plug-Ins/CLAP"),
                "/Library/Audio/Plug-Ins/CLAP"
            ]
            
        elif self.system == "Windows":
            paths[PluginFormat.VST] = [
                "C:\\Program Files\\VSTPlugins",
                "C:\\Program Files\\Steinberg\\VSTPlugins",
                "C:\\Program Files (x86)\\VSTPlugins",
                "C:\\Program Files (x86)\\Steinberg\\VSTPlugins"
            ]
            paths[PluginFormat.VST3] = [
                "C:\\Program Files\\Common Files\\VST3",
                "C:\\Program Files (x86)\\Common Files\\VST3"
            ]
            paths[PluginFormat.CLAP] = [
                "C:\\Program Files\\Common Files\\CLAP",
                "C:\\Program Files (x86)\\Common Files\\CLAP"
            ]
            
        elif self.system == "Linux":
            home = Path.home()
            paths[PluginFormat.VST] = [
                str(home / ".vst"),
                "/usr/lib/vst",
                "/usr/local/lib/vst"
            ]
            paths[PluginFormat.VST3] = [
                str(home / ".vst3"),
                "/usr/lib/vst3",
                "/usr/local/lib/vst3"
            ]
            paths[PluginFormat.CLAP] = [
                str(home / ".clap"),
                "/usr/lib/clap",
                "/usr/local/lib/clap"
            ]
            
        return paths
    
    def detect_format(self, plugin_path: str) -> PluginFormat:
        """Detect plugin format from file extension"""
        path = Path(plugin_path)
        suffix = path.suffix.lower()
        
        if suffix == ".vst3":
            return PluginFormat.VST3
        elif suffix == ".vst":
            return PluginFormat.VST
        elif suffix == ".component":
            return PluginFormat.AU
        elif suffix == ".clap":
            return PluginFormat.CLAP
        elif suffix == ".dll" and self.system == "Windows":
            # Could be VST2 or CLAP
            if "vst" in path.stem.lower():
                return PluginFormat.VST
            elif "clap" in path.stem.lower():
                return PluginFormat.CLAP
            return PluginFormat.VST  # Default to VST for DLLs
        else:
            return PluginFormat.UNKNOWN
            
    def read_plugin(self, plugin_path: str) -> Optional[PluginMetadata]:
        """Read metadata from a single plugin"""
        format_type = self.detect_format(plugin_path)
        
        if format_type == PluginFormat.UNKNOWN:
            print(f"Unknown plugin format for: {plugin_path}")
            return None
            
        reader = self.readers.get(format_type)
        if reader is None:
            print(f"No reader available for format: {format_type}")
            return None
            
        return reader.read(plugin_path)
    
    def scan_directory(self, directory: str, format_filter: Optional[PluginFormat] = None) -> List[PluginMetadata]:
        """Scan a directory for plugins"""
        results = []
        path = Path(directory)
        
        if not path.exists():
            print(f"Directory does not exist: {directory}")
            return results
            
        # Define extensions to look for
        extensions = []
        if format_filter:
            if format_filter == PluginFormat.VST:
                extensions = [".vst", ".dll"] if self.system == "Windows" else [".vst"]
            elif format_filter == PluginFormat.VST3:
                extensions = [".vst3"]
            elif format_filter == PluginFormat.AU:
                extensions = [".component"]
            elif format_filter == PluginFormat.CLAP:
                extensions = [".clap", ".dll"] if self.system == "Windows" else [".clap"]
        else:
            # Look for all formats
            extensions = [".vst", ".vst3", ".component", ".clap"]
            if self.system == "Windows":
                extensions.append(".dll")
                
        # Scan for plugins
        for ext in extensions:
            for plugin_path in path.glob(f"**/*{ext}"):
                if plugin_path.is_dir() or plugin_path.is_file():
                    metadata = self.read_plugin(str(plugin_path))
                    if metadata:
                        results.append(metadata)
                        
        return results
    
    def scan_default_locations(self) -> Dict[PluginFormat, List[PluginMetadata]]:
        """Scan all default plugin locations"""
        results = {}
        default_paths = self.get_default_plugin_paths()
        
        for format_type, paths in default_paths.items():
            format_results = []
            for path in paths:
                if Path(path).exists():
                    format_results.extend(self.scan_directory(path, format_type))
            results[format_type] = format_results
            
        return results


def main():
    """Example usage"""
    scanner = PluginScanner()
    
    # Example: Read a specific plugin
    plugin_path = "/Library/Audio/Plug-Ins/VST3/MyPlugin.vst3"
    if Path(plugin_path).exists():
        metadata = scanner.read_plugin(plugin_path)
        if metadata:
            print(f"Plugin: {metadata.name}")
            print(f"Format: {metadata.format.value}")
            print(f"Version: {metadata.version}")
            print(f"Manufacturer: {metadata.manufacturer}")
            print("-" * 50)
    
    # Example: Scan default locations
    print("Scanning default plugin locations...")
    all_plugins = scanner.scan_default_locations()
    
    for format_type, plugins in all_plugins.items():
        if plugins:
            print(f"\n{format_type.value} Plugins ({len(plugins)}):")
            for plugin in plugins[:5]:  # Show first 5 of each type
                print(f"  - {plugin.name} (v{plugin.version}) by {plugin.manufacturer}")
                
    # Example: Export to JSON
    all_metadata = []
    for plugins in all_plugins.values():
        for plugin in plugins:
            all_metadata.append(plugin.to_dict())
            
    if all_metadata:
        output_file = "plugin_metadata.json"
        with open(output_file, 'w') as f:
            json.dump(all_metadata, f, indent=2)
        print(f"\nMetadata exported to {output_file}")


if __name__ == "__main__":
    main()