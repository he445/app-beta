# 0005: SQLite com SQL puro, sem ORM

Status: aceito · Data: 2026-11-05 · Decisores: Everton Ferreira

## Contexto

A PoC precisa guardar lotes, sinalizações e decisões sem infraestrutura, e os dados
precisam ser legíveis por qualquer linguagem (portabilidade).

## Decisão

SQLite num arquivo (`$QA_DATA_DIR/qa.sqlite3`), com migrações numeradas em SQL puro em
`engine/src/qa_engine/adapters/migrations/` aplicadas na abertura. Sem ORM. O relatório
completo é guardado como JSON do contrato; sinalizações ficam numa tabela própria para
receber decisões; a tabela `decisions` é um histórico só de inserção, que mede a precisão
real de cada regra (calibração contínua, seção 10).

## Consequências

- Em servidor multiusuário, o mesmo SQL migra para PostgreSQL com ajustes mínimos.
- Uma única fila de análise por processo (a PoC é monousuário).
