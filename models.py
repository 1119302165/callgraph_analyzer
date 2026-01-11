"""
Core models for call graph analysis.
"""

from typing import List, Optional, Set, Dict, Any
from dataclasses import dataclass, field
import json

@dataclass
class Node:
    """Represents a code component (function, class, method, etc.) in the call graph."""
    
    id: str = ""
    name: str = ""
    component_type: str = "function"  # function, method, class, interface, etc.
    file_path: str = ""
    relative_path: str = ""
    source_code: str = ""
    start_line: int = 0
    end_line: int = 0
    has_docstring: bool = False
    docstring: str = ""
    parameters: Optional[List[str]] = None
    node_type: str = "function"  # function, method, class, etc.
    base_classes: Optional[List[str]] = None  # For classes
    class_name: Optional[str] = None  # For methods
    display_name: str = ""
    component_id: str = ""
    depends_on: Set[str] = field(default_factory=set)  # IDs of components this node calls
    api_url: Optional[str] = None  # For controller methods with API mapping annotations
    http_method: Optional[str] = None  # For controller methods, stores HTTP method (GET, POST, etc.)
    
    def model_dump(self) -> Dict[str, Any]:
        """Convert the node to a dictionary representation."""
        return {
            "id": self.id,
            "name": self.name,
            "component_type": self.component_type,
            "file_path": self.file_path,
            "relative_path": self.relative_path,
            "source_code": self.source_code,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "has_docstring": self.has_docstring,
            "docstring": self.docstring,
            "parameters": self.parameters,
            "node_type": self.node_type,
            "base_classes": self.base_classes,
            "class_name": self.class_name,
            "display_name": self.display_name,
            "component_id": self.component_id,
            "depends_on": list(self.depends_on),  # Convert set to list for JSON serialization
            "api_url": self.api_url,
            "http_method": self.http_method,
        }


@dataclass
class CallRelationship:
    """Represents a call relationship between two functions."""
    
    caller: str = ""  # ID of the calling function
    callee: str = ""  # ID of the called function
    call_line: int = 0  # Line number where the call occurs
    is_resolved: bool = False  # Whether the callee was found in the codebase

    def model_dump(self) -> Dict[str, Any]:
        """Convert the relationship to a dictionary representation."""
        return {
            "caller": self.caller,
            "callee": self.callee,
            "call_line": self.call_line,
            "is_resolved": self.is_resolved,
        }