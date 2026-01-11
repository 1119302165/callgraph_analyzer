"""
C++ AST analyzer for call graph generation using tree-sitter.
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


class TreeSitterCppAnalyzer:
    def __init__(self, file_path: str, content: str, repo_path: str = None):
        self.file_path = Path(file_path)
        self.content = content
        self.repo_path = repo_path or ""
        self.nodes: List[Node] = []
        self.call_relationships: List[CallRelationship] = []
        
        self.top_level_nodes = {}
        
        self.seen_relationships = set()

        try:
            cpp_language = get_parser("cpp")
            if cpp_language is None:
                logger.warning("C++ parser not available")
                self.parser = None
            else:
                self.parser = Parser()
                self.parser.set_language(cpp_language)

        except Exception as e:
            logger.error(f"Failed to initialize C++ parser: {e}")
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
            logger.error(f"Error analyzing C++ file {self.file_path}: {e}", exc_info=True)

    def _get_module_path(self) -> str:
        if self.repo_path:
            try:
                rel_path = os.path.relpath(str(self.file_path), self.repo_path)
            except ValueError:
                rel_path = str(self.file_path)
        else:
            rel_path = str(self.file_path)
        
        for ext in ['.cpp', '.cxx', '.cc', '.c', '.hpp', '.hxx', '.h']:
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
        if node.type in ["class_specifier", "struct_specifier"]:
            cls = self._extract_class_declaration(node)
            if cls:
                self.nodes.append(cls)
                self.top_level_nodes[cls.name] = cls
                
                self._extract_methods_from_class(node, cls.name)
        
        elif node.type == "function_definition":
            containing_class = self._find_containing_class(node)
            if containing_class is None:
                func = self._extract_function_definition(node)
                if func and self._should_include_function(func):
                    self.nodes.append(func)
                    self.top_level_nodes[func.name] = func
        
        elif node.type == "function_declarator":
            # Handle function declarations in headers
            func = self._extract_function_declaration(node)
            if func and self._should_include_function(func):
                self.nodes.append(func)
                self.top_level_nodes[func.name] = func
        
        for child in node.children:
            self._traverse_for_functions(child)

    def _extract_methods_from_class(self, class_node, class_name: str) -> None:
        for child in class_node.children:
            if child.type in ["function_definition", "declaration"]:
                # Check if this is a method definition inside the class
                method_name = self._get_method_name(child)
                if method_name:
                    method_key = f"{self._get_module_path()}.{class_name}.{method_name}"
                    method_node = self._create_method_node(child, method_name, class_name)
                    if method_node:
                        self.top_level_nodes[method_key] = method_node

    def _get_method_name(self, method_node) -> Optional[str]:
        """Get method name from function_definition or declaration node."""
        for child in method_node.children:
            if child.type in ["declarator", "function_declarator"]:
                return self._extract_function_name(child)
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
        """Extract class or struct declaration."""
        try:
            name_node = None
            for child in node.children:
                if child.type == "type_identifier" or child.type == "identifier":
                    name_node = child
                    break
            
            if not name_node:
                return None
                
            name = self._get_node_text(name_node)
            line_start = node.start_point[0] + 1
            line_end = node.end_point[0] + 1
            docstring = None
            base_classes = []
            
            # Look for base classes (inheritance)
            for child in node.children:
                if child.type == "base_class_clause":
                    for base in child.children:
                        if base.type == "type_identifier":
                            base_classes.append(self._get_node_text(base))
            
            code_snippet = "\n".join(self.content.splitlines()[line_start - 1 : line_end])
            
            node_type = "class" if node.type == "class_specifier" else "struct"
            display_name = f"{node_type} {name}"
            
            component_id = self._get_component_id(name, is_method=False)
            relative_path = self._get_relative_path()
            
            return Node(
                id=component_id,
                name=name,
                component_type=node_type,
                file_path=str(self.file_path),
                relative_path=relative_path,
                source_code=code_snippet,
                start_line=line_start,
                end_line=line_end,
                has_docstring=bool(docstring),
                docstring=docstring or "",
                parameters=None,
                node_type=node_type,
                base_classes=base_classes if base_classes else None,
                class_name=None,
                display_name=display_name,
                component_id=component_id,
            )
        except Exception:
            return None

    def _extract_function_definition(self, node) -> Optional[Node]:
        """Extract function definition."""
        try:
            # Look for the function name in the declarator
            declarator = None
            for child in node.children:
                if child.type in ["declarator", "function_declarator"]:
                    declarator = child
                    break
            
            if not declarator:
                return None
            
            # Extract function name from the declarator
            name = self._extract_function_name(declarator)
            if not name:
                return None
            
            line_start = node.start_point[0] + 1
            line_end = node.end_point[0] + 1
            parameters = self._extract_parameters(declarator)
            code_snippet = "\n".join(self.content.splitlines()[line_start - 1 : line_end])
            
            # Determine if this is a constructor/destructor by checking name and class context
            display_name = f"function {name}"
            node_type = "function"
            
            # Check if this might be a constructor or destructor
            containing_class = self._find_containing_class(node)
            if containing_class:
                if name == containing_class:
                    display_name = f"constructor {name}"
                    node_type = "constructor"
                elif name.startswith('~') and name[1:] == containing_class:
                    display_name = f"destructor {name}"
                    node_type = "destructor"
                else:
                    display_name = f"method {name}"
                    node_type = "method"
            
            component_id = self._get_component_id(name, containing_class, node_type in ["method", "constructor", "destructor"])
            relative_path = self._get_relative_path()
            
            return Node(
                id=component_id,
                name=name,
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
                class_name=containing_class,
                display_name=display_name,
                component_id=component_id,
            )
        except Exception as e:
            logger.debug(f"Error extracting function definition: {e}")
            return None

    def _extract_function_declaration(self, node) -> Optional[Node]:
        """Extract function declaration."""
        try:
            # Extract function name from the declarator
            name = self._extract_function_name(node)
            if not name:
                return None
            
            line_start = node.start_point[0] + 1
            line_end = node.end_point[0] + 1
            parameters = self._extract_parameters(node)
            code_snippet = self._get_node_text(node)
            
            component_id = self._get_component_id(name)
            relative_path = self._get_relative_path()
            
            return Node(
                id=component_id,
                name=name,
                component_type="function",
                file_path=str(self.file_path),
                relative_path=relative_path,
                source_code=code_snippet,
                start_line=line_start,
                end_line=line_end,
                has_docstring=False,
                docstring="",
                parameters=parameters,
                node_type="function",
                base_classes=None,
                class_name=None,
                display_name=f"function {name}",
                component_id=component_id,
            )
        except Exception as e:
            logger.debug(f"Error extracting function declaration: {e}")
            return None

    def _extract_function_name(self, node) -> Optional[str]:
        """Extract function name from a declarator node."""
        if node.type == "identifier":
            return self._get_node_text(node)
        
        for child in node.children:
            if child.type == "identifier":
                return self._get_node_text(child)
            elif child.type in ["function_declarator", "init_declarator", "field_declarator"]:
                name = self._extract_function_name(child)
                if name:
                    return name
            elif child.type == "scoped_identifier":
                # Handle namespaced functions like std::function_name
                for subchild in child.children:
                    if subchild.type == "identifier":
                        return self._get_node_text(subchild)
        
        return None

    def _should_include_function(self, func: Node) -> bool:
        excluded_names = {"main", "printf", "scanf", "malloc", "free", "strlen", 
                         "strcpy", "strcmp", "atoi", "itoa", "exit", "assert",
                         "fopen", "fclose", "fread", "fwrite", "fprintf", "fscanf",
                         "puts", "gets", "exit", "abort", "cout", "cin", "cerr"}  # Common C/C++ library functions

        if func.name in excluded_names or func.name.startswith('operator'):
            logger.debug(f"Skipping excluded function: {func.name}")
            return False

        return True

    def _extract_parameters(self, node) -> List[str]:
        parameters = []
        
        # Look for parameter_list in the declarator
        for child in node.children:
            if child.type == "parameter_list":
                for param_node in child.children:
                    if param_node.type == "parameter_declaration":
                        param_name = self._extract_parameter_name(param_node)
                        if param_name:
                            parameters.append(param_name)
            else:
                # Recursively look for parameter_list
                params = self._extract_parameters(child)
                if params:
                    parameters.extend(params)
        
        return parameters

    def _extract_parameter_name(self, param_node) -> Optional[str]:
        """Extract parameter name from a parameter declaration."""
        for child in param_node.children:
            if child.type == "identifier":
                return self._get_node_text(child)
            elif child.type == "parameter_list":
                # Handle function pointer parameters
                continue
            elif child.type == "declarator":
                # Look inside declarators for the identifier
                return self._extract_parameter_name(child)
        return None

    def _extract_call_relationships(self, node) -> None:
        current_top_level = None
        self._traverse_for_calls(node, current_top_level)

    def _traverse_for_calls(self, node, current_top_level) -> None:
        # Look for function calls
        if node.type == "call_expression":
            call_info = self._extract_call_from_node(node)
            if call_info and current_top_level:
                # Update the caller with the current function context
                call_info.caller = f"{self._get_module_path()}.{current_top_level}"
                self._add_relationship(call_info)

        # Find the current function or method context
        if node.type == "function_definition":
            declarator = None
            for child in node.children:
                if child.type in ["declarator", "function_declarator"]:
                    declarator = child
                    break
            
            if declarator:
                current_top_level = self._extract_function_name(declarator)
        elif node.type in ["class_specifier", "struct_specifier"]:
            # Handle methods inside classes
            name_node = None
            for child in node.children:
                if child.type == "type_identifier" or child.type == "identifier":
                    name_node = child
                    break
            if name_node:
                current_top_level = self._get_node_text(name_node)

        for child in node.children:
            self._traverse_for_calls(child, current_top_level)

    def _extract_call_from_node(self, node) -> Optional[CallRelationship]:
        """Extract call relationship from a call_expression node."""
        try:
            call_line = node.start_point[0] + 1
            callee_name = self._extract_callee_name(node)
            
            if not callee_name:
                return None
            
            # We'll set the caller later when we have the function context
            callee_id = f"{self._get_module_path()}.{callee_name}"
            
            # Check if the callee is a known function in our analysis
            is_resolved = callee_name in self.top_level_nodes
            
            return CallRelationship(
                caller="",  # Will be set later with current function context
                callee=callee_id,
                call_line=call_line,
                is_resolved=is_resolved,
            )
            
        except Exception as e:
            logger.debug(f"Error extracting call relationship: {e}")
            return None

    def _extract_callee_name(self, call_node) -> Optional[str]:
        """Extract callee name from a call_expression node."""
        for child in call_node.children:
            if child.type == "identifier":
                return self._get_node_text(child)
            elif child.type == "field_expression":  # For obj.method() calls
                for subchild in child.children:
                    if subchild.type == "field_identifier":
                        return self._get_node_text(subchild)
            elif child.type == "function_declarator":  # For function pointers
                name = self._extract_function_name(child)
                if name:
                    return name
            elif child.type == "scoped_identifier":  # For namespaced calls like std::function
                for subchild in child.children:
                    if subchild.type == "identifier":
                        # Return the last identifier (function name)
                        return self._get_node_text(subchild)
            elif child.type == "qualified_identifier":  # For class::method calls
                for subchild in child.children:
                    if subchild.type == "identifier":
                        # Return the last identifier (method name)
                        return self._get_node_text(subchild)
        
        # Look for the function name in the first child
        if call_node.children:
            first_child = call_node.children[0]
            if first_child.type == "identifier":
                return self._get_node_text(first_child)
            elif first_child.type == "field_expression":
                for subchild in first_child.children:
                    if subchild.type == "field_identifier":
                        return self._get_node_text(subchild)
            elif first_child.type == "qualified_identifier":
                for subchild in first_child.children:
                    if subchild.type == "identifier":
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
            if current.type in ["class_specifier", "struct_specifier"]:
                # Find the class name
                for child in current.children:
                    if child.type == "type_identifier" or child.type == "identifier":
                        return self._get_node_text(child)
            current = current.parent
        return None


def analyze_cpp_file(
    file_path: str, content: str, repo_path: str = None
) -> Tuple[List[Node], List[CallRelationship]]:
    """Analyze a C++ file using tree-sitter."""
    try:
        logger.debug(f"Tree-sitter C++ analysis for {file_path}")
        analyzer = TreeSitterCppAnalyzer(file_path, content, repo_path)
        analyzer.analyze()
        logger.debug(
            f"Found {len(analyzer.nodes)} top-level nodes, {len(analyzer.call_relationships)} calls"
        )
        return analyzer.nodes, analyzer.call_relationships
    except Exception as e:
        logger.error(f"Error in tree-sitter C++ analysis for {file_path}: {e}", exc_info=True)
        return [], []