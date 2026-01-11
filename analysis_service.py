"""
Call Graph Analysis Service

Pure call graph analysis functionality without LLM, Git or Docker dependencies.
"""

import logging
import traceback
from typing import Dict, List, Optional
from pathlib import Path

from .call_graph_analyzer import CallGraphAnalyzer
from .repo_analyzer import RepoAnalyzer
from .utils.security import safe_open_text
from .utils.patterns import CODE_EXTENSIONS


logger = logging.getLogger(__name__)


class CallGraphAnalysisService:
    """
    Pure call graph analysis service without external dependencies.
    
    This service handles:
    1. Repository structure analysis
    2. Multi-language AST parsing and call graph generation
    3. Result consolidation
    """

    def __init__(self):
        """Initialize the analysis service with language-specific analyzers."""
        self.call_graph_analyzer = CallGraphAnalyzer()

    def analyze_repository(
        self,
        repo_path: str,
        include_patterns: Optional[List[str]] = None,
        exclude_patterns: Optional[List[str]] = None,
    ) -> Dict[str, any]:
        """
        Perform complete repository analysis including call graph generation.

        Args:
            repo_path: Local repository path to analyze
            include_patterns: File patterns to include (e.g., ['*.py', '*.js'])
            exclude_patterns: Additional patterns to exclude

        Returns:
            Dict with analysis results including functions, relationships, and visualization
        """
        try:
            logger.debug(f"Starting analysis of {repo_path}")

            logger.debug("Analyzing repository file structure...")
            structure_result = self._analyze_structure(repo_path, include_patterns, exclude_patterns)
            logger.debug(f"Found {structure_result['summary']['total_files']} files to analyze.")

            logger.debug("Starting call graph analysis...")
            call_graph_result = self._analyze_call_graph(structure_result["file_tree"], repo_path)
            logger.debug(
                f"Call graph analysis complete. Found {call_graph_result['call_graph']['total_functions']} functions."
            )

            result = {
                "functions": call_graph_result["functions"],
                "relationships": call_graph_result["relationships"],
                "file_tree": structure_result["file_tree"],
                "summary": {
                    **structure_result["summary"],
                    **call_graph_result["call_graph"],
                    "analysis_type": "full",
                    "languages_analyzed": call_graph_result["call_graph"]["languages_found"],
                },
                "visualization": call_graph_result["visualization"],
            }

            logger.debug(
                f"Analysis completed: {result['summary']['total_functions']} functions found"
            )
            return result

        except Exception as e:
            logger.error(f"Analysis failed: {str(e)}", exc_info=True)
            raise RuntimeError(f"Repository analysis failed: {str(e)}")

    def analyze_repository_structure_only(
        self,
        repo_path: str,
        include_patterns: Optional[List[str]] = None,
        exclude_patterns: Optional[List[str]] = None,
    ) -> Dict[str, any]:
        """
        Perform lightweight structure-only analysis without call graph generation.

        Args:
            repo_path: Local repository path to analyze
            include_patterns: File patterns to include
            exclude_patterns: Additional patterns to exclude

        Returns:
            Dict: Repository structure with file tree and summary statistics
        """
        try:
            logger.debug(f"Starting structure analysis of {repo_path}")

            structure_result = self._analyze_structure(repo_path, include_patterns, exclude_patterns)

            result = {
                "file_tree": structure_result["file_tree"],
                "file_summary": {
                    **structure_result["summary"],
                    "analysis_type": "structure_only",
                },
            }

            logger.debug(
                f"Structure analysis completed: {result['file_summary']['total_files']} files found"
            )
            return result

        except Exception as e:
            logger.error(f"Structure analysis failed for {repo_path}: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise RuntimeError(f"Structure analysis failed: {str(e)}") from e

    def _analyze_structure(
        self,
        repo_dir: str,
        include_patterns: Optional[List[str]],
        exclude_patterns: Optional[List[str]],
    ) -> Dict[str, any]:
        """Analyze repository file structure with filtering."""
        logger.debug(
            f"Initializing RepoAnalyzer with include: {include_patterns}, exclude: {exclude_patterns}"
        )
        repo_analyzer = RepoAnalyzer(include_patterns, exclude_patterns)
        return repo_analyzer.analyze_repository_structure(repo_dir)

    def _analyze_call_graph(self, file_tree: Dict[str, any], repo_dir: str) -> Dict[str, any]:
        """
        Perform multi-language call graph analysis.
        """
        logger.debug("Extracting code files from file tree...")
        code_files = self.call_graph_analyzer.extract_code_files(file_tree)

        logger.debug(f"Found {len(code_files)} total code files. Filtering for supported languages.")
        supported_files = self._filter_supported_languages(code_files)
        logger.debug(f"Analyzing {len(supported_files)} supported files.")

        result = self.call_graph_analyzer.analyze_code_files(supported_files, repo_dir)

        result["call_graph"]["supported_languages"] = self._get_supported_languages()
        result["call_graph"]["unsupported_files"] = len(code_files) - len(supported_files)

        return result

    def _filter_supported_languages(self, code_files: List[Dict]) -> List[Dict]:
        """
        Filter code files to only include supported languages.

        Supports Python, JavaScript, TypeScript, Java, C#, C, C++, PHP, Go, and Rust.
        """
        supported_languages = {
            "python",
            "javascript",
            "typescript",
            "java",
            "csharp",
            "c",
            "cpp",
            "php",
        }

        return [
            file_info
            for file_info in code_files
            if file_info.get("language") in supported_languages
        ]

    def _get_supported_languages(self) -> List[str]:
        """Get list of currently supported languages for analysis."""
        return ["python", "javascript", "typescript", "java", "csharp", "c", "cpp", "php"]