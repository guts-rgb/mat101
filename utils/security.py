"""
Security utilities for file handling and validation
"""
import os
import re
from werkzeug.utils import secure_filename

def sanitize_filename(filename):
    """
    Sanitize filename to prevent directory traversal and other attacks
    """
    if not filename:
        return None
    
    # Use werkzeug's secure_filename as base
    safe_name = secure_filename(filename)
    
    # Additional sanitization
    # Remove any remaining path separators
    safe_name = safe_name.replace('/', '').replace('\\', '')
    
    # Limit length
    if len(safe_name) > 100:
        name, ext = os.path.splitext(safe_name)
        safe_name = name[:96] + ext
    
    return safe_name

def is_safe_path(path, base_dir):
    """
    Check if path is safe (within base directory)
    """
    try:
        abs_path = os.path.abspath(path)
        abs_base = os.path.abspath(base_dir)
        return abs_path.startswith(abs_base)
    except:
        return False

def validate_matlab_script(file_path):
    """
    Basic validation of MATLAB script for security
    Returns (is_safe: bool, issues: list)
    """
    issues = []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check for potentially dangerous commands
        dangerous_patterns = [
            r'system\s*\(',      # system() calls
            r'!\s*[^\n]*',       # Shell commands with !
            r'dos\s*\(',         # DOS commands
            r'unix\s*\(',        # Unix commands
            r'winopen\s*\(',     # Windows open
            r'web\s*\(',         # Web browser
            r'delete\s*\(',      # File deletion
            r'rmdir\s*\(',       # Directory removal
            r'movefile\s*\(',    # File moving
            r'copyfile\s*\(',    # File copying
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                issues.append(f"Potentially dangerous command found: {pattern}")
        
        # Check for file I/O outside working directory
        io_patterns = [
            r'fopen\s*\(\s*[\'"][^\'"\n]*[/\\]',  # Absolute paths in fopen
            r'save\s*\(\s*[\'"][^\'"\n]*[/\\]',   # Absolute paths in save
            r'load\s*\(\s*[\'"][^\'"\n]*[/\\]',   # Absolute paths in load
        ]
        
        for pattern in io_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                issues.append(f"Absolute file path detected: {pattern}")
        
        # File size check (limit to 1MB)
        if len(content) > 1024 * 1024:
            issues.append("Script file is too large (>1MB)")
        
        # Line count check (limit to 10000 lines)
        if len(content.split('\n')) > 10000:
            issues.append("Script has too many lines (>10000)")
        
        return len(issues) == 0, issues
    
    except Exception as e:
        return False, [f"Failed to validate script: {str(e)}"]

def create_sandbox_environment(base_dir, user_id):
    """
    Create a sandboxed environment for script execution
    """
    sandbox_dir = os.path.join(base_dir, 'sandbox', str(user_id))
    os.makedirs(sandbox_dir, exist_ok=True)
    
    # Create subdirectories
    input_dir = os.path.join(sandbox_dir, 'input')
    output_dir = os.path.join(sandbox_dir, 'output')
    temp_dir = os.path.join(sandbox_dir, 'temp')
    
    os.makedirs(input_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(temp_dir, exist_ok=True)
    
    return {
        'sandbox': sandbox_dir,
        'input': input_dir,
        'output': output_dir,
        'temp': temp_dir
    }