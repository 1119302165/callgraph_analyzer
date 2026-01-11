"""
PHP AST analyzer for call graph generation using tree-sitter.
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


class TreeSitterPHPAnalyzer:
    def __init__(self, file_path: str, content: str, repo_path: str = None):
        self.file_path = Path(file_path)
        self.content = content
        self.repo_path = repo_path or ""
        self.nodes: List[Node] = []
        self.call_relationships: List[CallRelationship] = []
        
        self.top_level_nodes = {}
        
        self.seen_relationships = set()

        try:
            php_language = get_parser("php")
            if php_language is None:
                logger.warning("PHP parser not available")
                self.parser = None
            else:
                self.parser = Parser()
                try:
                    # Try the newer API first (tree-sitter>=0.20.0)
                    self.parser.set_language(php_language)
                except AttributeError:
                    # Fallback to older API if needed
                    self.parser.language = php_language

        except Exception as e:
            logger.error(f"Failed to initialize PHP parser: {e}")
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
            logger.error(f"Error analyzing PHP file {self.file_path}: {e}", exc_info=True)

    def _get_module_path(self) -> str:
        if self.repo_path:
            try:
                rel_path = os.path.relpath(str(self.file_path), self.repo_path)
            except ValueError:
                rel_path = str(self.file_path)
        else:
            rel_path = str(self.file_path)
        
        for ext in ['.php', '.phtml', '.inc']:
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
        
        elif node.type in ["function_definition", "method_declaration", "class_declaration"]:
            if node.type in ["function_definition", "method_declaration"]:
                containing_class = self._find_containing_class(node)
                if containing_class is None:
                    func = self._extract_function_definition(node)
                    if func and self._should_include_function(func):
                        self.nodes.append(func)
                        self.top_level_nodes[func.name] = func
                else:
                    # Handle methods inside classes
                    method = self._extract_method_declaration(node, containing_class)
                    if method and self._should_include_function(method):
                        self.nodes.append(method)
                        method_key = f"{self._get_component_id(method.name, containing_class, is_method=True)}"
                        self.top_level_nodes[method_key] = method
        
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
                elif child.type == "compound_statement":  # For class definitions without explicit declaration_list
                    class_body = child
                    break
        
        if not class_body:
            return
            
        for child in class_body.children:
            if child.type == "method_declaration":
                method_name = self._get_method_name(child)
                if method_name:
                    method_key = f"{self._get_component_id(method_name, class_name, is_method=True)}"
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
                    method_key = f"{self._get_component_id(method_name, interface_name, is_method=True)}"
                    method_node = self._create_method_node(child, method_name, interface_name)
                    if method_node:
                        self.top_level_nodes[method_key] = method_node

    def _get_method_name(self, method_node) -> Optional[str]:
        """Get method name from method_declaration node."""
        for child in method_node.children:
            if child.type == "name":
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
            name_node = self._find_child_by_type(node, "name")
            if not name_node:
                return None
            name = self._get_node_text(name_node)
            line_start = node.start_point[0] + 1
            line_end = node.end_point[0] + 1
            docstring = None
            base_classes = []
            
            # Look for extends and implements clauses
            for child in node.children:
                if child.type == "extends_clause":
                    for ext in child.children:
                        if ext.type == "name":
                            base_classes.append(self._get_node_text(ext))
                elif child.type == "implements_clause":
                    for impl in child.children:
                        if impl.type == "name":
                            base_classes.append(self._get_node_text(impl))
            
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
            name_node = self._find_child_by_type(node, "name")
            if not name_node:
                return None
            name = self._get_node_text(name_node)
            line_start = node.start_point[0] + 1
            line_end = node.end_point[0] + 1
            docstring = None
            base_classes = []
            
            # Look for extends clauses for interfaces
            for child in node.children:
                if child.type == "extends_clause":
                    for ext in child.children:
                        if ext.type == "name":
                            base_classes.append(self._get_node_text(ext))
            
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

    def _extract_function_definition(self, node) -> Optional[Node]:
        try:
            name_node = self._find_child_by_type(node, "name")
            if not name_node:
                return None

            func_name = self._get_node_text(name_node)
            line_start = node.start_point[0] + 1
            line_end = node.end_point[0] + 1
            parameters = self._extract_parameters(node)
            code_snippet = self._get_node_text(node)

            display_name = f"function {func_name}"
            node_type = "function"

            component_id = self._get_component_id(func_name, is_method=False)
            relative_path = self._get_relative_path()

            return Node(
                id=component_id,
                name=func_name,
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
            logger.debug(f"Error extracting function definition: {e}")
            return None

    def _extract_method_declaration(self, node, class_name: str) -> Optional[Node]:
        try:
            name_node = self._find_child_by_type(node, "name")
            if not name_node:
                return None

            method_name = self._get_node_text(name_node)
            line_start = node.start_point[0] + 1
            line_end = node.end_point[0] + 1
            parameters = self._extract_parameters(node)
            code_snippet = self._get_node_text(node)

            display_name = f"method {method_name}"
            node_type = "method"

            component_id = self._get_component_id(method_name, class_name, is_method=True)
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
                class_name=class_name,
                display_name=display_name,
                component_id=component_id,
            )
        except Exception as e:
            logger.debug(f"Error extracting method declaration: {e}")
            return None

    def _should_include_function(self, func: Node) -> bool:
        excluded_names = {"__construct", "__destruct", "__get", "__set", "__isset", "__unset", 
                         "__call", "__callStatic", "__toString", "__invoke", "__set_state", 
                         "__clone", "__debugInfo", "main"}  # PHP magic methods and main

        if func.name in excluded_names:
            logger.debug(f"Skipping excluded function: {func.name}")
            return False

        return True

    def _extract_parameters(self, node) -> List[str]:
        parameters = []
        params_node = self._find_child_by_type(node, "formal_parameters")
        if params_node:
            for child in params_node.children:
                if child.type == "simple_parameter":
                    # Look for variable name in the parameter
                    for param_child in child.children:
                        if param_child.type == "variable_name":
                            param_name = self._get_node_text(param_child)
                            # Remove the $ prefix
                            if param_name.startswith('$'):
                                param_name = param_name[1:]
                            parameters.append(param_name)
        return parameters

    def _extract_call_relationships(self, node) -> None:
        current_top_level = None
        self._traverse_for_calls(node, current_top_level)

    def _traverse_for_calls(self, node, current_top_level) -> None:
        if node.type in ["class_declaration"]:
            name_node = self._find_child_by_type(node, "name")
            if name_node:
                current_top_level = self._get_node_text(name_node)
                
                # Handle inheritance relationships
                for child in node.children:
                    if child.type == "extends_clause":
                        for ext in child.children:
                            if ext.type == "name":
                                base_class = self._get_node_text(ext)
                                caller_id = self._get_component_id(current_top_level)
                                callee_id = f"{self._get_module_path()}.{base_class}" 
                                inheritance_rel = CallRelationship(
                                    caller=caller_id,
                                    callee=callee_id,
                                    call_line=node.start_point[0] + 1,
                                    is_resolved=False
                                )
                                self._add_relationship(inheritance_rel)
        
        elif node.type in ["function_definition", "method_declaration"]:
            name_node = self._find_child_by_type(node, "name")
            if name_node:
                current_top_level = self._get_node_text(name_node)

        # Look for function/method calls
        if node.type == "function_call_expression" and current_top_level:
            call_info = self._extract_call_from_node(node, current_top_level)
            if call_info:
                self._add_relationship(call_info)
        
        # Look for method calls on objects
        elif node.type == "member_call_expression" and current_top_level:
            call_info = self._extract_member_call_from_node(node, current_top_level)
            if call_info:
                self._add_relationship(call_info)

        for child in node.children:
            self._traverse_for_calls(child, current_top_level)

    def _extract_call_from_node(self, node, caller_name: str) -> Optional[CallRelationship]:
        """Extract call relationship from a function_call_expression node."""
        try:
            call_line = node.start_point[0] + 1
            callee_name = self._extract_callee_name(node)
            
            if not callee_name:
                return None
            
            # Remove namespace prefixes for comparison
            callee_name_clean = callee_name.split('\\')[-1]  # Get the actual function name
            
            caller_id = f"{self._get_module_path()}.{caller_name}"
            callee_id = f"{self._get_module_path()}.{callee_name_clean}"
            
            # Check if the callee is a known function in our analysis
            is_resolved = callee_name_clean in self.top_level_nodes
            
            return CallRelationship(
                caller=caller_id,
                callee=callee_id,
                call_line=call_line,
                is_resolved=is_resolved,
            )
            
        except Exception as e:
            logger.debug(f"Error extracting call relationship: {e}")
            return None

    def _extract_member_call_from_node(self, node, caller_name: str) -> Optional[CallRelationship]:
        """Extract call relationship from a member_call_expression node."""
        try:
            call_line = node.start_point[0] + 1
            callee_name = self._extract_method_name(node)
            
            if not callee_name:
                return None
            
            caller_id = f"{self._get_module_path()}.{caller_name}"
            callee_id = f"{self._get_module_path()}.{callee_name}"
            
            # Check if the callee is a known function in our analysis
            is_resolved = callee_name in self.top_level_nodes
            
            return CallRelationship(
                caller=caller_id,
                callee=callee_id,
                call_line=call_line,
                is_resolved=is_resolved,
            )
            
        except Exception as e:
            logger.debug(f"Error extracting member call relationship: {e}")
            return None

    def _extract_callee_name(self, call_node) -> Optional[str]:
        """Extract callee name from a function_call_expression node."""
        for child in call_node.children:
            if child.type == "name":  # Direct function call
                return self._get_node_text(child)
            elif child.type == "qualified_name":  # Namespaced function call
                # Get the full qualified name
                return self._get_node_text(child)
            elif child.type == "member_call_expression":  # Method call
                # For method calls, look for the method name
                for subchild in child.children:
                    if subchild.type == "name":
                        return self._get_node_text(subchild)
        
        # Look for the function name in the first child
        if call_node.children:
            first_child = call_node.children[0]
            if first_child.type == "name":
                return self._get_node_text(first_child)
            elif first_child.type == "qualified_name":
                return self._get_node_text(first_child)
        
        return None

    def _extract_method_name(self, call_node) -> Optional[str]:
        """Extract method name from a member_call_expression node."""
        for child in call_node.children:
            if child.type == "name":  # Method name
                return self._get_node_text(child)
            elif child.type == "field_identifier":  # Alternative for method name
                return self._get_node_text(child)
        
        # Check for member access in children
        for child in call_node.children:
            if child.type == "member_access_expression":
                for subchild in child.children:
                    if subchild.type == "name":
                        return self._get_node_text(subchild)
        
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
                name_node = self._find_child_by_type(current, "name")
                if name_node:
                    return self._get_node_text(name_node)
            current = current.parent
        return None


def analyze_php_file(
    file_path: str, content: str, repo_path: str = None
) -> Tuple[List[Node], List[CallRelationship]]:
    """Analyze a PHP file using tree-sitter."""
    try:
        logger.debug(f"Tree-sitter PHP analysis for {file_path}")
        analyzer = TreeSitterPHPAnalyzer(file_path, content, repo_path)
        analyzer.analyze()
        logger.debug(
            f"Found {len(analyzer.nodes)} top-level nodes, {len(analyzer.call_relationships)} calls"
        )
        return analyzer.nodes, analyzer.call_relationships
    except Exception as e:
        logger.error(f"Error in tree-sitter PHP analysis for {file_path}: {e}", exc_info=True)
        return [], []