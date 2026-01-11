#!/usr/bin/env python3
"""
Test script to verify HTTP method recognition functionality
"""
import logging
import sys
import os

# 设置日志级别为DEBUG以查看详细输出
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s - %(name)s - %(message)s')

# 将当前目录添加到系统路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from callgraph_analyzer.analyzers.java import analyze_java_file

def test_http_methods():
    # 测试用的Java代码，包含不同HTTP方法的注解
    java_content = """@RestController
@RequestMapping("/api")
public class FileUploadController {

    @PostMapping("/upload")
    public ResponseEntity<?> handleFileUpload(@RequestParam("file") MultipartFile file) {
        // method body
    }
    
    @GetMapping("/search")
    public ResponseEntity<?> search(@RequestParam("query") String query) {
        // method body
    }
    
    @PutMapping("/update")
    public ResponseEntity<?> update(@RequestParam("id") String id) {
        // method body
    }
    
    @DeleteMapping("/delete/{id}")
    public ResponseEntity<?> delete(@PathVariable("id") String id) {
        // method body
    }
    
    @PatchMapping("/partial-update")
    public ResponseEntity<?> partialUpdate(@RequestParam("id") String id) {
        // method body
    }
    
    @RequestMapping(value = "/generic", method = RequestMethod.POST)
    public ResponseEntity<?> genericPost() {
        // method body
    }
    
    @RequestMapping(value = "/generic-get", method = RequestMethod.GET)
    public ResponseEntity<?> genericGet() {
        // method body
    }
}"""

    print("Testing HTTP method recognition functionality...")
    nodes, relationships = analyze_java_file('test.java', java_content)
    
    print(f"Found {len(nodes)} nodes:")
    for node in nodes:
        if node.component_type == 'method' and node.api_url:
            print(f"Method: {node.name}, API URL: {node.api_url}, HTTP Method: {node.http_method}")

if __name__ == "__main__":
    test_http_methods()