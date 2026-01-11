"""
Repository Analyzer

Analyzes repository structure and extracts file information.
"""

import os
import stat
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class RepoAnalyzer:
    """
    Analyzes repository structure and extracts file information.
    """
    
    def __init__(
        self, 
        include_patterns: Optional[List[str]] = None, 
        exclude_patterns: Optional[List[str]] = None
    ):
        """
        Initialize the repository analyzer.
        
        Args:
            include_patterns: Patterns to include (e.g., ['*.py', '*.js'])
            exclude_patterns: Patterns to exclude
        """
        self.include_patterns = include_patterns or []
        self.exclude_patterns = exclude_patterns or [
            'node_modules', '__pycache__', '.git', '.svn', '.hg', 
            'dist', 'build', '.vscode', '.idea', '*.log', '*.tmp'
        ]
    
    def analyze_repository_structure(self, repo_path: str) -> Dict:
        """
        Analyze the repository structure and return a file tree representation.
        
        Args:
            repo_path: Path to the repository
            
        Returns:
            Dict containing the file tree and summary information
        """
        repo_path = Path(repo_path)
        file_tree = self._scan_directory(repo_path)
        
        # Count total files
        total_files = self._count_files(file_tree)
        
        summary = {
            "total_files": total_files,
            "root_path": str(repo_path),
            "analysis_timestamp": __import__('datetime').datetime.now().isoformat()
        }
        
        return {
            "file_tree": file_tree,
            "summary": summary
        }
    
    def _matches_pattern(self, name: str, patterns: List[str]) -> bool:
        """
        Check if a filename matches any of the given patterns.
        
        Args:
            name: Filename to check
            patterns: List of patterns to match against
            
        Returns:
            True if the name matches any pattern, False otherwise
        """
        import fnmatch
        
        for pattern in patterns:
            if fnmatch.fnmatch(name, pattern):
                return True
        return False
    
    def _should_exclude(self, path: Path) -> bool:
        """
        Determine if a path should be excluded based on exclude patterns.
        
        Args:
            path: Path to check
            
        Returns:
            True if the path should be excluded, False otherwise
        """
        # Check if any part of the path matches exclusion patterns
        for part in path.parts:
            if self._matches_pattern(part, self.exclude_patterns):
                return True
        
        # Check the full path name
        if self._matches_pattern(path.name, self.exclude_patterns):
            return True
        
        return False
    
    def _scan_directory(self, directory: Path) -> Dict:
        """
        Recursively scan a directory and return its structure.
        
        Args:
            directory: Directory to scan
            
        Returns:
            Dict representing the directory structure
        """
        result = {
            "type": "directory",
            "name": directory.name,
            "path": str(directory),
            "children": []
        }
        
        try:
            for item in directory.iterdir():
                if self._should_exclude(item):
                    continue
                
                if item.is_file():
                    # Check if file should be included
                    if self.include_patterns:
                        included = any(
                            self._matches_pattern(item.name, [pattern]) 
                            for pattern in self.include_patterns
                        )
                        if not included:
                            continue
                    
                    file_stat = item.stat()
                    file_info = {
                        "type": "file",
                        "name": item.name,
                        "path": str(item),
                        "size": file_stat.st_size,
                        "extension": item.suffix.lower() if item.suffix else "",
                        "modified": __import__('datetime').datetime.fromtimestamp(file_stat.st_mtime).isoformat()
                    }
                    result["children"].append(file_info)
                
                elif item.is_dir():
                    subdir_info = self._scan_directory(item)
                    result["children"].append(subdir_info)
        
        except PermissionError:
            # Handle case where directory is not accessible
            pass
        
        return result
    
    def _count_files(self, tree: Dict) -> int:
        """
        Count the total number of files in the tree structure.
        
        Args:
            tree: Tree structure to count files in
            
        Returns:
            Total number of files
        """
        count = 0
        
        if tree["type"] == "file":
            count = 1
        elif tree["type"] == "directory" and "children" in tree:
            for child in tree["children"]:
                count += self._count_files(child)
        
        return count