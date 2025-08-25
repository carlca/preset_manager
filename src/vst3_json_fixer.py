#!/usr/bin/env python3
"""
VST3 JSON Fixer
Specialized module for fixing common issues in VST3 moduleinfo.json files.
These files often have:
- Trailing commas
- Invalid control characters
- Mixed line endings
- UTF-8 BOM markers
- Spaces in JSON keys (which is valid but needs careful handling)
"""

import json
import re
import codecs
from pathlib import Path
from typing import Dict, Any, Optional, Union


class VST3JSONFixer:
    """Fixes common issues in VST3 moduleinfo.json files"""
    
    @staticmethod
    def read_file_robust(file_path: Union[str, Path]) -> str:
        """
        Read a file with robust encoding detection and normalization
        
        Args:
            file_path: Path to the file
            
        Returns:
            File content as string with normalized line endings
        """
        file_path = Path(file_path)
        
        # Try different encodings in order of likelihood
        encodings = ['utf-8-sig', 'utf-8', 'latin-1', 'cp1252', 'iso-8859-1']
        
        content = None
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    content = f.read()
                break
            except (UnicodeDecodeError, UnicodeError):
                continue
        
        if content is None:
            # Last resort: read as binary and decode with replacement
            with open(file_path, 'rb') as f:
                raw_bytes = f.read()
                # Remove BOM if present
                if raw_bytes.startswith(codecs.BOM_UTF8):
                    raw_bytes = raw_bytes[len(codecs.BOM_UTF8):]
                content = raw_bytes.decode('utf-8', errors='replace')
        
        # Normalize line endings to \n
        content = content.replace('\r\n', '\n').replace('\r', '\n')
        
        # Remove any null bytes
        content = content.replace('\x00', '')
        
        return content
    
    @staticmethod
    def remove_comments(content: str) -> str:
        """
        Remove C-style comments from JSON content
        
        Args:
            content: JSON string with potential comments
            
        Returns:
            JSON string without comments
        """
        # Remove single-line comments (// ...) but preserve URLs
        # Match // only if not preceded by : (for URLs)
        content = re.sub(r'(?<!:)//.*?$', '', content, flags=re.MULTILINE)
        
        # Remove multi-line comments (/* ... */)
        content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
        
        return content
    
    @staticmethod
    def fix_trailing_commas(content: str) -> str:
        """
        Remove trailing commas before closing brackets/braces
        
        Args:
            content: JSON string with potential trailing commas
            
        Returns:
            JSON string without trailing commas
        """
        # Keep removing trailing commas until no more are found
        # This handles nested cases
        prev_content = None
        max_iterations = 10  # Prevent infinite loops
        iterations = 0
        
        while prev_content != content and iterations < max_iterations:
            prev_content = content
            # Remove comma before closing brace or bracket, with optional whitespace
            content = re.sub(r',(\s*[}\]])', r'\1', content)
            iterations += 1
        
        return content
    
    @staticmethod
    def fix_control_characters(content: str) -> str:
        """
        Fix or remove invalid control characters in JSON strings
        
        Args:
            content: JSON string with potential control characters
            
        Returns:
            JSON string with fixed control characters
        """
        # First, let's identify string boundaries properly
        # We need to be careful not to modify control characters outside of string values
        
        # Split content into tokens (rough tokenization)
        result = []
        i = 0
        while i < len(content):
            if content[i] == '"':
                # Start of a string
                j = i + 1
                string_chars = ['"']
                
                # Find the end of the string
                while j < len(content):
                    if content[j] == '\\' and j + 1 < len(content):
                        # Escaped character - keep both the backslash and next char
                        string_chars.append(content[j])
                        string_chars.append(content[j + 1])
                        j += 2
                    elif content[j] == '"':
                        # End of string
                        string_chars.append('"')
                        j += 1
                        break
                    else:
                        # Regular character
                        char = content[j]
                        
                        # Check if it's a control character that needs escaping
                        if ord(char) < 32 and char not in '\n\r\t':
                            # Skip invalid control characters
                            j += 1
                            continue
                        elif char == '\t':
                            string_chars.append('\\t')
                        elif char == '\n':
                            string_chars.append('\\n')
                        elif char == '\r':
                            string_chars.append('\\r')
                        else:
                            string_chars.append(char)
                        j += 1
                
                result.append(''.join(string_chars))
                i = j
            else:
                # Not in a string, keep as-is
                result.append(content[i])
                i += 1
        
        return ''.join(result)
    
    @staticmethod
    def validate_and_fix_structure(content: str) -> str:
        """
        Validate and fix JSON structure issues
        
        Args:
            content: JSON string to validate
            
        Returns:
            Fixed JSON string
        """
        # Check for common structural issues
        
        # Ensure the content starts with { or [ and ends with } or ]
        content = content.strip()
        
        if not content:
            return '{}'
        
        # Check bracket balance
        open_braces = content.count('{')
        close_braces = content.count('}')
        open_brackets = content.count('[')
        close_brackets = content.count(']')
        
        # Add missing closing braces/brackets
        if open_braces > close_braces:
            content += '}' * (open_braces - close_braces)
        if open_brackets > close_brackets:
            content += ']' * (open_brackets - close_brackets)
        
        return content
    
    @staticmethod
    def parse(file_path: Union[str, Path]) -> Optional[Dict[str, Any]]:
        """
        Parse a VST3 moduleinfo.json file with all fixes applied
        
        Args:
            file_path: Path to the moduleinfo.json file
            
        Returns:
            Parsed JSON as dictionary, or None if parsing fails
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            return None
        
        try:
            # Read file with robust encoding handling
            content = VST3JSONFixer.read_file_robust(file_path)
            
            # Apply fixes in order
            content = VST3JSONFixer.remove_comments(content)
            content = VST3JSONFixer.fix_trailing_commas(content)
            content = VST3JSONFixer.fix_control_characters(content)
            content = VST3JSONFixer.validate_and_fix_structure(content)
            
            # Try to parse the fixed content
            try:
                return json.loads(content)
            except json.JSONDecodeError as e:
                # If it still fails, try one more aggressive approach
                # Remove all non-printable characters except whitespace
                import string
                printable = set(string.printable)
                content = ''.join(char for char in content if char in printable)
                
                # Try again
                return json.loads(content)
                
        except Exception as e:
            # Silently fail for VST3 files - many don't have valid JSON anyway
            return None
    
    @staticmethod
    def extract_metadata(data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract relevant metadata from parsed moduleinfo.json
        
        Args:
            data: Parsed JSON data
            
        Returns:
            Dictionary with normalized metadata
        """
        metadata = {}
        
        # Direct fields
        metadata['name'] = data.get('Name', '')
        metadata['version'] = data.get('Version', '')
        
        # Factory Info (nested)
        if 'Factory Info' in data and isinstance(data['Factory Info'], dict):
            factory = data['Factory Info']
            metadata['vendor'] = factory.get('Vendor', '')
            metadata['url'] = factory.get('URL', '')
            metadata['email'] = factory.get('E-Mail', '')
        else:
            metadata['vendor'] = data.get('Vendor', '')
        
        # Classes information
        if 'Classes' in data and isinstance(data['Classes'], list):
            metadata['num_classes'] = len(data['Classes'])
            
            # Get info from first class if available
            if data['Classes']:
                first_class = data['Classes'][0]
                if 'Sub Categories' in first_class:
                    metadata['categories'] = first_class['Sub Categories']
                if 'SDKVersion' in first_class:
                    metadata['sdk_version'] = first_class['SDKVersion']
        
        return metadata


def read_vst3_json(file_path: Union[str, Path]) -> Optional[Dict[str, Any]]:
    """
    Convenience function to read and parse VST3 moduleinfo.json files
    
    Args:
        file_path: Path to the moduleinfo.json file
        
    Returns:
        Parsed JSON data or None if parsing fails
    """
    return VST3JSONFixer.parse(file_path)


def test_vst3_fixer():
    """Test the VST3 JSON fixer with sample problematic content"""
    
    # Sample problematic VST3 JSON content
    test_content = '''
    {
      "Name": "Test Plugin",
      "Version": "1.0.0",
      "Factory Info": {
        "Vendor": "Test Vendor",
        "URL": "https://example.com",
        "E-Mail": "test@example.com",
        "Flags": {
          "Unicode": true,
          "Classes Discardable": false,
        },
      },
      "Classes": [
        {
          "CID": "1234567890ABCDEF",
          "Category": "Audio Module Class",
          "Sub Categories": [
            "Fx",
            "Distortion",
          ],
        },
      ],
    }
    '''
    
    print("Testing VST3 JSON Fixer")
    print("=" * 60)
    
    # Test each fix function
    print("\n1. Original content (with issues):")
    print("   - Has trailing commas")
    print("   - Has spaces in keys")
    
    print("\n2. After removing comments:")
    content = VST3JSONFixer.remove_comments(test_content)
    print("   ✓ Comments removed")
    
    print("\n3. After fixing trailing commas:")
    content = VST3JSONFixer.fix_trailing_commas(content)
    print("   ✓ Trailing commas removed")
    
    print("\n4. After fixing control characters:")
    content = VST3JSONFixer.fix_control_characters(content)
    print("   ✓ Control characters fixed")
    
    print("\n5. After structure validation:")
    content = VST3JSONFixer.validate_and_fix_structure(content)
    print("   ✓ Structure validated")
    
    print("\n6. Parsing result:")
    try:
        data = json.loads(content)
        print("   ✓ Successfully parsed!")
        
        metadata = VST3JSONFixer.extract_metadata(data)
        print("\n   Extracted metadata:")
        for key, value in metadata.items():
            print(f"     {key}: {value}")
            
    except json.JSONDecodeError as e:
        print(f"   ✗ Failed to parse: {e}")
    
    print("\n" + "=" * 60)
    print("Test completed!")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        # Test with a specific file
        file_path = sys.argv[1]
        print(f"Testing VST3 JSON file: {file_path}")
        
        data = read_vst3_json(file_path)
        if data:
            print("✓ Successfully parsed!")
            metadata = VST3JSONFixer.extract_metadata(data)
            print("\nExtracted metadata:")
            for key, value in metadata.items():
                print(f"  {key}: {value}")
        else:
            print("✗ Failed to parse")
    else:
        # Run test
        test_vst3_fixer()