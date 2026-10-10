"""Glint backend package.

The modules are deliberately small and flat:

* :mod:`app.config`            - every limit and path in one place
* :mod:`app.database`          - SQLite persistence (stdlib ``sqlite3``)
* :mod:`app.ocr_service`       - the RapidOCR / ONNX Runtime CPU wrapper
* :mod:`app.document_service`  - validation, image loading, PDF page rendering
* :mod:`app.text_utils`        - text clean-up and regex pattern extraction
* :mod:`app.analytics_service` - pandas summary + one matplotlib chart
* :mod:`app.schemas`           - pydantic response models
* :mod:`app.main`              - the FastAPI application and its routes
"""

__version__ = "1.0.0"
