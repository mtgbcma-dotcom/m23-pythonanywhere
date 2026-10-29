# Bookstore - Projeto final com PythonAnywhere e entrega continua

Projeto final do Módulo 23 de Continuação Back-End Python da EBAC.

Preparei a API Bookstore para hospedagem gratuita no PythonAnywhere, seguindo o material de Projeto Final. A aplicação utiliza SQLite na hospedagem e PostgreSQL no Docker. A integração contínua testa os dois bancos antes de permitir a entrega automática da branch main.



## Aplicação publicada

Publiquei o Bookstore em **https://brunom89.pythonanywhere.com/hello/**. A página mostra a versão da aplicação; a API está disponível em https://brunom89.pythonanywhere.com/api/.

Entrego o [PR de implementação](https://github.com/mtgbcma-dotcom/m23-pythonanywhere/pull/1) e o [PR de comprovação da atualização automática](https://github.com/mtgbcma-dotcom/m23-pythonanywhere/pull/2), junto com o endereço publicado. Mantive o histórico das entregas já integradas e registrei as correções posteriores na branch `main`.

## Consulta pública de produtos

Apliquei a orientação do tutor e a correção do módulo 17: a listagem `GET /api/products/` e o detalhe `GET /api/products/{id}/` são públicos, sem necessidade de login ou token. Preservei a paginação de 5 registros, os links para as páginas seguintes e a categoria na representação dos produtos.

Mantive o cadastro, a alteração e a exclusão de produtos restritos à equipe por sessão ou Basic Authentication. Os pedidos continuam protegidos por TokenAuthentication e retornam HTTP 401 sem token. Mantive também a permissão de categorias e o Poetry, com o manifesto e o lock sem alterações nesta correção.

Acrescentei testes de consulta anônima da listagem e dos detalhes, paginação sem login e bloqueio de todas as operações de escrita de produtos para visitantes e usuários comuns. Registrei a validação em [docs/CONTINUIDADE.md](docs/CONTINUIDADE.md).

## Continuidade do projeto e do ambiente

Dei continuidade ao [módulo 22 — Integração contínua](https://github.com/mtgbcma-dotcom/m22-ci/pull/1). Mantive os modelos, serializers, migração inicial, paginação, autenticação e testes da API Bookstore.

Mantive **Poetry** como gerenciador do projeto, com `pyproject.toml` e `poetry.lock` versionados. Preservei a identificação `m57-bookstore` e as dependências da base corrigida do módulo 17. Acrescentei ao manifesto somente as dependências necessárias para esta etapa e atualizei o lock pelo Poetry.

Configurei o Dockerfile para instalar Poetry 2.5.1, conferir o lock e instalar as dependências com `poetry install --only main --no-root`. O pip instala apenas a ferramenta Poetry na imagem; as dependências da aplicação são instaladas pelo Poetry a partir do lock.

Os arquivos `requirements*.txt` são exportações de compatibilidade do mesmo lock, utilizadas quando uma plataforma exige esse formato. A fonte de dependências desta entrega é o manifesto e o lock do Poetry. Registrei a continuidade e a validação em [docs/CONTINUIDADE.md](docs/CONTINUIDADE.md).

Para conferir o manifesto no computador com Poetry 2.5.1 instalado:

```powershell
poetry check --lock
poetry install --no-root --no-interaction
```

Nos módulos com PostgreSQL, executei os testes nos serviços Docker descritos abaixo, onde o banco está configurado. No contêiner, utilizei `poetry run python manage.py test` no mesmo ambiente instalado pelo Poetry.

## Recursos

- API de categorias, produtos e pedidos com Django REST Framework.
- Paginação de 5 registros por página.
- Autenticação por token somente nos pedidos; gestão restrita a administradores.
- Página pública `/hello/` com a versão da aplicação e o commit publicado.
- WhiteNoise para servir os arquivos estáticos com DEBUG desativado.
- Configurações privadas em variáveis de ambiente e `.env`, ignorado pelo Git.
- Docker Compose com PostgreSQL, volume persistente e rede bridge personalizada.
- GitHub Actions para verificações, testes em PostgreSQL e SQLite e entrega automática.
- Webhook `/update_server/` autenticado por assinatura HMAC SHA-256.

## Executar localmente no Windows

Com o Docker Desktop aberto, use o PowerShell na pasta que contém `docker-compose.yml`.

Na primeira execução:

```powershell
Copy-Item .env.example .env
```

Abra `.env`, ajuste `POSTGRES_PASSWORD` para o banco local e salve. Não sobrescreva esse arquivo nas próximas execuções.

```powershell
docker compose up -d --build --wait
docker compose ps
docker compose exec web poetry run python manage.py createsuperuser
docker compose exec web poetry run python manage.py seed_demo
```

Os serviços `web` e `db` devem estar `healthy`. O comando `seed_demo` cria 12 categorias e 12 produtos, sem duplicar os mesmos dados quando executado novamente.

- Apresentação: http://127.0.0.1:8004/hello/
- Raiz da API: http://127.0.0.1:8004/api/
- Produtos: http://127.0.0.1:8004/api/products/
- Administração: http://127.0.0.1:8004/admin/

Consulte a listagem e os detalhes de produtos sem fazer login. Para acessar categorias ou cadastrar, alterar e excluir produtos, use **Log in** com o administrador criado. A listagem de produtos preserva `count`, `next`, `previous` e `results`. Pedidos exigem `Authorization: Token <token>` e retornam HTTP 401 sem token, mesmo com sessão de login. O webhook fica desativado no ambiente Docker local.

## Testar

```powershell
docker compose exec -T web poetry run python manage.py check
docker compose exec -T web poetry run python manage.py makemigrations --check --dry-run
docker compose exec -T web poetry run python manage.py test --verbosity 2
```

Para executar a mesma suíte com SQLite, utilizado na hospedagem gratuita:

```powershell
docker compose exec -T -e DATABASE_ENGINE=sqlite -e SQLITE_DB_PATH=/tmp/m23-tests.sqlite3 web poetry run python manage.py test --verbosity 2
```

Os 133 testes passaram em PostgreSQL e SQLite no ambiente Docker Linux. Eles utilizam bancos temporários e cobrem a API, permissões, autenticação, paginação, assinatura do webhook, atualização do repositório, preservação de dados, configuração da hospedagem e arquivos estáticos.

Para parar ou recriar a aplicação preservando os cadastros:

```powershell
docker compose down
docker compose up -d --wait
```

O comando `down` preserva os volumes. Não utilize `-v` quando quiser manter os dados.

## Integracao continua

O workflow `.github/workflows/ci.yml`, chamado **CI - Bookstore**, executa em pushes e pull requests. O job de testes constrói a imagem, aguarda os serviços, verifica o Django e as migrações e testa a aplicação com PostgreSQL e SQLite.

O job **Publicar no PythonAnywhere** depende do sucesso dos testes e executa somente em pushes na main, quando a variável de repositório `PYTHONANYWHERE_DEPLOY_ENABLED` está definida como `true`. Antes dessa configuração, o job de publicação fica **Skipped**, enquanto os testes continuam funcionando.

As credenciais temporárias do banco de CI são geradas no runner. O `.env` local não é enviado ao GitHub nem utilizado pelo Actions.

## Hospedagem gratuita no PythonAnywhere

### 1. Preparar o repositorio

Envie o projeto completo ao seu repositório público, incluindo `.github` e `deploy`, em uma branch como `feat-pythonanywhere`. Abra o PR e aguarde os testes passarem. Para disponibilizar o código na main e permitir os deploys, faça o merge após a revisão. O link desse PR continua disponível para a entrega da atividade.

### 2. Criar a conta e instalar a aplicacao

Crie uma conta **Beginner** no [PythonAnywhere](https://www.pythonanywhere.com/registration/register/beginner/). No painel, abra um console Bash.

O exemplo abaixo pressupõe um repositório chamado `m23-pythonanywhere`; ajuste a URL se utilizar outro nome:

```bash
cd ~
git clone https://github.com/mtgbcma-dotcom/m23-pythonanywhere.git
cd m23-pythonanywhere
python3.10 -m venv ~/venv-m23
source ~/venv-m23/bin/activate
python -m pip install poetry==2.5.1
poetry install --only main --no-root --no-interaction
poetry run python deploy/configure_pythonanywhere.py
poetry run python manage.py migrate
poetry run python manage.py createsuperuser
poetry run python manage.py seed_demo
poetry run python manage.py collectstatic --noinput
```

Use uma versão de Python compatível com Django 5.2 e disponível na sua conta, como Python 3.10 ou posterior. Escolha a mesma versão ao criar o web app.

O assistente `configure_pythonanywhere.py` gera chaves privadas, identifica o repositório e prepara SQLite, domínio e caminhos do Python e do WSGI. Ele preserva um `.env` já existente. Para um domínio diferente do padrão, utilize `--domain SEU_DOMINIO.pythonanywhere.com` com o endereço informado na aba Web, inclusive o endereço regional europeu, se aplicável.

Os dados ficam em `data/db.sqlite3`, fora dos arquivos versionados. A configuração privada fica em `.env`, e o exemplo de WSGI gerado fica em `.deploy/pythonanywhere_wsgi.py`. Nenhuma chave é exibida pelo assistente.

### 3. Configurar o web app

Na aba **Web**, selecione **Add a new web app**, **Manual configuration** e a mesma versão de Python do ambiente virtual.

Configure:

- **Source code / Working directory:** `/home/SEU_USUARIO/m23-pythonanywhere`.
- **Virtualenv:** `/home/SEU_USUARIO/venv-m23`.
- **WSGI configuration file:** abra o arquivo indicado na aba Web e substitua seu conteúdo pelo arquivo `.deploy/pythonanywhere_wsgi.py` gerado no projeto.

Para visualizar o exemplo de WSGI no console, sem mostrar as chaves:

```bash
cat .deploy/pythonanywhere_wsgi.py
```

Clique em **Reload** na aba Web e confira `https://SEU_USUARIO.pythonanywhere.com/hello/` e `/api/`. O WhiteNoise serve os arquivos estáticos coletados, incluindo o CSS da API navegável e do painel administrativo.

### 4. Configurar a entrega automatica

No GitHub, acesse **Settings > Secrets and variables > Actions** do repositório.

Cadastre os seguintes **Repository secrets**:

| Nome | Valor |
|---|---|
| `PYTHONANYWHERE_WEBHOOK_URL` | `https://SEU_DOMINIO.pythonanywhere.com/update_server/` |
| `DEPLOY_WEBHOOK_SECRET` | O valor gerado no `.env` da hospedagem para essa mesma variável |

Para copiar a chave no console privado do PythonAnywhere, com o ambiente virtual ativo:

```bash
python -c "from dotenv import dotenv_values; print(dotenv_values('.env')['DEPLOY_WEBHOOK_SECRET'])"
```

Copie diretamente para o campo de secret do GitHub. Não inclua a chave em prints, mensagens ou commits.

Em **Variables**, cadastre a variável de repositório:

```text
PYTHONANYWHERE_DEPLOY_ENABLED = true
```

O Actions enviará a notificação ao webhook depois que o job de testes passar. A chamada é feita pelo cliente `deploy/github_hook_client.py`, com assinatura do conteúdo e tempo de espera apropriado à atualização. Esse fluxo não exige criar um segundo webhook em Settings > Webhooks.

### 5. Comprovar a entrega continua

Altere `VERSION` em `bookstore/version.py`, por exemplo de `1.0.0` para `1.0.1`, em uma nova branch. Faça o commit, envie a branch, abra um PR e aguarde os testes. Após fazer o merge na main, acompanhe o job **Publicar no PythonAnywhere** e confira a nova versão na página `/hello/`.

O webhook verifica a assinatura, o repositório, a branch e o commit aprovado. Ele busca a main e atualiza o clone apenas por fast-forward. Se a main já tiver um commit mais novo, ignora a solicitação antiga para evitar publicar código ainda não testado. Depois instala as dependências, aplica as migrações, coleta os estáticos e toca o arquivo WSGI para solicitar a recarga da aplicação.

Após conferir o registro de erros da hospedagem, ajustei o limite da coleta de estáticos de 30 para 120 segundos e o tempo de espera do cliente do GitHub Actions para 290 segundos. Os limites das etapas somam 260 segundos, com margem para a resposta antes do [limite de cinco minutos dos workers do PythonAnywhere](https://help.pythonanywhere.com/pages/AsyncInWebApps/). Mantive os limites, a assinatura do webhook, o bloqueio de entregas concorrentes e a gravação do sucesso somente após concluir todas as etapas.

Alterações locais em arquivos versionados e histórico divergente interrompem a atualização, preservando o clone. Entregas repetidas do mesmo commit não repetem uma publicação já concluída. Os detalhes de falha ficam no log do servidor, e não na resposta pública do webhook.

## Arquivos principais

- `.github/workflows/ci.yml`: integração e entrega contínuas.
- `bookstore/views.py`: apresentação e webhook autenticado.
- `bookstore/deployment.py`: atualização do clone e recarga do WSGI.
- `bookstore/version.py`: versão exibida para comprovar a publicação.
- `deploy/configure_pythonanywhere.py`: configuração privada da hospedagem.
- `deploy/github_hook_client.py`: cliente utilizado pelo Actions para chamar o webhook.
- `requirements.txt`: dependências da hospedagem gratuita com SQLite.
- `requirements-postgresql.txt`: dependências adicionais do Docker e do PostgreSQL.

## Referencias

- [Hospedagem de Django no PythonAnywhere](https://help.pythonanywhere.com/pages/DeployExistingDjangoProject/)
- [Recarga da aplicação no PythonAnywhere](https://help.pythonanywhere.com/pages/ReloadWebApp/)
- [Validação de assinaturas de webhooks](https://docs.github.com/en/webhooks/using-webhooks/validating-webhook-deliveries)
- [WhiteNoise com Django](https://whitenoise.readthedocs.io/en/stable/django.html)

## Autor

Bruno Costa Macedo de Almeida


## Compatibilidade dos testes de configuração

Ajustei o teste do arquivo WSGI para comparar o valor do caminho `project_dir` no código Python gerado. Assim, a verificação funciona com as barras escapadas do Windows e com os caminhos do Linux. Os testes de bloqueio e atualização do deploy continuam exclusivos de Linux, que é o ambiente utilizado no Docker e na hospedagem PythonAnywhere.


## Exportação para a hospedagem

Mantive o atualizador da hospedagem compatível com `requirements.txt`, mas gerei esse arquivo a partir do mesmo `poetry.lock`, com as versões e os marcadores de plataforma resolvidos pelo Poetry. Assim, a instalação da hospedagem e a instalação por Poetry usam as mesmas dependências. Para reproduzir a exportação, utilizei o plugin oficial `poetry-plugin-export` 1.9.0 e `poetry export --only main --without-hashes -f requirements.txt -o requirements.txt`.
