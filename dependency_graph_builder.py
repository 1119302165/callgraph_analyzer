"""
Dependency Graph Builder

Handles dependency analysis and graph building for call graph generation.
"""

import os
import json
from typing import Dict, List, Tuple, Any
from pathlib import Path

from analysis_service import CallGraphAnalysisService
from models import Node


class DependencyGraphBuilder:
    """Handles dependency analysis and graph building for call graph generation."""
    
    def __init__(self, repo_path: str):
        self.repo_path = repo_path
        self.analysis_service = CallGraphAnalysisService()
    
    def build_dependency_graph(self) -> Tuple[Dict[str, Any], List[str]]:
        """
        Build dependency graph from repository, returning components and leaf nodes.
        
        Returns:
            Tuple of (components, leaf_nodes)
        """
        # Analyze the repository
        analysis_result = self.analysis_service.analyze_repository(self.repo_path)
        
        # Convert function data to Node objects
        components = {}
        for func_data in analysis_result["functions"]:
            node = Node(**{k: v for k, v in func_data.items() if k != 'depends_on'})
            # Convert depends_on from list back to set if it was stored as list
            if 'depends_on' in func_data and isinstance(func_data['depends_on'], list):
                node.depends_on = set(func_data['depends_on'])
            elif 'depends_on' in func_data and isinstance(func_data['depends_on'], set):
                node.depends_on = func_data['depends_on']
            else:
                node.depends_on = set()
            components[node.id] = node
        
        # Populate depends_on based on call relationships
        for rel in analysis_result["relationships"]:
            caller_id = rel.get('caller')
            callee_id = rel.get('callee')
            if caller_id in components and callee_id:
                components[caller_id].depends_on.add(callee_id)
        
        # Get leaf nodes (nodes that don't call other nodes in our analysis)
        leaf_nodes = self._get_leaf_nodes(components, analysis_result["relationships"])
        
        return components, leaf_nodes

    def _get_leaf_nodes(self, components: Dict[str, Node], relationships: List[Dict]) -> List[str]:
        """
        Determine leaf nodes (nodes that don't call other nodes).
        
        Args:
            components: Dictionary of all components
            relationships: List of call relationships
            
        Returns:
            List of component IDs that are leaf nodes
        """
        # Start with all nodes as potential leaf nodes
        potential_leafs = set(components.keys())
        
        # Remove any nodes that call other nodes
        for rel in relationships:
            caller_id = rel.get('caller')
            if caller_id in potential_leafs:
                # Check if this caller actually calls other nodes in our components
                callee_id = rel.get('callee')
                if callee_id in components:
                    # This caller calls another node, so it's not a leaf
                    potential_leafs.discard(caller_id)
        
        return list(potential_leafs)
    
    def save_dependency_graph(self, components: Dict[str, Node], output_path: str):
        """
        Save the dependency graph to a JSON file.
        
        Args:
            components: Dictionary of components to save
            output_path: Path to save the dependency graph
        """
        result = {}
        for component_id, component in components.items():
            component_dict = component.model_dump()
            if 'depends_on' in component_dict and isinstance(component_dict['depends_on'], set):
                component_dict['depends_on'] = list(component_dict['depends_on'])
            result[component_id] = component_dict
        
        dir_name = os.path.dirname(output_path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        print(f"Saved {len(components)} components to {output_path}")
        return result