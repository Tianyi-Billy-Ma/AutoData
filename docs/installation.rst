Installation
============

Prerequisites
-------------

-   **Python 3.11+**
-   **uv** (for dependency management)

Steps
-----

1.  **Clone the repository:**

    .. code-block:: bash

        git clone https://github.com/Tianyi-Billy-Ma/AutoData.git
        cd AutoData

2.  **Install dependencies and environment:**

    .. code-block:: bash

        uv sync --group dev,test,docs

3.  **Install browser binaries:**

    .. code-block:: bash

        playwright install
        playwright install-deps
