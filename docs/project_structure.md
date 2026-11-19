# Project structure

```text
CustomerDocManager/
├── app.py                         # Streamlit entry point
├── pages/                         # Streamlit preview and builder screens
├── document_manager/
│   ├── paths.py                   # Shared paths to project resources
│   ├── database/
│   │   ├── connection.py          # PostgreSQL connections and SQL loader
│   │   ├── repository.py          # Customer/template catalog reads
│   │   ├── metadata.py            # Schema inspection and request validation
│   │   ├── table_query.py         # Metadata-driven row queries
│   │   └── queries/               # Parameterized SQL files
│   ├── services/
│   │   ├── document_service.py    # Data loading and document generation workflow
│   │   └── template_builder.py    # Transactional draft composition
│   └── documents/
│       ├── generation.py          # Whole DOCX and plain-text document generation
│       ├── templating.py          # Plain-text placeholder substitution
│       ├── images.py             # Shared image validation
│       ├── html_document.py      # Supported HTML structure and page settings
│       ├── html_rendering.py     # HTML placeholder/table/image substitution
│       └── exporters/
│           ├── docx.py
│           ├── rtf.py
│           └── pdf.py
├── assets/                        # Fonts and images
├── public_schema/                 # PostgreSQL initialization and assembly procedure
├── examples/
│   ├── docx/                      # Local source templates
│   └── html/                      # Local HTML examples/templates
├── output/                        # Generated files and conversion reports
├── tests/
└── docs/
```

The application entry point is `streamlit run app.py`.
Application modules use the `document_manager` package. For example:

```python
from document_manager.services.document_service import generate_document_from_blocks
from document_manager.database.repository import get_builder_catalog
```

SQL queries are loaded relative to `database/connection.py`; font paths are
resolved through `document_manager.paths`. Neither depends on the current
working directory. SQL initialization remains in `public_schema`, as mounted
by Docker Compose.

Docker Compose runs PostgreSQL and pgAdmin using their upstream images.
Streamlit and document generation run locally; no application image or separate
HTTP API service is needed. Database and pgAdmin data remain in their named volumes.

The former `templates/` and `html_templates/` folders were separated into source
examples and generated output. Files were moved, not discarded. Local examples,
outputs, and tests are ignored by Git.
