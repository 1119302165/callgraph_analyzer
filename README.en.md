# Call Graph Analyzer

Based on the call graph generation module extracted from https://github.com/FSoft-AI4Code/CodeWiki repository for maintenance and easy expansion of multi-language support and parser optimization.

Call Graph Analyzer is a tool for analyzing code repositories and generating function call relationship graphs. It supports multiple programming languages, including Python, Java, JavaScript, and more.

## Features

- Analyze code repositories in multiple programming languages
- Generate call relationships between functions/methods
- Output analysis results in JSON format
- Support visualization of call graphs

## Installation

Before using, make sure you have installed the necessary dependencies:

```bash
pip install tree-sitter tree-sitter-python tree-sitter-java tree-sitter-javascript tree-sitter-typescript tree-sitter-cpp tree-sitter-c-sharp tree-sitter-php
```

## Usage

### Command Line Usage

Analyze a code repository:

```bash
python -m callgraph_analyzer.cli analyze <repo_path> -o <output_path>
```

Parameters:
- `<repo_path>`: Path to the code repository to analyze
- `<output_path>`: Output JSON file path

Example：
```bash
python -m callgraph_analyzer.cli analyze "/path/to/your/code/repo" -o "/path/to/output/results.json"
```

### Visualization

Convert analysis results to DOT format:

```bash
python -m callgraph_analyzer.cli visualize <input_json> -o <output_dot>
```

Parameters:
- `<input_json>`: JSON file containing analysis results
- `<output_dot>`: Output DOT file path

## Output Format

Analysis results are output in JSON format, containing the following fields:

- `components`: List of code components, including functions, classes, etc.
- `depends_on`: Dependencies between components
- `leaf_nodes`: Nodes that don't call other components
- `summary`: Summary of analysis results

## API Usage

You can also use it directly in your code:

```python
from callgraph_analyzer.cli import analyze_repository

# Analyze repository and save results
results = analyze_repository('/path/to/repo', '/path/to/output.json')
```

## Supported Languages

- Python
- Java
- JavaScript/TypeScript
- C/C++
- C#
- PHP
- Other languages supported via tree-sitter

## Dependencies

The `depends_on` field contains dependencies between components, indicating which other components the current component calls. This helps understand the code's call chain and dependency structure.