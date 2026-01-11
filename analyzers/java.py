import logging
from typing import List, Optional, Tuple
from pathlib import Path
import sys
import os

from tree_sitter import Parser, Language
import tree_sitter_java
from ..models import Node, CallRelationship

logger = logging.getLogger(__name__)

class TreeSitterJavaAnalyzer:
	def __init__(self, file_path: str, content: str, repo_path: str = None):
		self.file_path = Path(file_path)
		self.content = content
		self.repo_path = repo_path or ""
		self.nodes: List[Node] = []
		self.call_relationships: List[CallRelationship] = []
		self._analyze()
	
	def _get_module_path(self) -> str:
		if self.repo_path:
			try:
				rel_path = os.path.relpath(str(self.file_path), self.repo_path)
			except ValueError:
				rel_path = str(self.file_path)
		else:
			rel_path = str(self.file_path)
		
		for ext in ['.java']:
			if rel_path.endswith(ext):
				rel_path = rel_path[:-len(ext)]
				break
		return rel_path.replace('/', '.').replace('\\', '.')
	
	def _get_relative_path(self) -> str:
		"""Get relative path from repo root."""
		if self.repo_path:
			try:
				return os.path.relpath(str(self.file_path), self.repo_path)
			except ValueError:
				return str(self.file_path)
		else:
			return str(self.file_path)
	
	def _get_component_id(self, name: str, parent_class: str = None) -> str:
		module_path = self._get_module_path()
		if parent_class:
			return f"{module_path}.{parent_class}.{name}"
		else:
			return f"{module_path}.{name}"

	def _analyze(self):
		from ..setup_parser import get_parser
		java_language = get_parser("java")
		if java_language is None:
			logger.warning("Java parser not available")
			return
		
		parser = Parser(java_language)
		
		tree = parser.parse(bytes(self.content, "utf8"))
		self.root_node = tree.root_node  # Store root node for later use
		lines = self.content.splitlines()
		
		top_level_nodes = {}
		
		self._extract_nodes(self.root_node, top_level_nodes, lines)
		
		self._extract_relationships(self.root_node, top_level_nodes)
	
	def _extract_nodes(self, node, top_level_nodes, lines):
		node_type = None
		node_name = None
		
		if node.type == "class_declaration":
			is_abstract = any(c.type == "modifier" and c.text.decode() == "abstract" for c in node.children)
			node_type = "abstract class" if is_abstract else "class"
			name_node = next((c for c in node.children if c.type == "identifier"), None)
			node_name = name_node.text.decode() if name_node else None
		elif node.type == "interface_declaration":
			node_type = "interface"
			name_node = next((c for c in node.children if c.type == "identifier"), None)
			node_name = name_node.text.decode() if name_node else None
		elif node.type == "enum_declaration":
			node_type = "enum"
			name_node = next((c for c in node.children if c.type == "identifier"), None)
			node_name = name_node.text.decode() if name_node else None
		elif node.type == "record_declaration":
			node_type = "record"
			name_node = next((c for c in node.children if c.type == "identifier"), None)
			node_name = name_node.text.decode() if name_node else None
		elif node.type == "annotation_type_declaration":
			node_type = "annotation"
			name_node = next((c for c in node.children if c.type == "identifier"), None)
			node_name = name_node.text.decode() if name_node else None
		elif node.type == "method_declaration":
			node_type = "method"
			name_node = next((c for c in node.children if c.type == "identifier"), None)
			if name_node:
				method_name = name_node.text.decode()
				containing_class = self._find_containing_class_name(node)
				if containing_class:
					node_name = f"{containing_class}.{method_name}"
				else:
					node_name = method_name
		
		if node_type and node_name:
			# Check if this is a controller method and extract API URL
			api_url = None
			if node.type == "method_declaration":
				containing_class_name = self._find_containing_class_name(node)
				logger.debug(f"Processing method in class: {containing_class_name}")
				is_controller = False
				class_path_prefix = None
				if containing_class_name:
					# Check for Controller annotation in the class itself
					class_node = self._find_class_node_by_name(containing_class_name)
					if class_node:
						is_controller = self._is_controller_class(class_node)
						logger.debug(f"Class {containing_class_name} {'is' if is_controller else 'is not'} a Controller based on annotations")
						# Extract path prefix from class annotations
						class_path_prefix = self._extract_path_prefix_from_class_annotations(class_node)
						if class_path_prefix:
							logger.debug(f"Found class path prefix: {class_path_prefix}")
								
					if not is_controller:
						# Fallback: Check if class name contains 'Controller'
						if 'Controller' in containing_class_name or 'controller' in containing_class_name:
							is_controller = True
							logger.debug(f"Class {containing_class_name} identified as Controller based on name")
							
				if is_controller:
					logger.debug(f"Found Controller class: {containing_class_name}, extracting API URL")
					api_url = self._extract_api_url_from_annotations(node)
					# Prepend class path prefix if both exist
					if api_url and class_path_prefix:
						# Ensure proper URL concatenation without double slashes
						if class_path_prefix.endswith('/') and api_url.startswith('/'):
							api_url = class_path_prefix + api_url[1:]
						elif not class_path_prefix.endswith('/') and not api_url.startswith('/'):
							api_url = class_path_prefix + '/' + api_url
						else:
							api_url = class_path_prefix + api_url
						logger.debug(f"Combined API URL with class prefix: {api_url}")
				else:
					logger.debug(f"Class {containing_class_name} is not a Controller, skipping API URL extraction")
			
			component_id = self._get_component_id(node_name)
			relative_path = self._get_relative_path()
			node_obj = Node(
				id=component_id,
				name=node_name,
				component_type=node_type,
				file_path=str(self.file_path),
				relative_path=relative_path,
				source_code="\n".join(lines[node.start_point[0]:node.end_point[0]+1]),
				start_line=node.start_point[0]+1,
				end_line=node.end_point[0]+1,
				has_docstring=False,
				docstring="",
				parameters=None,
				node_type=node_type,
				base_classes=None,
				class_name=None,
				display_name=f"{node_type} {node_name}",
				component_id=component_id,
				depends_on=set(),
				api_url=api_url
			)
			self.nodes.append(node_obj)
			top_level_nodes[node_name] = node_obj
		
		# Recursively process children
		for child in node.children:
			self._extract_nodes(child, top_level_nodes, lines)
	
	def _extract_api_url_from_annotations(self, method_node):
		"""Extract API URL from method annotations like @RequestMapping, @GetMapping, @PostMapping, etc."""
		logger.debug(f"Extracting API URL from method: {method_node.text.decode()[:100]}...")
		
		# Check modifiers of the method node for annotations (this is where annotations like @PostMapping are located)
		for child in method_node.children:
			if child.type == "modifiers":
				logger.debug(f"Found modifiers: {child.text.decode()[:100]}...")
				for modifier_child in child.children:
					if modifier_child.type == "annotation":
						logger.debug(f"Found annotation in modifiers: {modifier_child.text.decode()}")
						url = self._parse_annotation_for_url(modifier_child)
						if url:
							logger.debug(f"Extracted URL from annotation: {url}")
							return url
					elif modifier_child.type == "marker_annotation":
						# Handle marker annotations like @RequestBody
						for marker_child in modifier_child.children:
							if marker_child.type == "annotation":
								logger.debug(f"Found annotation in marker annotation: {marker_child.text.decode()}")
								url = self._parse_annotation_for_url(marker_child)
								if url:
									logger.debug(f"Extracted URL from annotation: {url}")
									return url
		
		# Also check the parent node for annotations that might precede the method
		parent = method_node.parent
		if parent:
			logger.debug(f"Parent node type: {parent.type}")
			# Get siblings of the method node (before the method itself)
			for i, child in enumerate(parent.children):
				if child == method_node:
					logger.debug(f"Found method node at index {i}")
					# Look at preceding nodes for annotations
					for j in range(i-1, -1, -1):
						sibling = parent.children[j]
						logger.debug(f"Checking sibling {j} with type: {sibling.type}")
						if sibling.type == "annotation":
							logger.debug(f"Found annotation: {sibling.text.decode()}")
							url = self._parse_annotation_for_url(sibling)
							if url:
								logger.debug(f"Extracted URL from annotation: {url}")
								return url
						# If sibling is a class_body, look for annotations inside it
						elif sibling.type == "class_body":
							for sub_child in sibling.children:
								if sub_child.type == "annotation":
									logger.debug(f"Found annotation in class body: {sub_child.text.decode()}")
									url = self._parse_annotation_for_url(sub_child)
									if url:
										logger.debug(f"Extracted URL from annotation: {url}")
										return url
					break
		logger.debug("No URL found in annotations for method")
		return None
	
	def _parse_annotation_for_url(self, annotation_node):
		"""Parse annotation to extract URL path."""
		logger.debug(f"Parsing annotation node: {annotation_node.text.decode()}")
		annotation_name = None
		argument_value = None
		
		# Find the annotation name
		for child in annotation_node.children:
			if child.type == "identifier":
				annotation_name = child.text.decode()
				logger.debug(f"Found annotation name: {annotation_name}")
				break
		
		is_spring_annotation = False
		processed_annotation_name = None
		
		if annotation_name and annotation_name in ["RequestMapping", "GetMapping", "PostMapping", "PutMapping", "DeleteMapping", "PatchMapping"]:
			logger.debug(f"Processing Spring annotation: {annotation_name}")
			is_spring_annotation = True
			processed_annotation_name = annotation_name
		elif annotation_name:
			# Check if annotation ends with the expected names (handles full package names like org.springframework.web.bind.annotation.GetMapping)
			trimmed_annotation = annotation_name.split('.')[-1]  # Get the last part after dots
			if trimmed_annotation in ["RequestMapping", "GetMapping", "PostMapping", "PutMapping", "DeleteMapping", "PatchMapping"]:
				logger.debug(f"Processing Spring annotation: {trimmed_annotation}")
				is_spring_annotation = True
				processed_annotation_name = trimmed_annotation
			else:
				logger.debug(f"Annotation {annotation_name} is not a Spring mapping annotation")
		
		# Look for arguments in the annotation if it's a Spring mapping annotation
		if is_spring_annotation:
			for child in annotation_node.children:
				if child.type == "annotation_argument_list":
					logger.debug(f"Found annotation argument list with {len(child.children)} children")
					for arg in child.children:
						logger.debug(f"Processing argument of type: {arg.type}")
						if arg.type == "element_value_pair":
							# Check if this is a 'value' or 'path' argument
							key_node = next((c for c in arg.children if c.type == "identifier"), None)
							if key_node:
								key_text = key_node.text.decode()
								logger.debug(f"Found key node: {key_text}")
								if key_text in ["value", "path"]:
									value_node = next((c for c in arg.children if c.type in ["string_literal", "element_value_array_initializer"]), None)
									if value_node:
										logger.debug(f"Found value node of type: {value_node.type}")
										if value_node.type == "string_literal":
											# Remove quotes from the string literal
											text = value_node.text.decode()
											logger.debug(f"Found string literal: {text}")
											if text.startswith('"') and text.endswith('"'):
												url = text[1:-1]
												logger.debug(f"Extracted URL: {url}")
												return url
										elif value_node.type == "element_value_array_initializer":
											# Handle array initializer like {"/path1", "/path2"}
											logger.debug("Processing array initializer")
											for elem in value_node.children:
												if elem.type == "string_literal":
													text = elem.text.decode()
													logger.debug(f"Found array element: {text}")
													if text.startswith('"') and text.endswith('"'):
														url = text[1:-1]
														logger.debug(f"Extracted URL from array: {url}")
														return url
						elif arg.type == "string_literal" and not argument_value:
							# Direct string argument (like @GetMapping("/path"))
							text = arg.text.decode()
							logger.debug(f"Found direct string argument: {text}")
							if text.startswith('"') and text.endswith('"'):
								url = text[1:-1]
								logger.debug(f"Extracted direct URL: {url}")
								return url
		else:
			logger.debug(f"Annotation {annotation_name} is not a Spring mapping annotation")
		
		logger.debug("No URL found in annotation")
		return None

	def _extract_relationships(self, node, top_level_nodes):
		# 1. Inheritance: Class extends another class
		if node.type == "class_declaration":
			class_name = self._get_identifier_name(node)
			children_types = [c.type for c in node.children]
			
			extends_node = next((c for c in node.children if c.type == "superclass"), None)
			if extends_node:
				base_class_name = self._get_type_name(extends_node)
				if class_name and base_class_name and not self._is_primitive_type(base_class_name):
					caller_id = self._get_component_id(class_name)
					callee_id = self._get_component_id(base_class_name)  
					self.call_relationships.append(CallRelationship(
						caller=caller_id,
						callee=callee_id,  
						call_line=node.start_point[0]+1,
						is_resolved=False  
					))
			else:
				logger.debug(f"   No superclass found for {class_name}")
		
		# 2. Interface Implementation: Class/enum/record implements interface
		if node.type in ["class_declaration", "enum_declaration", "record_declaration"]:
			implementer_name = self._get_identifier_name(node)
			implements_node = next((c for c in node.children if c.type == "super_interfaces"), None)
			if implements_node and implementer_name:
				for child in implements_node.children:
					if child.type == "type_list":
						for type_child in child.children:
							if type_child.type in ["type_identifier", "generic_type"]:
								interface_name = self._get_type_name(type_child)
								if interface_name and not self._is_primitive_type(interface_name):
									caller_id = self._get_component_id(implementer_name)
									callee_id = self._get_component_id(interface_name)  
									self.call_relationships.append(CallRelationship(
										caller=caller_id,
										callee=callee_id,  
										call_line=node.start_point[0]+1,
										is_resolved=False
									))
		
		# 3. Field Type Use: Class has field of another class/interface type
		if node.type == "field_declaration":
			containing_class = self._find_containing_class(node, top_level_nodes)
			type_node = next((c for c in node.children if c.type in ["type_identifier", "generic_type"]), None)
			if containing_class and type_node:
				field_type_name = self._get_type_name(type_node)
				if field_type_name and not self._is_primitive_type(field_type_name):
					self.call_relationships.append(CallRelationship(
						caller=containing_class,
						callee=field_type_name,  
						call_line=node.start_point[0]+1,
						is_resolved=False
					))
		
		# 4. Method Calls: Method calls on objects
		if node.type == "method_invocation":
			containing_class = self._find_containing_class(node, top_level_nodes)
			containing_method = self._find_containing_method(node)
			if containing_class:
				object_name = None
				method_name = None
				
				if node.children:
					first_child = node.children[0]
					if first_child.type == "identifier":
						object_name = first_child.text.decode()
						if len(node.children) >= 3:  
							method_child = node.children[2]
							if method_child.type == "identifier":
								method_name = method_child.text.decode()
				
				if object_name and method_name:
					target_type = None						
					caller_id = containing_method or containing_class
						
					if object_name in top_level_nodes:
						target_type = object_name
					else:
						target_type = self._find_variable_type(node, object_name, top_level_nodes)

					if target_type and not self._is_primitive_type(target_type):
						self.call_relationships.append(CallRelationship(
							caller=caller_id,
							callee=target_type,
							call_line=node.start_point[0]+1,
							is_resolved=False
						))
		
		# 5. Object Creation
		if node.type == "object_creation_expression":
			containing_class = self._find_containing_class(node, top_level_nodes)
			type_node = next((c for c in node.children if c.type in ["type_identifier", "generic_type"]), None)
			if containing_class and type_node:
				created_type = self._get_type_name(type_node)
				if created_type and not self._is_primitive_type(created_type):
					self.call_relationships.append(CallRelationship(
						caller=containing_class,
						callee=created_type,
						call_line=node.start_point[0]+1,
						is_resolved=False
					))
		
		# Recursively process children
		for child in node.children:
			self._extract_relationships(child, top_level_nodes)
	
	def _is_primitive_type(self, type_name: str) -> bool:
		"""Check if type is a Java primitive or common built-in type."""
		primitives = {
			"boolean", "byte", "char", "double", "float", "int", "long", "short",
			"Boolean", "Byte", "Character", "Double", "Float", "Integer", "Long", "Short",
			"String", "Object", "List", "Set", "Map", "Collection", "Optional",
			"void", "Void"
		}
		return type_name in primitives
	
	def _get_identifier_name(self, node):
		"""Get identifier name from a node."""
		name_node = next((c for c in node.children if c.type == "identifier"), None)
		return name_node.text.decode() if name_node else None
	
	def _get_type_name(self, node):
		"""Get type name from a type node."""
		if node.type == "type_identifier":
			return node.text.decode()
		elif node.type == "generic_type":
			type_node = next((c for c in node.children if c.type == "type_identifier"), None)
			return type_node.text.decode() if type_node else None
		elif node.type == "superclass":
			type_node = next((c for c in node.children if c.type == "type_identifier"), None)
			return type_node.text.decode() if type_node else None
		return None
	
	def _find_containing_class(self, node, top_level_nodes):
		current = node.parent
		while current:
			if current.type in ["class_declaration", "interface_declaration", "enum_declaration", "record_declaration", "annotation_type_declaration"]:
				class_name = self._get_identifier_name(current)
				if class_name and class_name in top_level_nodes:
					return self._get_component_id(class_name)  
			current = current.parent
		return None
	
	def _find_variable_type(self, node, variable_name, top_level_nodes):
		method_node = node.parent
		while method_node and method_node.type != "method_declaration":
			method_node = method_node.parent
		
		if method_node:
			for child in method_node.children:
				if child.type == "block":
					variable_type = self._search_variable_declaration(child, variable_name)
					if variable_type:
						return variable_type
		
		class_node = node.parent
		while class_node and class_node.type != "class_declaration":
			class_node = class_node.parent
			
		if class_node:
			for child in class_node.children:
				if child.type == "class_body":
					for body_child in child.children:
						if body_child.type == "field_declaration":
							identifier_node = None
							type_node = None
							for field_child in body_child.children:
								if field_child.type in ["type_identifier", "generic_type"]:
									type_node = field_child
								elif field_child.type == "variable_declarator":
									identifier_node = next((c for c in field_child.children if c.type == "identifier"), None)
								
							if identifier_node and type_node and identifier_node.text.decode() == variable_name:
								field_type = self._get_type_name(type_node)
								return field_type
		
		return None
	
	def _search_variable_declaration(self, block_node, variable_name):
		for child in block_node.children:
			if child.type == "local_variable_declaration":
				type_node = None
				identifier_node = None
				for decl_child in child.children:
					if decl_child.type in ["type_identifier", "generic_type"]:
						type_node = decl_child
					elif decl_child.type == "variable_declarator":
						identifier_node = next((c for c in decl_child.children if c.type == "identifier"), None)
				
				if identifier_node and type_node and identifier_node.text.decode() == variable_name:
					return self._get_type_name(type_node)
			
			elif child.type == "block":
				result = self._search_variable_declaration(child, variable_name)
				if result:
					return result
		
		return None
	
	def _find_containing_class_name(self, node):
		current = node.parent
		while current:
			if current.type in ["class_declaration", "interface_declaration", "enum_declaration", "record_declaration"]:
				name_node = next((c for c in current.children if c.type == "identifier"), None)
				if name_node:
					return name_node.text.decode()
			current = current.parent
		return None
	
	def _find_containing_method(self, node):
		current = node.parent
		while current:
			if current.type == "method_declaration":
				method_name = self._get_identifier_name(current)
				class_name = self._find_containing_class_name(current)
				if method_name and class_name:
					return self._get_component_id(f"{class_name}.{method_name}")
			current = current.parent
		return None
	
	def _find_class_node_by_name(self, class_name):
		"""Find the class node by its name in the AST."""
		def search_in_node(node):
			if node.type == "class_declaration":
				name_node = next((c for c in node.children if c.type == "identifier"), None)
				if name_node and name_node.text.decode() == class_name:
					return node
			for child in node.children:
				result = search_in_node(child)
				if result:
					return result
			return None
		
		root = self._get_root_node()
		if root:
			return search_in_node(root)
		return None

	def _is_controller_class(self, class_node):
		"""Check if a class node has Controller-related annotations."""
		logger.debug(f"Checking if class has Controller annotation")
		# Check for annotations in the class modifiers
		for child in class_node.children:
			if child.type == "modifiers":
				for modifier_child in child.children:
					if modifier_child.type == "annotation" or modifier_child.type == "marker_annotation":
						annotation_node = modifier_child
						if modifier_child.type == "marker_annotation":
							# For marker annotations, look for the annotation inside
							annotation_children = [c for c in modifier_child.children if c.type == "annotation"]
							if annotation_children:
								annotation_node = annotation_children[0]
						annotation_name = None
						for grandchild in annotation_node.children:
							if grandchild.type == "identifier":
								annotation_name = grandchild.text.decode()
								break
						if annotation_name:
							trimmed_annotation = annotation_name.split('.')[-1]
							logger.debug(f"Found class annotation: {trimmed_annotation}")
							if trimmed_annotation in ["Controller", "RestController"]:
								logger.debug(f"Class has Controller annotation: {trimmed_annotation}")
								return True
		return False

	def _extract_path_prefix_from_class_annotations(self, class_node):
		"""Extract path prefix from class level annotations like @RequestMapping("/api")."""
		logger.debug(f"Checking class for path prefix annotations")
		# Check for annotations in the class modifiers
		for child in class_node.children:
			if child.type == "modifiers":
				for modifier_child in child.children:
					if modifier_child.type == "annotation":
						annotation_name = None
						annotation_arg_list = None
						
						for grandchild in modifier_child.children:
							if grandchild.type == "identifier":
								annotation_name = grandchild.text.decode()
							elif grandchild.type == "annotation_argument_list":
								annotation_arg_list = grandchild
						
						if annotation_name:
							trimmed_annotation = annotation_name.split('.')[-1]
							logger.debug(f"Found class annotation: {trimmed_annotation}")
							# Check if it's a request mapping annotation
							if trimmed_annotation in ["RequestMapping", "GetMapping", "PostMapping", 
													 "PutMapping", "DeleteMapping", "PatchMapping"]:
								if annotation_arg_list:
									# Look for 'value' or 'path' argument
									for arg in annotation_arg_list.children:
										if arg.type == "element_value_pair":
											key_node = next((c for c in arg.children if c.type == "identifier"), None)
											if key_node and key_node.text.decode() in ["value", "path"]:
												value_node = next((c for c in arg.children 
															  if c.type in ["string_literal", "element_value_array_initializer"]), None)
												if value_node and value_node.type == "string_literal":
													text = value_node.text.decode()
													if text.startswith('"') and text.endswith('"'):
														path_prefix = text[1:-1]
														logger.debug(f"Found class path prefix: {path_prefix}")
														return path_prefix
										elif arg.type == "string_literal":
											# Direct string argument (like @RequestMapping("/api"))
											text = arg.text.decode()
											if text.startswith('"') and text.endswith('"'):
												path_prefix = text[1:-1]
												logger.debug(f"Found class path prefix: {path_prefix}")
												return path_prefix
		return None

	def _get_root_node(self):
		"""Return the stored root node."""
		return getattr(self, 'root_node', None)

def analyze_java_file(file_path: str, content: str, repo_path: str = None) -> Tuple[List[Node], List[CallRelationship]]:
	analyzer = TreeSitterJavaAnalyzer(file_path, content, repo_path)
	return analyzer.nodes, analyzer.call_relationships
