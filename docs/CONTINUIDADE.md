# Continuidade do Bookstore com Poetry

Dei continuidade ao [módulo 22 — Integração contínua](https://github.com/mtgbcma-dotcom/m22-ci/pull/1) e preservei os modelos, serializers, migração inicial, paginação, autenticação e testes anteriores.

Mantive `pyproject.toml` e `poetry.lock`, com o nome `m57-bookstore`, a partir do [módulo 17 corrigido](https://github.com/mtgbcma-dotcom/m17-token/commit/71a99b1a8a52f6ecc3a58abe914ce75293b01edd). Os dois arquivos são a fonte das dependências do projeto. O Docker instala o ambiente pelo lock utilizando Poetry 2.5.1.

Registrei no manifesto as dependências adicionais necessárias à etapa, mantendo as versões já registradas na base sempre que compatíveis. Não alterei os modelos, serializers, rotas da API nem os testes de funcionalidades.

Mantive os arquivos de requirements como exportações de compatibilidade do lock do Poetry. Para atualizar essas exportações, utilizei `poetry-plugin-export` 1.9.0, com os comandos `poetry export --only main --without-hashes -f requirements.txt -o requirements.txt`.

Validei a instalação com `poetry check --lock` e a construção da imagem. Executei as verificações de Django, migrações e testes utilizando o ambiente instalado pelo Poetry. Os bancos e volumes usados para validar esta correção são separados dos dados da aplicação publicada.

## Resultado da validação em 28/10/2026

Construí a imagem Python 3.13 com Poetry 2.5.1 e confirmei que `poetry check --lock` não apresenta inconsistências. As verificações do Django e de migrações terminaram sem problemas. Executei os 130 testes no PostgreSQL e os mesmos 130 testes no SQLite: todos passaram, sem testes ignorados no Linux. Confirmei também a resolução do serviço `db` e a conexão TCP na porta 5432. 

Mantive os arquivos Python da aplicação e da suíte de testes sem alterações nesta correção.

## Consulta pública de produtos — 29/10/2026

Apliquei a [correção do módulo 17](https://github.com/mtgbcma-dotcom/m17-token/commit/fa76987cbcc8ef4231c6119b59959024c803fce9) conforme a orientação do tutor. Liberei a listagem e os detalhes de produtos sem login, preservando a paginação de 5 registros e a categoria na representação. Mantive a escrita de produtos restrita à equipe e os pedidos autenticados por token.

Acrescentei três testes para a leitura anônima, a paginação pública e o bloqueio das operações de escrita para visitantes e usuários comuns. Atualizei as expectativas dos cenários anteriores que bloqueavam a consulta de produtos. Mantive os modelos, serializers, migrações, dependências, pyproject.toml e poetry.lock sem alterações nesta correção.

Validei o manifesto e o lock com Poetry 2.5.1, construí a imagem Python 3.13 e executei as verificações de Django e migrações sem problemas. Executei os 133 testes no PostgreSQL e os mesmos 133 no SQLite: todos passaram no Docker Linux. Conferi também requisições HTTP reais sem credenciais: listagem, segunda página e detalhe de produto retornaram HTTP 200; pedidos sem token retornaram HTTP 401; escrita de produtos e acesso a categorias sem login retornaram HTTP 403.

## Tempo da coleta de estáticos na hospedagem

Identifiquei no registro de erros do PythonAnywhere que `collectstatic --noinput` excedia o limite de 30 segundos durante a publicação. Ampliei essa etapa para 120 segundos e ajustei a espera do cliente para 290 segundos, preservando os demais limites e as verificações de segurança. O conjunto das etapas permanece limitado a 260 segundos, antes da resposta do cliente e do limite de cinco minutos do worker. Mantive as dependências e o lock do Poetry sem alterações.

Após esse ajuste, reconstruí a imagem pelo Poetry e repeti as verificações de Django, migrações, 133 testes no PostgreSQL e 133 no SQLite: todos passaram. As requisições HTTP anônimas de produtos retornaram 200 e os pedidos sem token continuaram retornando 401.
