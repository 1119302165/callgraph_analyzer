# 调用图分析器

基于 https://github.com/FSoft-AI4Code/CodeWiki 仓库 调用图生成模块提取出来作为维护，便于扩展多语言和解析器优化。

调用图分析器是一个用于分析代码仓库并生成函数调用关系图的工具。它支持多种编程语言，包括 Python、Java、JavaScript 等。

## 功能特性

- 分析多种编程语言的代码仓库
- 生成函数/方法间的调用关系
- 输出 JSON 格式的分析结果
- 支持可视化调用图
- 支持API端点追踪和函数调用链搜索

## 安装依赖

在使用之前，请确保安装了必要的依赖：

```bash
pip install -r requirements.txt
```

## 使用方法

### 命令行使用

#### 分析代码仓库

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

#### 生成可视化

将分析结果转换为 DOT 格式：

```bash
python -m callgraph_analyzer.cli visualize <input_json> -o <output_dot>
```

参数说明：
- `<input_json>`: 包含分析结果的 JSON 文件
- `<output_dot>`: 输出 DOT 文件路径
- `--filter-empty-node`: 启用过滤空节点模式（只显示有连接关系的节点），默认不启用

#### 追踪API端点调用链

根据API URL追踪函数调用链：

```bash
python -m callgraph_analyzer.cli trace-api <api_url> -f <results_json> [--recursive] [--max-depth N]
```

参数说明：
- `<api_url>`: 要搜索的API URL（例如 /api/users）
- `-f <results_json>`: 包含分析结果的JSON文件路径
- `--recursive`: 是否递归追踪所有依赖（可选）
- `--max-depth N`: 递归追踪的最大深度（默认为5）

示例：
```bash
python -m callgraph_analyzer.cli trace-api "/api/users" -f "results.json"
python -m callgraph_analyzer.cli trace-api "/api/users" -f "results.json" --recursive --max-depth 3
```

#### 搜索函数调用链

根据函数关键词搜索从Controller到目标函数的调用链：

```bash
python -m callgraph_analyzer.cli search-func <keyword> -f <results_json> [--max-depth N]
```

参数说明：
- `<keyword>`: 要搜索的函数关键词（例如 processUser, authenticate）
- `-f <results_json>`: 包含分析结果的JSON文件路径
- `--max-depth N`: 搜索路径的最大深度（默认为5）

示例：
```bash
python -m callgraph_analyzer.cli search-func "processUser" -f "results.json"
python -m callgraph_analyzer.cli search-func "authenticate" -f "results.json" --max-depth 4
```

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