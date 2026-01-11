#!/usr/bin/env python3
"""
Test script to verify API tracing functionality with recursive dependency tracking
"""
import json
import logging
from typing import Dict, List
from callgraph_analyzer.models import Node

# 设置日志级别为DEBUG以查看详细输出
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s - %(name)s - %(message)s')

from callgraph_analyzer.analyzers.java import analyze_java_file

def create_test_data():
    """Create test data with the specific scenario mentioned by the user"""
    
    # 创建包含RAGService和Logger的Java代码
    java_content = """@RestController
@RequestMapping("/chat")
public class TestRAGService {
    
    private static final Logger logger = LoggerFactory.getLogger(TestRAGService.class);
    
    @Autowired
    private RAGService ragService;

    @PostMapping("/completions/stream")
    public ResponseEntity<?> chatCompletionsStream(@RequestBody ChatRequest request) {
        logger.info("Processing chat completions stream request");
        return ragService.processChatRequest(request);
    }
    
    @GetMapping("/models")
    public ResponseEntity<?> getModels() {
        logger.info("Getting available models");
        return ragService.getModels();
    }
}

@Service
class RAGService {
    
    private static final Logger logger = LoggerFactory.getLogger(RAGService.class);

    public ResponseEntity<?> processChatRequest(ChatRequest request) {
        logger.info("Processing chat request in RAG service");
        return handleRequest(request);
    }
    
    public ResponseEntity<?> getModels() {
        logger.info("Getting models in RAG service");
        return getAllModels();
    }
    
    private ResponseEntity<?> handleRequest(ChatRequest request) {
        // 处理请求的具体逻辑
        return ResponseEntity.ok().build();
    }
    
    private ResponseEntity<?> getAllModels() {
        // 获取模型列表的逻辑
        return ResponseEntity.ok().build();
    }
}"""

    print("Testing API tracing functionality...")
    nodes, relationships = analyze_java_file('TestRAGService.java', java_content)
    
    print(f"Found {len(nodes)} nodes:")
    for node in nodes:
        if node.component_type == 'method' and node.api_url:
            print(f"Method: {node.name}, API URL: {node.api_url}, HTTP Method: {node.http_method}")

    # 构建模拟的依赖图
    components = {}
    for node in nodes:
        components[node.id] = node
    
    # 手动添加一些依赖关系
    # 控制器方法调用服务方法
    if "TestRAGService.chatCompletionsStream" in components:
        components["TestRAGService.chatCompletionsStream"].depends_on = {
            "RAGService.processChatRequest"
        }
    if "TestRAGService.getModels" in components:
        components["TestRAGService.getModels"].depends_on = {
            "RAGService.getModels"
        }
    if "RAGService.processChatRequest" in components:
        components["RAGService.processChatRequest"].depends_on = {
            "RAGService.handleRequest"
        }
    if "RAGService.getModels" in components:
        components["RAGService.getModels"].depends_on = {
            "RAGService.getAllModels"
        }
    # 添加Logger的依赖
    for comp_id, comp in components.items():
        if "logger" in comp.name.lower() or "log" in comp.name.lower():
            # 模拟Logger相关的内部方法调用
            continue
    
    # 保存为JSON格式供CLI使用
    result = {
        "components": {},
        "leaf_nodes": [],
        "summary": {
            "total_components": len(components),
            "total_leaf_nodes": 0,
            "repository_path": "."
        }
    }
    
    for comp_id, comp in components.items():
        comp_dict = comp.model_dump()
        if isinstance(comp_dict['depends_on'], set):
            comp_dict['depends_on'] = list(comp_dict['depends_on'])
        result["components"][comp_id] = comp_dict
    
    # 保存结果
    with open('test_results.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    print("\nTest data created successfully in test_results.json")
    return result

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


if __name__ == "__main__":
    # 创建测试数据
    test_data = create_test_data()
    
    # 测试API追踪功能
    print("\n" + "="*60)
    print("Testing API Tracing Functionality")
    print("="*60)
    
    # 首先测试非递归模式
    print("\n1. Testing non-recursive API trace for /chat/completions/stream:")
    trace_api_calls("/chat/completions/stream", "test_results.json", recursive=False)
    
    # 然后测试递归模式
    print("\n" + "-"*60)
    print("2. Testing recursive API trace for /chat/completions/stream:")
    trace_api_calls("/chat/completions/stream", "test_results.json", recursive=True, max_depth=3)