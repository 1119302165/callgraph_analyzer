# Call Graph Analyzer

Based on the call graph generation module extracted from https://github.com/FSoft-AI4Code/CodeWiki repository for maintenance and easy expansion of multi-language support and parser optimization.

Call Graph Analyzer is a tool for analyzing code repositories and generating function call relationship graphs. It supports multiple programming languages, including Python, Java, JavaScript, and more.

## Features

- Analyze code repositories in multiple programming languages
- Generate call relationships between functions/methods
- Output analysis results in JSON format
- Support visualization of call graphs
- Support API endpoint tracing and function call chain searching

## Installation

Before using, make sure you have installed the necessary dependencies:

```bash
pip install -r requirements.txt
```

## Usage

### Command Line Usage

#### Analyze a Code Repository

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

#### Visualization

Convert analysis results to DOT format:

```bash
python -m callgraph_analyzer.cli visualize <input_json> -o <output_dot>
```

Parameters:
- `<input_json>`: JSON file containing analysis results
- `<output_dot>`: Output DOT file path
- `--filter-empty-node`: Enable filtering of empty nodes (only show nodes with connections), disabled by default

#### Trace API Endpoint Call Chains

Trace function call chains based on API URL:

```bash
python -m callgraph_analyzer.cli trace-api <api_url> -f <results_json> [--recursive] [--max-depth N]
```

Parameters:
- `<api_url>`: The API URL to search for (e.g., /api/users)
- `-f <results_json>`: Input JSON file containing analysis results
- `--recursive`: Whether to recursively trace all dependencies (optional)
- `--max-depth N`: Maximum depth for recursive tracing (default is 5)

Example：
```bash
python -m callgraph_analyzer.cli trace-api "/api/users" -f "results.json"
python -m callgraph_analyzer.cli trace-api "/api/users" -f "results.json" --recursive --max-depth 3
```

#### Search Function Call Chains

Search for call chains from Controller to target function based on function keyword:

```bash
python -m callgraph_analyzer.cli search-func <keyword> -f <results_json> [--max-depth N]
```

Parameters:
- `<keyword>`: The function keyword to search for (e.g., processUser, authenticate)
- `-f <results_json>`: Input JSON file containing analysis results
- `--max-depth N`: Maximum depth for path search (default is 5)

Example：
```bash
python -m callgraph_analyzer.cli search-func "processUser" -f "results.json"
python -m callgraph_analyzer.cli search-func "authenticate" -f "results.json" --max-depth 4
```

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