"""``python -m qa_engine.entrypoints.desktop`` (e ``QA.exe``)."""

from __future__ import annotations

import multiprocessing

if __name__ == "__main__":
    # Obrigatório no executável: sem isto, cada processo de análise abriria outra cópia do programa.
    multiprocessing.freeze_support()
    from qa_engine.entrypoints.desktop.main import main

    raise SystemExit(main())
