"""
Export Pipeline: CUP → Standard Python

Analyzes a CUP Pipeline, classifies its steps by architectural role,
and generates standard Python files in the target pattern.
"""

from codeupipe import Pipeline
from codeupipe.converter.filters.parse_config import ParseConfigFilter
from codeupipe.converter.filters.analyze import AnalyzePipelineFilter
from codeupipe.converter.filters.classify import ClassifyStepsFilter
from codeupipe.converter.filters.generate_export import GenerateExportFilter
from codeupipe.converter.taps.conversion_log import ConversionLogTap


def build_export_pipeline(log_tap: ConversionLogTap = None) -> Pipeline:
    """
    Build the CUP → Standard export pipeline.

    Steps:
    1. ParseConfig — load .cup.json or pattern defaults
    2. AnalyzePipeline — introspect the pipeline instance
    3. ClassifySteps — assign steps to architectural roles
    4. GenerateExport — produce standard Python files

    Returns a Pipeline ready to .run() with a Payload containing:
        - pipeline: The CUP Pipeline instance to export
        - config_path (optional): Path to .cup.json
        - pattern (optional): Pattern name fallback
    """
    export = Pipeline()
    export.add_filter(ParseConfigFilter(), name="parse_config")
    export.add_filter(AnalyzePipelineFilter(), name="analyze_pipeline")
    export.add_filter(ClassifyStepsFilter(), name="classify_steps")
    export.add_filter(GenerateExportFilter(), name="generate_export")

    if log_tap:
        export.add_tap(log_tap, name="conversion_log")

    return export
