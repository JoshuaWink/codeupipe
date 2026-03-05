"""
Import Pipeline: Standard Python → CUP

Scans a standard Python project, classifies files by directory/role,
and generates CUP Filter/Tap classes plus Pipeline composition code.
"""

from codeupipe import Pipeline
from codeupipe.converter.filters.parse_config import ParseConfigFilter
from codeupipe.converter.filters.scan_project import ScanProjectFilter
from codeupipe.converter.filters.classify_files import ClassifyFilesFilter
from codeupipe.converter.filters.generate_import import GenerateImportFilter
from codeupipe.converter.taps.conversion_log import ConversionLogTap


def build_import_pipeline(log_tap: ConversionLogTap = None) -> Pipeline:
    """
    Build the Standard → CUP import pipeline.

    Steps:
    1. ParseConfig — load .cup.json or pattern defaults
    2. ScanProject — find Python files in the project
    3. ClassifyFiles — map files to roles by directory
    4. GenerateImport — produce CUP Filter/Tap/Pipeline code

    Returns a Pipeline ready to .run() with a Payload containing:
        - project_path: Root directory of the standard Python project
        - config_path (optional): Path to .cup.json
        - pattern (optional): Pattern name fallback
    """
    imp = Pipeline()
    imp.add_filter(ParseConfigFilter(), name="parse_config")
    imp.add_filter(ScanProjectFilter(), name="scan_project")
    imp.add_filter(ClassifyFilesFilter(), name="classify_files")
    imp.add_filter(GenerateImportFilter(), name="generate_import")

    if log_tap:
        imp.add_tap(log_tap, name="conversion_log")

    return imp
