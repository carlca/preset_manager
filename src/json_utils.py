"""
JSON Utilities
Provides robust JSON parsing with support for common JSON variations including:
- Trailing commas
- Comments (// and /* */)
- Unquoted keys (with json5)
- Single quotes (with json5)
"""

import json
import re
from typing import Dict, Any, Optional, Union
from pathlib import Path

# Try to import json5 for more lenient parsing
try:
    import json5
    HAS_JSON5 = True
except ImportError:
    HAS_JSON5 = False


class JSONParser:
    """Robust JSON parser that handles common variations and errors"""
    
    @staticmethod
    def clean_json_string(content: str) -> str:
        """
        Clean a JSON string to make it valid JSON
        
        Handles:
        - Trailing commas before ] or }
        - Single-line comments (//)
        - Multi-line comments (/* */)
        - BOM (Byte Order Mark)
        - Control characters in strings
        """
        # Remove BOM if present
        if content.startswith('\ufeff'):
            content = content[1:]
        
        # Remove single-line comments (// comment)
        # But preserve URLs (http://, https://, file://)
        content = re.sub(r'(?<!:)//.*?$', '', content, flags=re.MULTILINE)
        
        # Remove multi-line comments (/* comment */)
        content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
        
        # Remove trailing commas before closing braces/brackets
        # This handles multiple passes to catch nested cases
        prev_content = None
        while prev_content != content:
            prev_content = content
            # Remove trailing comma before } or ]
            content = re.sub(r',(\s*[}\]])', r'\1', content)
        
        # Escape control characters in strings
        # This is a more careful approach that only touches string values
        def escape_control_chars(match):
            string_content = match.group(1)
            # Replace actual newlines, tabs, etc. with their escape sequences
            string_content = string_content.replace('\n', '\\n')
            string_content = string_content.replace('\r', '\\r')
            string_content = string_content.replace('\t', '\\t')
            string_content = string_content.replace('\b', '\\b')
            string_content = string_content.replace('\f', '\\f')
            return '"' + string_content + '"'
        
        # Only escape control chars within quoted strings, not in the whole content
        # This regex matches quoted strings while respecting escaped quotes
        content = re.sub(r'"((?:[^"\\]|\\.)*)?"', escape_control_chars, content)
        
        # Remove any trailing whitespace
        content = content.strip()
        
        return content
    
    @staticmethod
    def parse(file_path: Union[str, Path], encoding: str = 'utf-8') -> Optional[Dict[str, Any]]:
        """
        Parse a JSON file with maximum compatibility
        
        Args:
            file_path: Path to the JSON file
            encoding: File encoding (default: utf-8)
            
        Returns:
            Parsed JSON as dictionary, or None if parsing fails
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            print(f"File not found: {file_path}")
            return None
        
        try:
            # Read the file content
            with open(file_path, 'r', encoding=encoding) as f:
                content = f.read()
        except UnicodeDecodeError:
            # Try with different encodings
            for alt_encoding in ['utf-8-sig', 'latin-1', 'cp1252']:
                try:
                    with open(file_path, 'r', encoding=alt_encoding) as f:
                        content = f.read()
                    break
                except UnicodeDecodeError:
                    continue
            else:
                print(f"Could not decode file {file_path} with any known encoding")
                return None
        except Exception as e:
            print(f"Error reading file {file_path}: {e}")
            return None
        
        # Try json5 first if available (most lenient)
        if HAS_JSON5:
            try:
                return json5.loads(content)
            except Exception:
                pass  # Fall back to other methods
        
        # Try standard JSON
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass  # Try cleaning the content
        
        # Clean and try again
        cleaned_content = JSONParser.clean_json_string(content)
        
        try:
            return json.loads(cleaned_content)
        except json.JSONDecodeError as e:
            # Try more aggressive cleaning
            try:
                # Handle specific VST3 moduleinfo.json issues
                # Some files have spaces in keys which is valid JSON but might have other issues
                
                # First, handle potential control characters more aggressively
                # Replace any control character that's not already escaped
                import string
                printable = set(string.printable)
                cleaned_content = ''.join(char if char in printable else ' ' for char in cleaned_content)
                
                # Remove all whitespace around colons and commas (but keep spaces in quoted strings)
                # This is a more careful approach
                parts = []
                in_string = False
                escape_next = False
                for i, char in enumerate(cleaned_content):
                    if escape_next:
                        parts.append(char)
                        escape_next = False
                        continue
                    if char == '\\':
                        escape_next = True
                        parts.append(char)
                        continue
                    if char == '"' and not escape_next:
                        in_string = not in_string
                        parts.append(char)
                        continue
                    if not in_string and char in ' \t\n\r' and i > 0 and i < len(cleaned_content) - 1:
                        # Check if this whitespace is around : or ,
                        prev_char = cleaned_content[i-1] if i > 0 else ''
                        next_char = cleaned_content[i+1] if i < len(cleaned_content) - 1 else ''
                        if prev_char in ':,' or next_char in ':,':
                            continue  # Skip this whitespace
                    parts.append(char)
                cleaned_content = ''.join(parts)
                
                # Try to fix unquoted keys (simple cases)
                # This is a basic attempt - json5 handles this better
                cleaned_content = re.sub(
                    r'([,\{\s])([a-zA-Z_][a-zA-Z0-9_]*)\s*:',
                    r'\1"\2":',
                    cleaned_content
                )
                
                return json.loads(cleaned_content)
            except json.JSONDecodeError:
                # Last resort: try to extract valid JSON objects/arrays
                result = JSONParser.extract_json_objects(cleaned_content)
                if result:
                    return result[0] if len(result) == 1 else {'objects': result}
                
                # Suppress detailed error for common VST3 issues
                if "moduleinfo.json" not in str(file_path):
                    print(f"Could not parse JSON from {file_path}: {e}")
                return None
    
    @staticmethod
    def extract_json_objects(content: str) -> list:
        """
        Extract valid JSON objects or arrays from a string
        
        This is useful when dealing with partially corrupted JSON files
        """
        objects = []
        
        # Find potential JSON objects (starting with { or [)
        for match in re.finditer(r'[\{\[]', content):
            start = match.start()
            
            # Try to find the matching closing bracket
            bracket_count = 0
            in_string = False
            escape_next = False
            
            open_char = content[start]
            close_char = '}' if open_char == '{' else ']'
            
            for i in range(start, len(content)):
                char = content[i]
                
                if escape_next:
                    escape_next = False
                    continue
                
                if char == '\\':
                    escape_next = True
                    continue
                
                if char == '"' and not escape_next:
                    in_string = not in_string
                    continue
                
                if not in_string:
                    if char == open_char:
                        bracket_count += 1
                    elif char == close_char:
                        bracket_count -= 1
                        
                        if bracket_count == 0:
                            # Found matching closing bracket
                            potential_json = content[start:i+1]
                            try:
                                obj = json.loads(potential_json)
                                objects.append(obj)
                                break
                            except json.JSONDecodeError:
                                # Try cleaning this portion
                                cleaned = JSONParser.clean_json_string(potential_json)
                                try:
                                    obj = json.loads(cleaned)
                                    objects.append(obj)
                                    break
                                except json.JSONDecodeError:
                                    pass
                            break
        
        return objects
    
    @staticmethod
    def parse_plugin_manifest(file_path: Union[str, Path]) -> Optional[Dict[str, Any]]:
        """
        Parse a plugin manifest file (moduleinfo.json, clap.json, etc.)
        
        These files often have trailing commas and comments
        """
        result = JSONParser.parse(file_path)
        
        if result:
            # Normalize common field names
            normalized = {}
            
            # Map common variations to standard names
            name_fields = ['Name', 'name', 'plugin_name', 'pluginName', 'displayName']
            version_fields = ['Version', 'version', 'plugin_version', 'pluginVersion']
            vendor_fields = ['Vendor', 'vendor', 'manufacturer', 'Manufacturer', 'company', 'Company']
            desc_fields = ['Description', 'description', 'desc', 'info', 'about']
            category_fields = ['Category', 'category', 'type', 'plugin_type', 'pluginType']
            
            for field in name_fields:
                if field in result:
                    normalized['name'] = result[field]
                    break
            
            for field in version_fields:
                if field in result:
                    normalized['version'] = result[field]
                    break
            
            for field in vendor_fields:
                if field in result:
                    normalized['vendor'] = result[field]
                    break
            
            for field in desc_fields:
                if field in result:
                    normalized['description'] = result[field]
                    break
            
            for field in category_fields:
                if field in result:
                    normalized['category'] = result[field]
                    break
            
            # Include any other fields
            for key, value in result.items():
                if key not in normalized.values():
                    normalized[key] = value
            
            return normalized
        
        return None


def read_plugin_json(file_path: Union[str, Path]) -> Optional[Dict[str, Any]]:
    """
    Convenience function to read plugin JSON files
    
    Args:
        file_path: Path to the JSON file
        
    Returns:
        Parsed JSON as dictionary, or None if parsing fails
    """
    return JSONParser.parse_plugin_manifest(file_path)


def test_json_parser():
    """Test the JSON parser with various malformed JSON samples"""
    
    test_cases = [
        # Valid JSON
        ('{"name": "Test", "version": "1.0"}', True),
        
        # Trailing comma
        ('{"name": "Test", "version": "1.0",}', True),
        
        # Multiple trailing commas
        ('{"items": [1, 2, 3,], "name": "Test",}', True),
        
        # Single-line comments
        ('{"name": "Test", // This is a comment\n"version": "1.0"}', True),
        
        # Multi-line comments
        ('{"name": "Test", /* This is a\nmulti-line comment */ "version": "1.0"}', True),
        
        # Mixed issues
        ('''
        {
            "name": "Test Plugin", // Plugin name
            "version": "1.0.0",
            "features": [
                "Feature 1",
                "Feature 2", // Last feature
            ],
        }
        ''', True),
    ]
    
    for i, (json_str, should_parse) in enumerate(test_cases):
        cleaned = JSONParser.clean_json_string(json_str)
        try:
            result = json.loads(cleaned)
            parsed = True
            print(f"Test {i+1}: {'✓' if should_parse else '✗'} Parsed successfully")
        except json.JSONDecodeError as e:
            parsed = False
            print(f"Test {i+1}: {'✗' if should_parse else '✓'} Failed to parse: {e}")
        
        assert parsed == should_parse, f"Test {i+1} failed"
    
    print("\nAll tests passed!")


if __name__ == "__main__":
    # Run tests
    test_json_parser()
    
    # Example usage
    import sys
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        result = read_plugin_json(file_path)
        if result:
            print(f"\nSuccessfully parsed {file_path}:")
            print(json.dumps(result, indent=2))
        else:
            print(f"\nFailed to parse {file_path}")