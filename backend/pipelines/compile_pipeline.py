"""
Compile the Vertex AI retrain pipeline into a JSON package.
"""

from __future__ import annotations

import sys
from pathlib import Path

from kfp.v2 import compiler


CURRENT_DIR = Path(__file__).resolve().parent
BACKEND_ROOT = CURRENT_DIR.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from pipelines.retrain_pipeline import retrain_pipeline


OUTPUT_PATH = CURRENT_DIR / "retrain_pipeline.json"


def main() -> None:
    compiler.Compiler().compile(
        pipeline_func=retrain_pipeline,
        package_path=str(OUTPUT_PATH),
    )
    print(f"Compiled retrain pipeline to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
