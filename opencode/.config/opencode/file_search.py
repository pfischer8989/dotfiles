#!/usr/bin/env python3
"""Simple file search utility for Linux."""

import os
import sys
from pathlib import Path


def search_files(directory, patterns, extensions=None, max_depth=None, case_sensitive=False):
    """
    Search for files on a directory.
    
    Args:
        directory: Path to search directory
        patterns: List of filename patterns to match
        extensions: List of extensions to filter (e.g., ['.txt', '.py'])
        max_depth: Maximum directory depth (-1 for unlimited)
        case_sensitive: Whether pattern matching is case-sensitive
    """
    results = []
    
    if not os.path.isdir(directory):
        print(f"Error: '{directory}' is not a valid directory")
        return results
    
    def search_recursive(path, current_depth):
        if max_depth is not None and current_depth > max_depth:
            return
        
        try:
            entries = list(os.scandir(path))
        except PermissionError:
            return
        except OSError:
            return
        
        for entry in entries:
            if entry.is_symlink():
                continue
            
            if entry.is_file():
                path = Path(entry.path)
                if any(pattern in entry.name if case_sensitive else pattern.lower() in entry.name.lower() 
                       for pattern in patterns):
                    if extensions is None or any(path.suffix.lower() == ext.lower() for ext in extensions):
                        results.append(str(path.absolute()))
            elif entry.is_dir():
                search_recursive(entry.path, current_depth + 1)
    
    search_recursive(directory, 0)
    return results


def main():
    if len(sys.argv) < 3:
        print("Usage: python file_search.py <directory> <pattern> [pattern...] [options]")
        print("Options:")
        print("  -e <ext>      Filter by extension (can be used multiple times)")
        print("  -d <num>      Limit search depth (0=current dir only)")
        print("  -s            Case-sensitive search")
        print("  -h            Show this help")
        sys.exit(1)
    
    target_dir = sys.argv[1]
    patterns = sys.argv[2:]
    
    extensions = None
    max_depth = None
    case_sensitive = False
    
    # Parse options
    i = 0
    while i < len(patterns):
        if patterns[i] == '-e' and i + 1 < len(patterns):
            extensions = [patterns[i + 1] if not patterns[i + 1].startswith('-') else 
                         patterns[i].split('=')[1]]
            i += 2
        elif patterns[i] == '-d' and i + 1 < len(patterns):
            max_depth = int(patterns[i + 1]) if patterns[i + 1].isdigit() else -1
            i += 2
        elif patterns[i] == '-s':
            case_sensitive = True
        elif patterns[i] in ['-h', '--help']:
            main()
            return
        else:
            i += 1
    
    # Handle absolute paths
    paths_to_search = []
    if os.path.exists(target_dir):
        if os.path.isdir(target_dir):
            paths_to_search = [target_dir]
        else:
            for path in Path(target_dir).parents:
                paths_to_search.append(str(path))
    else:
        # Try as a file, search its parents
        current = Path(target_dir)
        while current.exists() and not current.is_dir():
            current = current.parent
        if current.exists() and current.is_dir():
            paths_to_search = [str(current)]
        else:
            print(f"Error: '{target_dir}' does not exist")
            sys.exit(1)
    
    for search_path in paths_to_search:
        results = search_files(search_path, patterns, extensions, max_depth, case_sensitive)
        if results:
            print(f"Found {len(results)} file(s) in {search_path}:")
            for result in results:
                print(result)
        else:
            print(f"No files found in {search_path}")


if __name__ == '__main__':
    main()
