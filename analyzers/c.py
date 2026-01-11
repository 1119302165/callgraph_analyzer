"""
C AST analyzer for call graph generation using tree-sitter.
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


class TreeSitterCAnalyzer:
    def __init__(self, file_path: str, content: str, repo_path: str = None):
        self.file_path = Path(file_path)
        self.content = content
        self.repo_path = repo_path or ""
        self.nodes: List[Node] = []
        self.call_relationships: List[CallRelationship] = []
        
        self.top_level_nodes = {}
        
        self.seen_relationships = set()

        try:
            c_language = get_parser("c")
            if c_language is None:
                logger.warning("C parser not available")
                self.parser = None
            else:
                self.parser = Parser()
                self.parser.set_language(c_language)

        except Exception as e:
            logger.error(f"Failed to initialize C parser: {e}")
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
            logger.error(f"Error analyzing C file {self.file_path}: {e}", exc_info=True)

    def _get_module_path(self) -> str:
        if self.repo_path:
            try:
                rel_path = os.path.relpath(str(self.file_path), self.repo_path)
            except ValueError:
                rel_path = str(self.file_path)
        else:
            rel_path = str(self.file_path)
        
        for ext in ['.c', '.h']:
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

    def _get_component_id(self, name: str) -> str:
        module_path = self._get_module_path()
        return f"{module_path}.{name}"

    def _extract_functions(self, node) -> None:
        self._traverse_for_functions(node)
        self.nodes.sort(key=lambda n: n.start_line)

    def _traverse_for_functions(self, node) -> None:
        if node.type in ["function_definition"]:
            func = self._extract_function_definition(node)
            if func and self._should_include_function(func):
                self.nodes.append(func)
                self.top_level_nodes[func.name] = func
        
        elif node.type in ["function_declarator", "init_declarator"]:
            # Handle function declarations in headers
            func = self._extract_function_declaration(node)
            if func and self._should_include_function(func):
                self.nodes.append(func)
                self.top_level_nodes[func.name] = func
        
        for child in node.children:
            self._traverse_for_functions(child)

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
            elif child.type in ["function_declarator", "init_declarator"]:
                name = self._extract_function_name(child)
                if name:
                    return name
        
        return None

    def _should_include_function(self, func: Node) -> bool:
        excluded_names = {"main", "printf", "scanf", "malloc", "free", "strlen", 
                         "strcpy", "strcmp", "atoi", "itoa", "exit", "assert",
                         "fopen", "fclose", "fread", "fwrite", "fprintf", "fscanf",
                         "puts", "gets", "exit", "abort"}  # Common C library functions

        if func.name in excluded_names:
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
            else:
                name = self._extract_parameter_name(child)
                if name:
                    return name
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

        # Find the current function context
        if node.type == "function_definition":
            declarator = None
            for child in node.children:
                if child.type in ["declarator", "function_declarator"]:
                    declarator = child
                    break
            
            if declarator:
                current_top_level = self._extract_function_name(declarator)

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
            elif child.type == "field_expression":  # For struct.function calls
                for subchild in child.children:
                    if subchild.type == "field_identifier":
                        return self._get_node_text(subchild)
            elif child.type == "function_declarator":  # For function pointers
                name = self._extract_function_name(child)
                if name:
                    return name
        
        # Look for the function name in the first child
        if call_node.children:
            first_child = call_node.children[0]
            if first_child.type == "identifier":
                return self._get_node_text(first_child)
            elif first_child.type == "field_expression":
                for subchild in first_child.children:
                    if subchild.type == "field_identifier":
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


def analyze_c_file(
    file_path: str, content: str, repo_path: str = None
) -> Tuple[List[Node], List[CallRelationship]]:
    """Analyze a C file using tree-sitter."""
    try:
        logger.debug(f"Tree-sitter C analysis for {file_path}")
        analyzer = TreeSitterCAnalyzer(file_path, content, repo_path)
        analyzer.analyze()
        logger.debug(
            f"Found {len(analyzer.nodes)} top-level nodes, {len(analyzer.call_relationships)} calls"
        )
        return analyzer.nodes, analyzer.call_relationships
    except Exception as e:
        logger.error(f"Error in tree-sitter C analysis for {file_path}: {e}", exc_info=True)
        return [], []