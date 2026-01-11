"""
Setup script for initializing tree-sitter parsers for the call graph analyzer.
"""
import os
from pathlib import Path
from tree_sitter import Language


def setup_parsers():
    """
    Setup tree-sitter parsers for all supported languages.
    """
    # 获取当前脚本所在目录
    current_dir = Path(__file__).parent
    build_dir = current_dir / "build"
    build_dir.mkdir(exist_ok=True)
    
    # 创建各种语言的解析器
    parsers = {}
    
    # Python parser (using built-in)
    try:
        import tree_sitter_python
        PY_LANGUAGE = Language(tree_sitter_python.language())
        parsers['python'] = PY_LANGUAGE
    except ImportError:
        print("Warning: tree_sitter_python not available")
    
    # JavaScript parser
    try:
        import tree_sitter_javascript
        JS_LANGUAGE = Language(tree_sitter_javascript.language())
        parsers['javascript'] = JS_LANGUAGE
    except ImportError:
        print("Warning: tree_sitter_javascript not available")
    
    # TypeScript parser
    try:
        import tree_sitter_typescript
        TS_LANGUAGE = Language(tree_sitter_typescript.language_typescript())  # TypeScript has separate functions for ts and tsx
        parsers['typescript'] = TS_LANGUAGE
    except ImportError:
        print("Warning: tree_sitter_typescript not available")
    
    # Java parser
    try:
        import tree_sitter_java
        JAVA_LANGUAGE = Language(tree_sitter_java.language())
        parsers['java'] = JAVA_LANGUAGE
    except ImportError:
        print("Warning: tree_sitter_java not available")
    
    # C++ parser
    try:
        import tree_sitter_cpp
        CPP_LANGUAGE = Language(tree_sitter_cpp.language())
        parsers['cpp'] = CPP_LANGUAGE
    except ImportError:
        print("Warning: tree_sitter_cpp not available")
    
    # C# parser
    try:
        import tree_sitter_c_sharp
        CSHARP_LANGUAGE = Language(tree_sitter_c_sharp.language())
        parsers['csharp'] = CSHARP_LANGUAGE
    except ImportError:
        print("Warning: tree_sitter_c_sharp not available")
    
    # PHP parser
    try:
        import tree_sitter_php
        PHP_LANGUAGE = Language(tree_sitter_php.language_php())  # PHP uses specific function
        parsers['php'] = PHP_LANGUAGE
    except ImportError:
        print("Warning: tree_sitter_php not available")
    
    return parsers


# 导出解析器字典
PARSERS = setup_parsers()


def get_parser(language: str):
    """
    Get the appropriate parser for the specified language.
    
    Args:
        language: Programming language name
        
    Returns:
        Language parser object or None if not available
    """
    return PARSERS.get(language)