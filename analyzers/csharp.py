"""
C# AST analyzer for call graph generation using tree-sitter.
"""
import logging
import os
import traceback
from typing import List, Set, Optional, Tuple
from pathlib import Path
import sys
import os

from tree_sitter import Parser
from ..setup_parser import get_parser
from ..models import Node, CallRelationship

logger = logging.getLogger(__name__)


class TreeSitterCSharpAnalyzer:
    def __init__(self, file_path: str, content: str, repo_path: str = None):
        self.file_path = Path(file_path)
        self.content = content
        self.repo_path = repo_path or ""
        self.nodes: List[Node] = []
        self.call_relationships: List[CallRelationship] = []
        
        self.top_level_nodes = {}
        
        self.seen_relationships = set()

        try:
            csharp_language = get_parser("csharp")
            if csharp_language is None:
                logger.warning("C# parser not available")
                self.parser = None
            else:
                self.parser = Parser()
                self.parser.set_language(csharp_language)

        except Exception as e:
            logger.error(f"Failed to initialize C# parser: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            self.parser = None


    def _add_relationship(self, relationship: CallRelationship) -> bool:
        rel_key = (relationship.caller, relationship.callee, relationship.call_line)
        
        if rel_key not in self.seen_relationships:
            self.seen_relationships.add(rel_key)
            self.call_relationships.append(relationship)
            return True
        return False

    def analyze(self) -> None:
        if self.parser is None:
            logger.warning(f"Skipping {self.file_path} - parser initialization failed")
            return

        try:
            tree = self.parser.parse(bytes(self.content, "utf8"))
            root_node = tree.root_node

            logger.debug(f"Parsed AST with root node type: {root_node.type}")

            self._extract_functions(root_node)
            self._extract_call_relationships(root_node)

            logger.debug(
                f"Analysis complete: {len(self.nodes)} nodes, {len(self.call_relationships)} relationships"
            )

        except Exception as e:
            logger.error(f"Error analyzing C# file {self.file_path}: {e}", exc_info=True)

    def _get_module_path(self) -> str:
        if self.repo_path:
            try:
                rel_path = os.path.relpath(str(self.file_path), self.repo_path)
            except ValueError:
                rel_path = str(self.file_path)
        else:
            rel_path = str(self.file_path)
        
        for ext in ['.cs']:
            if rel_path.endswith(ext):
                rel_path = rel_path[:-len(ext)]
                break
        return rel_path.replace('/', '.').replace('\\', '.')

    def _get_relative_path(self) -> str:
        if self.repo_path:
            try:
                return os.path.relpath(str(self.file_path), self.repo_path)
            except ValueError:
                return str(self.file_path)
        else:
            return str(self.file_path)

    def _get_component_id(self, name: str, class_name: str = None, is_method: bool = False) -> str:
        module_path = self._get_module_path()
        
        if is_method and class_name:
            return f"{module_path}.{class_name}.{name}"
        elif class_name and not is_method: 
            return f"{module_path}.{name}"
        else:  
            return f"{module_path}.{name}"

    def _extract_functions(self, node) -> None:
        self._traverse_for_functions(node)
        self.nodes.sort(key=lambda n: n.start_line)

    def _traverse_for_functions(self, node) -> None:
        if node.type in ["class_declaration"]:
            cls = self._extract_class_declaration(node)
            if cls:
                self.nodes.append(cls)
                self.top_level_nodes[cls.name] = cls
                
                self._extract_methods_from_class(node, cls.name)
        
        elif node.type == "interface_declaration":
            interface = self._extract_interface_declaration(node)
            if interface:
                self.nodes.append(interface)
                self.top_level_nodes[interface.name] = interface
                
                self._extract_methods_from_interface(node, interface.name)
        
        elif node.type in ["method_declaration", "constructor_declaration", "local_function_statement"]:
            containing_class = self._find_containing_class(node)
            if containing_class is None:
                method = self._extract_method_declaration(node)
                if method and self._should_include_function(method):
                    self.nodes.append(method)
                    self.top_level_nodes[method.name] = method
        
        for child in node.children:
            self._traverse_for_functions(child)

    def _extract_methods_from_class(self, class_node, class_name: str) -> None:
        class_body = self._find_child_by_type(class_node, "class_declaration")
        if not class_body:
            # Try to find class body differently
            for child in class_node.children:
                if child.type == "declaration_list":
                    class_body = child
                    break
        
        if not class_body:
            return
            
        for child in class_body.children:
            if child.type in ["method_declaration", "constructor_declaration", "local_function_statement"]:
                method_name = self._get_method_name(child)
                if method_name:
                    method_key = f"{self._get_module_path()}.{class_name}.{method_name}"
                    method_node = self._create_method_node(child, method_name, class_name)
                    if method_node:
                        self.top_level_nodes[method_key] = method_node

    def _extract_methods_from_interface(self, interface_node, interface_name: str) -> None:
        interface_body = self._find_child_by_type(interface_node, "declaration_list")
        if not interface_body:
            return
            
        for child in interface_body.children:
            if child.type == "method_declaration":
                method_name = self._get_method_name(child)
                if method_name:
                    method_key = f"{self._get_module_path()}.{interface_name}.{method_name}"
                    method_node = self._create_method_node(child, method_name, interface_name)
                    if method_node:
                        self.top_level_nodes[method_key] = method_node

    def _get_method_name(self, method_node) -> Optional[str]:
        """Get method name from method_declaration or constructor_declaration node."""
        for child in method_node.children:
            if child.type == "identifier":
                return self._get_node_text(child)
        return None

    def _create_method_node(self, node, method_name: str, class_name: str) -> Optional[Node]:
        """Create a method node for relationship mapping."""
        try:
            line_start = node.start_point[0] + 1
            line_end = node.end_point[0] + 1
            component_id = self._get_component_id(method_name, class_name, is_method=True)
            relative_path = self._get_relative_path()
            
            return Node(
                id=component_id,
                name=method_name,
                component_type="method",
                file_path=str(self.file_path),
                relative_path=relative_path,
                source_code="\n".join(self.content.splitlines()[line_start - 1 : line_end]),
                start_line=line_start,
                end_line=line_end,
                has_docstring=False,
                docstring="",
                parameters=None,
                node_type="method",
                base_classes=None,
                class_name=class_name,
                display_name=f"method {method_name}",
                component_id=component_id
            )
        except Exception as e:
            logger.debug(f"Error creating method node for {method_name}: {e}")
            return None

    def _extract_class_declaration(self, node) -> Optional[Node]:
        """Extract class declaration."""
        try:
            name_node = self._find_child_by_type(node, "identifier")
            if not name_node:
                return None
            name = self._get_node_text(name_node)
            line_start = node.start_point[0] + 1
            line_end = node.end_point[0] + 1
            docstring = None
            base_classes = []
            
            # Look for base list (extends/implements)
            for child in node.children:
                if child.type == "base_list":
                    for base_type in child.children:
                        if base_type.type == "identifier" or base_type.type == "generic_name":
                            base_name = self._get_node_text(base_type)
                            if base_name not in [":", ","]:  # Skip punctuation
                                base_classes.append(base_name)
            
            code_snippet = "\n".join(self.content.splitlines()[line_start - 1 : line_end])
            
            component_id = self._get_component_id(name, is_method=False)
            relative_path = self._get_relative_path()
            
            return Node(
                id=component_id,
                name=name,
                component_type="class",
                file_path=str(self.file_path),
                relative_path=relative_path,
                source_code=code_snippet,
                start_line=line_start,
                end_line=line_end,
                has_docstring=bool(docstring),
                docstring=docstring or "",
                parameters=None,
                node_type="class",
                base_classes=base_classes if base_classes else None,
                class_name=None,
                display_name=f"class {name}",
                component_id=component_id,
            )
        except Exception:
            return None

    def _extract_interface_declaration(self, node) -> Optional[Node]:
        """Extract interface declaration."""
        try:
            name_node = self._find_child_by_type(node, "identifier")
            if not name_node:
                return None
            name = self._get_node_text(name_node)
            line_start = node.start_point[0] + 1
            line_end = node.end_point[0] + 1
            docstring = None
            base_classes = []
            
            # Look for base list for interfaces
            for child in node.children:
                if child.type == "base_list":
                    for base_type in child.children:
                        if base_type.type == "identifier" or base_type.type == "generic_name":
                            base_name = self._get_node_text(base_type)
                            if base_name not in [":", ","]:  # Skip punctuation
                                base_classes.append(base_name)
            
            code_snippet = "\n".join(self.content.splitlines()[line_start - 1 : line_end])
            
            component_id = self._get_component_id(name, is_method=False)
            relative_path = self._get_relative_path()
            
            return Node(
                id=component_id,
                name=name,
                component_type="interface",
                file_path=str(self.file_path),
                relative_path=relative_path,
                source_code=code_snippet,
                start_line=line_start,
                end_line=line_end,
                has_docstring=bool(docstring),
                docstring=docstring or "",
                parameters=None,
                node_type="interface",
                base_classes=base_classes if base_classes else None,
                class_name=None,
                display_name=f"interface {name}",
                component_id=component_id,
            )
        except Exception:
            return None

    def _extract_method_declaration(self, node) -> Optional[Node]:
        try:
            name_node = self._find_child_by_type(node, "identifier")
            if not name_node:
                # For method declarations, the name might be nested differently
                for child in node.children:
                    if child.type == "identifier":
                        name_node = child
                        break
            
            if not name_node:
                return None

            method_name = self._get_node_text(name_node)
            line_start = node.start_point[0] + 1
            line_end = node.end_point[0] + 1
            parameters = self._extract_parameters(node)
            code_snippet = self._get_node_text(node)

            # Determine method type
            if node.type == "constructor_declaration":
                display_name = f"constructor {method_name}"
                node_type = "constructor"
            elif node.type == "local_function_statement":
                display_name = f"local function {method_name}"
                node_type = "function"
            else:
                display_name = f"method {method_name}"
                node_type = "method"

            component_id = self._get_component_id(method_name, is_method=False)
            relative_path = self._get_relative_path()

            return Node(
                id=component_id,
                name=method_name,
                component_type=node_type,
                file_path=str(self.file_path),
                relative_path=relative_path,
                source_code=code_snippet,
                start_line=line_start,
                end_line=line_end,
                has_docstring=False,
                docstring="",
                parameters=parameters,
                node_type=node_type,
                base_classes=None,
                class_name=None,
                display_name=display_name,
                component_id=component_id,
            )
        except Exception as e:
            logger.debug(f"Error extracting method declaration: {e}")
            return None

    def _should_include_function(self, func: Node) -> bool:
        excluded_names = {"Main", "main"}  # Exclude main method

        if func.name in excluded_names:
            logger.debug(f"Skipping excluded function: {func.name}")
            return False

        return True

    def _extract_parameters(self, node) -> List[str]:
        parameters = []
        params_node = self._find_child_by_type(node, "parameter_list")
        if params_node:
            for child in params_node.children:
                if child.type == "parameter":
                    # Look for identifier in the parameter
                    for param_child in child.children:
                        if param_child.type == "identifier":
                            parameters.append(self._get_node_text(param_child))
                        elif param_child.type == "variable_declarator":
                            var_id = self._find_child_by_type(param_child, "identifier")
                            if var_id:
                                parameters.append(self._get_node_text(var_id))
        return parameters

    def _extract_call_relationships(self, node) -> None:
        current_top_level = None
        self._traverse_for_calls(node, current_top_level)

    def _traverse_for_calls(self, node, current_top_level) -> None:
        if node.type in ["class_declaration"]:
            name_node = self._find_child_by_type(node, "identifier")
            if name_node:
                current_top_level = self._get_node_text(name_node)
                
                # Handle inheritance relationships
                for child in node.children:
                    if child.type == "base_list":
                        for base_type in child.children:
                            if base_type.type in ["identifier", "generic_name"]:
                                base_name = self._get_node_text(base_type)
                                if base_name not in [":", ","]:  # Skip punctuation
                                    caller_id = self._get_component_id(current_top_level)
                                    callee_id = f"{self._get_module_path()}.{base_name}" 
                                    inheritance_rel = CallRelationship(
                                        caller=caller_id,
                                        callee=callee_id,
                                        call_line=node.start_point[0] + 1,
                                        is_resolved=False
                                    )
                                    self._add_relationship(inheritance_rel)
        
        elif node.type in ["method_declaration", "constructor_declaration", "local_function_statement"]:
            name_node = self._find_child_by_type(node, "identifier")
            if name_node:
                current_top_level = self._get_node_text(name_node)

        # Look for method calls
        if node.type == "invocation_expression" and current_top_level:
            call_info = self._extract_call_from_node(node, current_top_level)
            if call_info:
                self._add_relationship(call_info)
        
        # Look for object instantiation
        elif node.type == "object_creation_expression" and current_top_level:
            callee_name = self._extract_constructor_name(node)
            if callee_name:
                call_info = CallRelationship(
                    caller=f"{self._get_module_path()}.{current_top_level}",
                    callee=f"{self._get_module_path()}.{callee_name}",
                    call_line=node.start_point[0] + 1,
                    is_resolved=False
                )
                self._add_relationship(call_info)

        for child in node.children:
            self._traverse_for_calls(child, current_top_level)

    def _extract_call_from_node(self, node, caller_name: str) -> Optional[CallRelationship]:
        """Extract call relationship from an invocation_expression node."""
        try:
            call_line = node.start_point[0] + 1
            callee_name = self._extract_callee_name(node)
            
            if not callee_name:
                return None
            
            caller_id = f"{self._get_module_path()}.{caller_name}"
            callee_id = f"{self._get_module_path()}.{callee_name}"
            
            if callee_name in self.top_level_nodes:
                return CallRelationship(
                    caller=caller_id,
                    callee=callee_id,
                    call_line=call_line,
                    is_resolved=True,
                )
            
            return CallRelationship(
                caller=caller_id,
                callee=callee_id,
                call_line=call_line,
                is_resolved=False,
            )
            
        except Exception as e:
            logger.debug(f"Error extracting call relationship: {e}")
            return None

    def _extract_constructor_name(self, node) -> Optional[str]:
        """Extract constructor name from object_creation_expression node."""
        type_node = self._find_child_by_type(node, "identifier")
        if type_node:
            return self._get_node_text(type_node)
        # Also check for generic names
        for child in node.children:
            if child.type == "generic_name":
                id_node = self._find_child_by_type(child, "identifier")
                if id_node:
                    return self._get_node_text(id_node)
        return None

    def _extract_callee_name(self, call_node) -> Optional[str]:
        if not call_node.children:
            return None
            
        # Look for the method name in the call
        for child in call_node.children:
            if child.type == "member_access_expression":  # obj.Method() call
                # Get the method name from member access
                for subchild in child.children:
                    if subchild.type == "identifier":
                        # This could be the object or the method name
                        # The method name is typically the last identifier in member access
                        return self._get_node_text(subchild)
            elif child.type == "identifier":  # Direct method call
                return self._get_node_text(child)
        
        # For method calls like obj.methodName, the method name is usually after the dot
        member_access = self._find_child_by_type(call_node, "member_access_expression")
        if member_access:
            for subchild in member_access.children:
                if subchild.type == "identifier":
                    # Get the rightmost identifier (the method name)
                    identifiers = []
                    for subsubchild in member_access.children:
                        if subsubchild.type == "identifier":
                            identifiers.append(self._get_node_text(subsubchild))
                    if identifiers:
                        return identifiers[-1]  # Return the last identifier (method name)
        
        return None

    def _find_child_by_type(self, node, node_type: str):
        """Find first child node of specified type."""
        for child in node.children:
            if child.type == node_type:
                return child
        return None

    def _get_node_text(self, node) -> str:
        start_byte = node.start_byte
        end_byte = node.end_byte
        return self.content.encode("utf8")[start_byte:end_byte].decode("utf8")

    def _find_containing_class(self, method_node) -> Optional[str]:
        """Find the containing class for a method."""
        current = method_node.parent
        while current:
            if current.type == "class_declaration":
                name_node = self._find_child_by_type(current, "identifier")
                if name_node:
                    return self._get_node_text(name_node)
            current = current.parent
        return None


def analyze_csharp_file(
    file_path: str, content: str, repo_path: str = None
) -> Tuple[List[Node], List[CallRelationship]]:
    """Analyze a C# file using tree-sitter."""
    try:
        logger.debug(f"Tree-sitter C# analysis for {file_path}")
        analyzer = TreeSitterCSharpAnalyzer(file_path, content, repo_path)
        analyzer.analyze()
        logger.debug(
            f"Found {len(analyzer.nodes)} top-level nodes, {len(analyzer.call_relationships)} calls"
        )
        return analyzer.nodes, analyzer.call_relationships
    except Exception as e:
        logger.error(f"Error in tree-sitter C# analysis for {file_path}: {e}", exc_info=True)
        return [], []