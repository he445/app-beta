"""Detectores: uma função pura por defeito (imagem + parâmetros → achados).

Cada regra tem um diretório com ``manifest.yaml`` (validado contra
``contracts/schemas/detector-manifest.schema.json``) e uma especificação em
``docs/especificacoes/detectors/<id>.md``. O registro fica em :mod:`qa_engine.detectors.registry`.
"""
