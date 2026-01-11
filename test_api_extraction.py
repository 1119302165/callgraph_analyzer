#!/usr/bin/env python3
"""
Test script to verify API URL extraction functionality
"""
import logging
import sys
import os

# 设置日志级别为DEBUG以查看详细输出
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s - %(name)s - %(message)s')

# 将当前目录添加到系统路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

# 导入所需模块
from callgraph_analyzer.analyzers.java import analyze_java_file

def test_api_extraction():
    # 测试用的Java代码
    java_content = """@RestController
public class ChatController {
    @PostMapping(value = "/chat/completions/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public Flux<String> chatCompletionsStream(@RequestBody ChatCompletionRequest request) {
        // method body
    }
    
    @PostMapping("/chat/retrieve")
    public List<RetrievedDocument> retrieveDocuments(@RequestBody ChatCompletionRequest request) {
        // method body
    }
    
    private int countTokens(String text) {
        // helper method without API annotation
        return 0;
    }
}"""

    print("Testing API URL extraction...")
    nodes, relationships = analyze_java_file('test.java', java_content)
    
    print(f"Found {len(nodes)} nodes:")
    for node in nodes:
        if node.component_type == 'method':
            print(f"Method: {node.name}, API URL: {node.api_url}")

if __name__ == "__main__":
    test_api_extraction()