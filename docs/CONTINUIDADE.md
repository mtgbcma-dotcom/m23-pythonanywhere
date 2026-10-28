# Continuidade do Bookstore com Poetry

Dei continuidade ao [módulo 22 — Integração contínua](https://github.com/mtgbcma-dotcom/m22-ci/pull/1) e preservei os modelos, serializers, migração inicial, paginação, autenticação e testes anteriores.

Mantive `pyproject.toml` e `poetry.lock`, com o nome `m57-bookstore`, a partir do [módulo 17 corrigido](https://github.com/mtgbcma-dotcom/m17-token/commit/71a99b1a8a52f6ecc3a58abe914ce75293b01edd). Os dois arquivos são a fonte das dependências do projeto. O Docker instala o ambiente pelo lock utilizando Poetry 2.5.1.

Registrei no manifesto as dependências adicionais necessárias à etapa, mantendo as versões já registradas na base sempre que compatíveis. Não alterei os modelos, serializers, rotas da API nem os testes de funcionalidades.

Mantive os arquivos de requirements como exportações de compatibilidade do lock do Poetry. Para atualizar essas exportações, utilizei `poetry-plugin-export` 1.9.0, com os comandos `poetry export --only main --without-hashes -f requirements.txt -o requirements.txt`.

Validei a instalação com `poetry check --lock` e a construção da imagem. Executei as verificações de Django, migrações e testes utilizando o ambiente instalado pelo Poetry. Os bancos e volumes usados para validar esta correção são separados dos dados da aplicação publicada.

## Resultado da validação em 28/10/2026

Construí a imagem Python 3.13 com Poetry 2.5.1 e confirmei que `poetry check --lock` não apresenta inconsistências. As verificações do Django e de migrações terminaram sem problemas. Executei os 130 testes no PostgreSQL e os mesmos 130 testes no SQLite: todos passaram, sem testes ignorados no Linux. Confirmei também a resolução do serviço `db` e a conexão TCP na porta 5432. 

Mantive os arquivos Python da aplicação e da suíte de testes sem alterações nesta correção.
