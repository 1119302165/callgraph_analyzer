"""
Command-line interface for the call graph analyzer.

Provides a simple interface to analyze code repositories and generate function call graphs.
"""

import sys
import json
import argparse
from pathlib import Path
from typing import Dict, Any


def analyze_repository(repo_path: str, output_path: str = None) -> Dict[Any, Any]:
    """
    Analyze a repository and generate a call graph.
    
    Args:
        repo_path: Path to the repository to analyze
        output_path: Optional path to save the results (JSON format)
        
    Returns:
        Dictionary containing analysis results
    """
    # Import here to avoid issues when only using visualize
    from .dependency_graph_builder import DependencyGraphBuilder
    
    print(f"Analyzing repository: {repo_path}")
    
    # Initialize the dependency graph builder
    builder = DependencyGraphBuilder(repo_path)
    
    # Build the dependency graph
    components, leaf_nodes = builder.build_dependency_graph()
    
    print(f"Found {len(components)} components and {len(leaf_nodes)} leaf nodes")
    
    # Prepare results
    results = {
        "components": {comp_id: comp.model_dump() for comp_id, comp in components.items()},
        "leaf_nodes": leaf_nodes,
        "summary": {
            "total_components": len(components),
            "total_leaf_nodes": len(leaf_nodes),
            "repository_path": repo_path
        }
    }
    
    # Save to file if output path provided
    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"Results saved to: {output_path}")
    
    return results


def visualize_results(results: Dict[Any, Any], output_file: str = None, filter_empty_nodes: bool = False):
    """
    Generate a simple visualization of the call graph.
    
    Args:
        results: Results from the analysis
        output_file: Optional file to save visualization (DOT format)
        filter_empty_nodes: Whether to filter out graphs with only one node (effectively empty of relationships)
    """
    components = results["components"]
    relationships = []
    
    # Extract relationships from components
    for comp_id, comp_data in components.items():
        for dep_id in comp_data.get("depends_on", []):
            relationships.append({
                "caller": comp_id,
                "callee": dep_id
            })
    
    # Generate DOT format for graph visualization
    dot_content = "digraph CallGraph {\n"
    dot_content += "  rankdir=TB;\n"
    dot_content += "  node [shape=box];\n\n"
    
    # Identify nodes that have relationships if filter is enabled
    if filter_empty_nodes:
        connected_nodes = set()
        for rel in relationships:
            connected_nodes.add(rel["caller"])
            connected_nodes.add(rel["callee"])
            
        # Only include nodes that participate in relationships
        for comp_id in components.keys():
            if comp_id in connected_nodes:
                # Simplify the node label to just the function name
                comp_name = comp_id.split('.')[-1] if '.' in comp_id else comp_id
                dot_content += f'  "{comp_id}" [label="{comp_name}"];\n'
    else:
        # Include all nodes when filter is disabled
        for comp_id in components.keys():
            # Simplify the node label to just the function name
            comp_name = comp_id.split('.')[-1] if '.' in comp_id else comp_id
            dot_content += f'  "{comp_id}" [label="{comp_name}"];\n'
    
    # Add relationships as edges
    for rel in relationships:
        dot_content += f'  "{rel["caller"]}" -> "{rel["callee"]}";\n'
    
    dot_content += "}\n"
    
    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(dot_content)
        print(f"Visualization saved to: {output_file}")
    
    return dot_content


def trace_api_calls(api_url: str, input_file: str, recursive: bool = False, max_depth: int = 5):
    """
    Trace function call chains based on API URL.
    
    Args:
        api_url: The API URL to search for
        input_file: Path to the JSON file containing analysis results
        recursive: Whether to recursively trace dependencies
        max_depth: Maximum depth for recursive tracing
    """
    # Load the results from JSON file
    with open(input_file, 'r', encoding='utf-8') as f:
        results = json.load(f)
    
    components = results["components"]
    
    # Find components with matching API URL
    matching_components = []
    for comp_id, comp_data in components.items():
        if comp_data.get("api_url") == api_url:
            matching_components.append(comp_id)
    
    if not matching_components:
        print(f"No components found with API URL: {api_url}")
        return
    
    print(f"Found {len(matching_components)} component(s) with API URL: {api_url}")
    
    for comp_id in matching_components:
        comp_data = components[comp_id]
        print(f"\nComponent: {comp_id}")
        print(f"  Name: {comp_data['name']}")
        print(f"  Type: {comp_data['component_type']}")
        print(f"  File: {comp_data['relative_path']}")
        print(f"  API URL: {comp_data['api_url']}")
        print(f"  HTTP Method: {comp_data.get('http_method', 'N/A')}")
        print(f"  Source Code:\n{comp_data['source_code']}")
        
        # Show dependencies (functions called by this component)
        depends_on = comp_data.get("depends_on", [])
        if depends_on:
            print(f"  Depends on ({len(depends_on)} components):")
            for dep_id in depends_on:
                print(f"    - {dep_id}")
                
                if recursive:
                    # Recursively trace dependencies
                    _trace_recursive(dep_id, components, visited={comp_id}, current_depth=1, max_depth=max_depth)
        else:
            print("  No dependencies found")


def _trace_recursive(component_id, components, visited=None, current_depth=0, max_depth=5):
    """
    Helper function to recursively trace dependencies.
    
    Args:
        component_id: Component ID to trace
        components: Dictionary of all components
        visited: Set of already visited components to prevent cycles
        current_depth: Current recursion depth
        max_depth: Maximum allowed recursion depth
    """
    if visited is None:
        visited = set()
    
    # Stop if max depth reached
    if current_depth >= max_depth:
        indent = "    " * current_depth
        print(f"{indent}    (Max depth reached)")
        return
    
    # Prevent circular references
    if component_id in visited:
        indent = "    " * current_depth
        print(f"{indent}    (Circular reference detected, stopping)")
        return
    
    # Add current component to visited set
    new_visited = visited | {component_id}
    
    if component_id in components:
        dep_data = components[component_id]
        indent = "    " * current_depth
        print(f"{indent}      ├─ {component_id}")
        print(f"{indent}      │  ├─ Type: {dep_data['component_type']}")
        print(f"{indent}      │  ├─ File: {dep_data['relative_path']}")
        print(f"{indent}      │  ├─ API URL: {dep_data.get('api_url', 'N/A')}")
        print(f"{indent}      │  ├─ HTTP Method: {dep_data.get('http_method', 'N/A')}")
        print(f"{indent}      │  ├─ Source Code:\n{indent}      │    {dep_data.get('source_code', 'N/A').replace(chr(10), chr(10) + indent + '      │    ')}")
        
        # Get further dependencies
        further_deps = dep_data.get("depends_on", [])
        if further_deps:
            print(f"{indent}      │  └─ Depends on ({len(further_deps)} components):")
            # Only show first few dependencies to avoid cluttering the output
            deps_to_show = min(5, len(further_deps))  # Limit to first 5 dependencies
            for idx, next_dep_id in enumerate(further_deps[:deps_to_show]):
                print(f"{indent}      │    ├─ {next_dep_id}")
                # Continue recursion for this dependency
                _trace_recursive(next_dep_id, components, new_visited, current_depth + 1, max_depth)
            if len(further_deps) > deps_to_show:
                print(f"{indent}      │    └─ ... and {len(further_deps) - deps_to_show} more")
        else:
            print(f"{indent}      │  └─ No further dependencies")
    else:
        indent = "    " * current_depth
        print(f"{indent}      ├─ {component_id} (not found in components)")


def search_function_calls(keyword: str, input_file: str, recursive: bool = False, max_depth: int = 5):
    """
    Search for function call chains based on a keyword, showing paths from controllers to matching functions.
    
    Args:
        keyword: The function keyword to search for
        input_file: Path to the JSON file containing analysis results
        recursive: Whether to recursively trace dependencies
        max_depth: Maximum depth for recursive tracing
    """
    # Load the results from JSON file
    with open(input_file, 'r', encoding='utf-8') as f:
        results = json.load(f)
    
    components = results["components"]
    
    # Find components with matching keyword in their name
    matching_components = []
    for comp_id, comp_data in components.items():
        if keyword.lower() in comp_data['name'].lower() or keyword.lower() in comp_id.lower():
            matching_components.append(comp_id)
    
    if not matching_components:
        print(f"No components found with keyword: {keyword}")
        return
    
    print(f"Found {len(matching_components)} component(s) matching keyword: {keyword}")
    
    # Find all controllers that eventually lead to the matching components
    for target_comp_id in matching_components:
        print(f"\nTarget component: {target_comp_id}")
        print(f"Finding paths from controllers to this component...")
        
        # Look for components that depend on the target component
        components_calling_target = []
        for comp_id, comp_data in components.items():
            depends_on_list = comp_data.get("depends_on", [])
            if target_comp_id in depends_on_list:
                components_calling_target.append(comp_id)
        
        if components_calling_target:
            print(f"Components that call {target_comp_id}:")
            for caller_id in components_calling_target:
                caller_data = components[caller_id]
                print(f"  - {caller_id} (Type: {caller_data['component_type']})")
                
                # If caller is not a controller, recursively find controllers that lead to it
                if 'controller' not in caller_data['component_type'].lower():
                    print(f"    Looking for controllers leading to {caller_id}...")
                    find_controllers_to_component(caller_id, components, visited=set(), current_depth=1, max_depth=max_depth)
        else:
            print(f"No components directly call {target_comp_id}. Let's look for potential paths in reverse...")


def find_controllers_to_component(target_component_id, components, visited=None, current_depth=0, max_depth=5):
    """
    Helper function to find controllers that lead to a specific component by traversing backwards.
    
    Args:
        target_component_id: Component ID to find paths to
        components: Dictionary of all components
        visited: Set of already visited components to prevent cycles
        current_depth: Current recursion depth
        max_depth: Maximum allowed recursion depth
    """
    if visited is None:
        visited = set()
    
    # Stop if max depth reached
    if current_depth >= max_depth:
        indent = "    " * current_depth
        print(f"{indent}    (Max depth reached)")
        return
    
    # Prevent circular references
    if target_component_id in visited:
        indent = "    " * current_depth
        print(f"{indent}    (Circular reference detected, stopping)")
        return
    
    # Add current component to visited set
    new_visited = visited | {target_component_id}
    
    if target_component_id in components:
        target_data = components[target_component_id]
        
        # Find all components that call this target component
        callers = []
        for comp_id, comp_data in components.items():
            depends_on_list = comp_data.get("depends_on", [])
            if target_component_id in depends_on_list:
                callers.append(comp_id)
        
        if callers:
            indent = "    " * current_depth
            for caller_id in callers:
                caller_data = components[caller_id]
                print(f"{indent}- {caller_id} (Type: {caller_data['component_type']}) -> {target_component_id}")
                
                # If this caller is a controller, we've found a path
                if 'controller' in caller_data['component_type'].lower() or \
                   ('name' in caller_data and 'controller' in caller_data['name'].lower()) or \
                   ('id' in caller_data and 'controller' in caller_data['id'].lower()):
                    print(f"{indent}  └── FOUND CONTROLLER PATH!")
                else:
                    # Continue searching for controllers that lead to this caller
                    print(f"{indent}  └── Continuing search to find controller...")
                    find_controllers_to_component(caller_id, components, new_visited, current_depth + 1, max_depth)
        else:
            indent = "    " * current_depth
            print(f"{indent}- No direct callers found for {target_component_id}")
    else:
        indent = "    " * current_depth
        print(f"{indent}- {target_component_id} (not found in components)")


def find_call_paths_to_component(target_component_id, components, max_depth=5):
    """
    Find all paths from controllers to a specific target component using BFS-like approach.
    
    Args:
        target_component_id: Component ID to find paths to
        components: Dictionary of all components
        max_depth: Maximum depth for path search
    """
    # First, find all controllers in the system
    controllers = []
    for comp_id, comp_data in components.items():
        if ('controller' in comp_data['component_type'].lower() or 
            'controller' in comp_data.get('name', '').lower() or 
            'controller' in comp_id.lower()):
            controllers.append(comp_id)
    
    if not controllers:
        print("No controllers found in the system.")
        return []
    
    print(f"Found {len(controllers)} controllers to search from: {controllers[:5]}{'...' if len(controllers) > 5 else ''}")
    
    # For each controller, find if there's a path to the target
    all_paths = []
    for controller_id in controllers:
        path = find_single_path(controller_id, target_component_id, components, max_depth)
        if path:
            all_paths.append(path)
    
    return all_paths


def find_single_path(start_component_id, target_component_id, components, max_depth=5):
    """
    Find a single path from start_component_id to target_component_id using DFS.
    
    Args:
        start_component_id: Starting component ID
        target_component_id: Target component ID
        components: Dictionary of all components
        max_depth: Maximum depth for path search
        
    Returns:
        A path as a list of component IDs, or None if no path found
    """
    def dfs(current_id, target, visited, path, depth):
        if depth > max_depth:
            return None
        if current_id == target:
            return path + [current_id]
        if current_id in visited:
            return None
        
        visited.add(current_id)
        path = path + [current_id]
        
        current_comp = components.get(current_id)
        if current_comp:
            depends_on = current_comp.get("depends_on", [])
            for next_id in depends_on:
                result = dfs(next_id, target, visited.copy(), path, depth + 1)
                if result:
                    return result
        
        return None
    
    return dfs(start_component_id, target_component_id, set(), [], 0)


def search_function_calls_keyword(keyword: str, input_file: str, max_depth: int = 5):
    """
    Enhanced search function that finds paths from controllers to components matching the keyword.
    
    Args:
        keyword: The function keyword to search for
        input_file: Path to the JSON file containing analysis results
        max_depth: Maximum depth for path search
    """
    # Load the results from JSON file
    with open(input_file, 'r', encoding='utf-8') as f:
        results = json.load(f)
    
    components = results["components"]
    
    # Find components with matching keyword in their name
    matching_components = []
    for comp_id, comp_data in components.items():
        if keyword.lower() in comp_data['name'].lower() or keyword.lower() in comp_id.lower():
            matching_components.append(comp_id)
    
    if not matching_components:
        print(f"No components found with keyword: {keyword}")
        return
    
    print(f"Found {len(matching_components)} component(s) matching keyword: {keyword}")
    
    # For each matching component, find paths from controllers
    for target_comp_id in matching_components:
        print(f"\nSearching for paths from controllers to: {target_comp_id}")
        
        # Find paths from controllers to this component
        paths = find_call_paths_to_component(target_comp_id, components, max_depth)
        
        if paths:
            print(f"Found {len(paths)} path(s) to {target_comp_id}:")
            for i, path in enumerate(paths):
                print(f"  Path {i+1}:")
                for j, comp_id in enumerate(path):
                    comp_data = components[comp_id]
                    indent = "    " * (j + 1)
                    print(f"{indent}{comp_id} (Type: {comp_data['component_type']})")
                    if comp_data.get('api_url'):
                        print(f"{indent}  API URL: {comp_data['api_url']}")
                    print(f"{indent}  Source Code Preview: {comp_data['source_code'][:100]}...")
        else:
            print(f"  No paths found from controllers to {target_comp_id}")
            
            # As a fallback, show the component details
            comp_data = components[target_comp_id]
            print(f"  Component details:")
            print(f"    Type: {comp_data['component_type']}")
            print(f"    File: {comp_data['relative_path']}")
            print(f"    API URL: {comp_data.get('api_url', 'N/A')}")
            print(f"    Source Code:\n{comp_data['source_code']}")


def main():
    """Main entry point for the command-line interface."""
    parser = argparse.ArgumentParser(
        description="Analyze code repositories and generate function call graphs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s analyze /path/to/repo                    # Analyze repository
  %(prog)s analyze /path/to/repo -o results.json   # Save results to JSON
  %(prog)s visualize results.json -o graph.dot     # Visualize results as DOT
  %(prog)s trace-api /api/users -f results.json    # Trace API calls
  %(prog)s trace-api /api/users -f results.json --recursive  # Trace API calls recursively
        """
    )
    
    # Create subparsers for different commands
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Analyze command
    analyze_parser = subparsers.add_parser('analyze', help='Analyze a repository for call graphs')
    analyze_parser.add_argument('repo_path', help='Path to the repository to analyze')
    analyze_parser.add_argument('-o', '--output', help='Output file path for results (JSON format)')
    
    # Visualize command
    visualize_parser = subparsers.add_parser('visualize', help='Visualize analysis results')
    visualize_parser.add_argument('input_file', help='Input file with analysis results (JSON format)')
    visualize_parser.add_argument('-o', '--output', help='Output file for visualization (DOT format)', 
                                  default='call_graph.dot')
    visualize_parser.add_argument('--filter-empty-node', action='store_true', 
                                 help='Enable filtering of graphs with only one node (by default, graphs with only one node are NOT filtered)')
    
    # Trace API command
    trace_api_parser = subparsers.add_parser('trace-api', help='Trace function call chains by API URL')
    trace_api_parser.add_argument('api_url', help='The API URL to search for (e.g., /api/users)')
    trace_api_parser.add_argument('-f', '--file', required=True, 
                                  help='Input JSON file containing analysis results (e.g., results.json)')
    trace_api_parser.add_argument('--recursive', action='store_true', 
                                  help='Recursively trace all dependencies (default: False)')
    trace_api_parser.add_argument('--max-depth', type=int, default=5, 
                                  help='Maximum depth for recursive tracing (default: 5)')
    
    # New search function command
    search_func_parser = subparsers.add_parser('search-func', help='Search function call chains by keyword')
    search_func_parser.add_argument('keyword', help='The function keyword to search for (e.g., processUser, authenticate)')
    search_func_parser.add_argument('-f', '--file', required=True, 
                                   help='Input JSON file containing analysis results (e.g., results.json)')
    search_func_parser.add_argument('--max-depth', type=int, default=5, 
                                   help='Maximum depth for path search (default: 5)')
    
    args = parser.parse_args()
    
    if args.command == 'analyze':
        try:
            results = analyze_repository(args.repo_path, args.output)
            print("Analysis completed successfully!")
        except Exception as e:
            print(f"Error during analysis: {e}", file=sys.stderr)
            sys.exit(1)
    
    elif args.command == 'visualize':
        try:
            # Load results from JSON file
            with open(args.input_file, 'r', encoding='utf-8') as f:
                results = json.load(f)
            
            # Use the filter_empty_nodes flag based on the argument
            filter_empty = args.filter_empty_node
            visualize_results(results, args.output, filter_empty)
            print("Visualization completed successfully!")
        except Exception as e:
            print(f"Error during visualization: {e}", file=sys.stderr)
            sys.exit(1)
    
    elif args.command == 'trace-api':
        try:
            trace_api_calls(args.api_url, args.file, args.recursive, args.max_depth)
        except Exception as e:
            print(f"Error during API tracing: {e}", file=sys.stderr)
            sys.exit(1)
    
    elif args.command == 'search-func':
        try:
            search_function_calls_keyword(args.keyword, args.file, args.max_depth)
        except Exception as e:
            print(f"Error during function search: {e}", file=sys.stderr)
            sys.exit(1)
    
    elif args.command is None:
        parser.print_help()
        sys.exit(1)
    
    else:
        print(f"Unknown command: {args.command}")
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()