#!/usr/bin/env python3
"""
Debug script to understand the AST structure of Java code with annotations
"""
import sys
import os

def debug_ast_structure():
    # Import the same way as in the main code
    from setup_parser import get_parser
    
    # Get the Java language parser
    java_language = get_parser("java")
    if java_language is None:
        print("Java parser not available")
        return
        
    from tree_sitter import Parser
    parser = Parser(java_language)
    
    # Test Java code with class-level annotations (like in the user's example)
    java_code = """@RestController
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
}"""
    
    # Parse the code
    tree = parser.parse(bytes(java_code, "utf8"))
    
    def print_tree(node, indent=0):
        """Recursively print the AST tree structure"""
        newline_replacement = node.text.decode().replace(chr(10), '\\n')
        print("  " * indent + f"{node.type}: '{newline_replacement[:100]}'")
        for child in node.children:
            print_tree(child, indent + 1)
    
    print("AST Structure:")
    print_tree(tree.root_node)

if __name__ == "__main__":
    debug_ast_structure()