#!/usr/bin/env python3
"""
Script to create test data for API tracing functionality
"""
import json
from callgraph_analyzer.analyzers.java import analyze_java_file
from callgraph_analyzer.models import Node

def create_test_data():
    # 测试您提到的API端点
    java_content = '''@RestController
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
}'''

    print('Testing /chat/completions/stream API endpoint...')
    nodes, relationships = analyze_java_file('ChatController.java', java_content)

    print(f'Found {len(nodes)} nodes:')
    for node in nodes:
        if node.component_type == 'method' and node.api_url:
            print(f'Method: {node.name}, API URL: {node.api_url}, HTTP Method: {node.http_method}')
            print(f'Source Code: {repr(node.source_code[:100])}...')

    # 构建模拟的依赖图
    components = {}
    for node in nodes:
        components[node.id] = node

    # 准备结果格式
    result = {
        'components': {},
        'leaf_nodes': [],
        'summary': {
            'total_components': len(components),
            'total_leaf_nodes': 0,
            'repository_path': '.'
        }
    }

    for comp_id, comp in components.items():
        comp_dict = comp.model_dump()
        if isinstance(comp_dict['depends_on'], set):
            comp_dict['depends_on'] = list(comp_dict['depends_on'])
        result['components'][comp_id] = comp_dict

    # 保存结果
    with open('results.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print('\nTest results created successfully in results.json')
    return result

if __name__ == "__main__":
    create_test_data()