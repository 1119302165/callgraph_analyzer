#!/usr/bin/env python3
"""
Test script to verify class-level path prefix functionality
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

def test_class_prefix():
    # 测试用的Java代码，包含类级别的@RequestMapping注解
    java_content = """@RestController
@RequestMapping("/api")
public class FileUploadController {

    private static final Logger logger = LoggerFactory.getLogger(FileUploadController.class);

    @Value("${code2doc.upload.path:${user.home}/.code2doc/zip}")
    private String uploadPath;

    @Value("${code2doc.unzip.path:${user.home}/.code2doc/unzip}")
    private String unzipPath;

    @Autowired
    private TaskService taskService;

    @Autowired
    private RAGService ragService;

    @PostMapping("/upload")
    public ResponseEntity<?> handleFileUpload(@RequestParam("file") MultipartFile file) {
        // method body
    }
    
    @GetMapping("/search")
    public ResponseEntity<?> search(@RequestParam("query") String query) {
        // method body
    }
}"""

    print("Testing class-level path prefix functionality...")
    nodes, relationships = analyze_java_file('test.java', java_content)
    
    print(f"Found {len(nodes)} nodes:")
    for node in nodes:
        if node.component_type == 'method' and node.api_url:
            print(f"Method: {node.name}, API URL: {node.api_url}")

if __name__ == "__main__":
    test_class_prefix()