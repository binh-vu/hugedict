Development
===========

Install from Source
-------------------

.. admonition:: Prerequisite tools/libraries

    1. `maturin <https://github.com/PyO3/maturin>`__
    2. `Rust <https://www.rust-lang.org/>`__
    3. CMake
    4. CLang

If you are inside a virtual environment, you can install it to directly

.. code:: bash

    maturin develop -r  # -r to compile in release mode, it's optional

Otherwise, you can build a wheel and install it

.. code:: bash

    maturin build -r -o dist
    pip install dist/hugedict-*.whl

You can also consult the :source:`containers/manylinux2014_x86_64/Dockerfile` for guidance to install from scratch.

Setup Documentation
-------------------

1. Installing dependencies & copying required files

.. code:: bash

    pip install .
    pip install -r docs/requirements.txt
    cp CHANGELOG.md docs/source/changelog.md

2. Run ``sphinx-autobuild``

.. code:: bash

    sphinx-autobuild docs/source docs/build/html
