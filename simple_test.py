import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from analyzers.java import analyze_java_file

# 使用简单的Java内容
java_content = '''
@RestController
@RequestMapping("/chat")
public class RAGService {
    @PostMapping("/completions/stream")
    public ResponseEntity<?> chatCompletionsStream(@RequestBody ChatRequest request) {
        return null;
    }
}
'''

print('Testing API endpoint...')
nodes, relationships = analyze_java_file('RAGService.java', java_content)

print(f'Found {len(nodes)} nodes:')
for node in nodes:
    if hasattr(node, 'api_url') and node.api_url:
        print(f'Method: {node.name}, API URL: {node.api_url}, HTTP Method: {node.http_method}')

# 构建组件数据
components = {}
for node in nodes:
    components[node.id] = node

# 添加依赖关系
if 'RAGService.chatCompletionsStream' in components:
    components['RAGService.chatCompletionsStream'].depends_on = {'SomeService.methodCall'}

# 保存为JSON格式
import json
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
    if isinstance(comp_dict.get('depends_on'), set):
        comp_dict['depends_on'] = list(comp_dict['depends_on'])
    result['components'][comp_id] = comp_dict

with open('chat_results.json', 'w', encoding='utf-8') as f:
    json.dump(result, f, indent=2, ensure_ascii=False)

print('\nTest data created successfully in chat_results.json')