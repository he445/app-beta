"""Motor de referência do QA automático de digitalização.

A arquitetura é hexagonal (ADR-0003): ``domain`` não conhece nada,
``detectors`` são funções puras sobre matrizes, ``application`` orquestra os
casos de uso por meio das ``ports`` e ``adapters`` embrulham ferramentas.
"""

__version__ = "0.2.0"
