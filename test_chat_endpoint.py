#!/usr/bin/env python3
"""
Test script to verify API tracing functionality with the specific endpoint mentioned by the user
"""
import json
import logging
from typing import Dict, List
from callgraph_analyzer.models import Node

# 设置日志级别为DEBUG以查看详细输出
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s - %(name)s - %(message)s')

from callgraph_analyzer.analyzers.java import analyze_java_file

def create_chat_endpoint_test():
    """Create test data with the specific API endpoint mentioned by the user"""
    
    # 创建包含您提到的API端点的Java代码
    java_content = """@RestController
@RequestMapping("/chat")
public class RAGService {

    private static final Logger logger = LoggerFactory.getLogger(RAGService.class);

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
        logger.info("Handling request internally");
        return ResponseEntity.ok().build();
    }
    
    private ResponseEntity<?> getAllModels() {
        // 获取模型列表的逻辑
        logger.info("Getting all models internally");
        return ResponseEntity.ok().build();
    }
}"""

    print("Testing the specific API endpoint mentioned by the user...")
    nodes, relationships = analyze_java_file('RAGService.java', java_content)
    
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
    if "RAGService.chatCompletionsStream" in components:
        components["RAGService.chatCompletionsStream"].depends_on = {
            "RAGService.processChatRequest"
        }
    if "RAGService.getModels" in components:
        components["RAGService.getModels"].depends_on = {
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
    with open('chat_results.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    print("\nTest data created successfully in chat_results.json")
    return result

if __name__ == "__main__":
    # 创建测试数据
    test_data = create_chat_endpoint_test()
    
    print("\n" + "="*60)
    print("Test data for /chat/completions/stream endpoint created")
    print("="*60)