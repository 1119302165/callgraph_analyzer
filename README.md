# 调用图分析器

调用图分析器是一个用于分析代码仓库并生成函数调用关系图的工具。它支持多种编程语言，包括 Python、Java、JavaScript 等。

## 功能特性

- 分析多种编程语言的代码仓库
- 生成函数/方法间的调用关系
- 输出 JSON 格式的分析结果
- 支持可视化调用图

## 安装依赖

在使用之前，请确保安装了必要的依赖：

```bash
pip install tree-sitter tree-sitter-python tree-sitter-java tree-sitter-javascript tree-sitter-typescript tree-sitter-cpp tree-sitter-c-sharp tree-sitter-php
```

## 使用方法

### 命令行使用

分析代码仓库：

```bash
python -m callgraph_analyzer.cli analyze <repo_path> -o <output_path>
```

参数说明：
- `<repo_path>`: 要分析的代码仓库路径
- `<output_path>`: 输出 JSON 文件路径

示例：
```bash
python -m callgraph_analyzer.cli analyze "/path/to/your/code/repo" -o "/path/to/output/results.json"
```

### 生成可视化

将分析结果转换为 DOT 格式：

```bash
python -m callgraph_analyzer.cli visualize <input_json> -o <output_dot>
```

参数说明：
- `<input_json>`: 包含分析结果的 JSON 文件
- `<output_dot>`: 输出 DOT 文件路径

## 输出格式

分析结果以 JSON 格式输出，包含以下字段：

- `components`: 代码组件列表，包括函数、类等
- `depends_on`: 组件间的依赖关系
- `leaf_nodes`: 没有调用其他组件的节点
- `summary`: 分析结果摘要

## API 使用

也可以在代码中直接使用：

```python
from callgraph_analyzer.cli import analyze_repository

# 分析仓库并保存结果
results = analyze_repository('/path/to/repo', '/path/to/output.json')
```

## 支持的语言

- Python
- Java
- JavaScript/TypeScript
- C/C++
- C#
- PHP
- 其他通过 tree-sitter 支持的语言

## 依赖关系

`depends_on` 字段包含了组件间的依赖关系，表示当前组件调用了哪些其他组件。这有助于理解代码的调用链和依赖结构。