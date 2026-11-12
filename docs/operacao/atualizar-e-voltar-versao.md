# Atualizar e voltar versão

O programa é uma pasta (`QA-SOS-Docs-<versão>`); os dados (banco, configuração do
usuário, pastas de trabalho) ficam em `%LOCALAPPDATA%` e sobrevivem à troca de versão.

## Atualizar

1. Feche o programa.
2. Renomeie a pasta atual para `QA-SOS-Docs-<versão>-anterior` (não apague).
3. Descompacte a versão nova no mesmo lugar e abra o `QA.exe`.

Ao abrir, se a versão nova muda o banco (migração), o programa **copia o banco antes**,
para `backups\antes-de-atualizar` na pasta de dados, e só então aplica as mudanças. A
versão aparece em **Gestão** (versão de cada máquina) e em `/health`.

## Voltar para a versão anterior (menos de 5 minutos)

1. Feche o programa novo.
2. Abra o `QA.exe` da pasta `QA-SOS-Docs-<versão>-anterior`.
3. Se a versão nova tinha mudado o banco, a anterior não abre os dados e mostra o que
   fazer:

   ```text
   QA-suporte.exe backup restore --before-update
   ```

   (rode na pasta da versão anterior, com o programa fechado). Isso põe no lugar a cópia
   feita antes da atualização; o banco da versão nova fica guardado ao lado, com
   `antes-da-restauracao` no nome.
4. Abra o `QA.exe` da versão anterior de novo.

As decisões tomadas **antes** da atualização voltam todas. As tomadas na versão nova
não estão na cópia, mas não se perdem: o banco da versão nova fica guardado ao lado
(`antes-da-restauracao`) e volta com `QA-suporte.exe backup restore <esse arquivo>` quando
a versão nova corrigida for instalada. As pastas originais dos lotes nunca são tocadas.
