# GP Agenda

MVP para a GP Estética Automotiva: clientes, catálogo de serviços, orçamento imprimível por atendimento, agenda sem horários sobrepostos e acompanhamento do status das ordens de serviço.

[Abrir o piloto na Vercel](https://gp-agenda-piloto.vercel.app/studio)

## Estado do projeto

- Interface React e backend Flask. SQLite no ambiente local e PostgreSQL do Neon no piloto publicado na Vercel.
- Testes automatizados de autenticação, CSRF, cadastro, orçamento, agendamento, conflito de horários e mudança de status.
- CI configurada em `.github/workflows/ci.yml`. O [job remoto](https://github.com/Beckerr11/gp-agenda/actions/runs/44120442351) foi barrado antes da execução por uma restrição de faturamento da conta. Os comandos de verificação podem ser executados localmente.
- Conversa inicial em 12/11/2026 e demonstração no celular com Ronaldo em 17/11/2026. O relatório acadêmico mantém os registros do teste e as fotos autorizadas.
- Roteiros para registrar essa etapa estão em `docs/registro_de_campo.md` e `docs/validacao_com_ronaldo.md`.
- O banco local contém somente registros fictícios usados no teste visual e **não** está incluído no pacote.

## Iniciar no Windows

Requisitos: Python 3.12 e Node.js 22 ou superior.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
cd frontend
npm ci
npm run build
cd ..
$env:GP_SECRET_KEY = (python -c "import secrets; print(secrets.token_hex(32))")
$env:GP_ADMIN_USER = 'ronaldo'
$env:GP_ADMIN_PASSWORD = '<defina uma senha única com ao menos 12 caracteres>'
.\.venv\Scripts\python.exe -m flask --app app create-admin
.\.venv\Scripts\python.exe -m waitress --listen=127.0.0.1:5059 app:app
```

Abra `http://127.0.0.1:5059/studio`. A interface antiga de verificação permanece em `/login`.

Para o uso real, guarde `GP_SECRET_KEY` de forma persistente e não use a senha de demonstração. O arquivo de dados fica em `instance/gp_estetica.sqlite3`; faça backup desse arquivo antes de atualizar ou mover a aplicação. Para exposição pública, configure HTTPS, `GP_HTTPS=1`, um domínio, monitoramento e armazenamento persistente antes de incluir dados reais de clientes.

## Publicar o piloto na Vercel com Neon

O Flask roda na Vercel e o PostgreSQL do Neon preserva os dados entre execuções. O modo local continua usando SQLite. Inicialize um banco vazio dedicado ao piloto. Em um ambiente local com as dependências Python instaladas e `DATABASE_URL`, `GP_ADMIN_USER` e `GP_ADMIN_PASSWORD` configuradas, execute:

```powershell
python -m flask --app app init-db
python -m flask --app app create-admin
npm ci --prefix frontend
npm run build --prefix frontend
vercel link
```

Configure `DATABASE_URL`, `GP_HTTPS=1` e uma `GP_SECRET_KEY` aleatória de pelo menos 32 caracteres nas variáveis de produção do projeto Vercel. Depois de rodar `vercel deploy --prod`, abra `/studio`. Confira `/health`, login, cadastro fictício, rejeição de um horário conflitante e abertura do orçamento. Use registros fictícios nas sessões de validação.

## Executar testes

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
cd frontend
npm run build
```

## Verificar o piloto

Consulte [o endpoint de saúde](https://gp-agenda-piloto.vercel.app/health) para conferir a comunicação entre Flask e Postgres. Para verificar o fluxo, entre com o usuário de teste e cadastre um cliente fictício e um serviço. Reserve um horário e confirme que uma segunda reserva sobreposta é rejeitada. Abra o orçamento, mude o status e recarregue a agenda para conferir a persistência. O PostgreSQL usa um bloqueio de transação para impedir que duas gravações concorrentes aceitem o mesmo intervalo.

## Estrutura

```text
app.py                 Flask, regras de negócio, API e banco
frontend/src/          React e estilos
frontend/src/components/CountUp.jsx  componente React Bits
static/react/          build pronto para servir pelo Flask
tests/                 testes automatizados
docs/                  artefatos das quatro experiências
.github/workflows/     pipeline CI
```

## Fontes e componentes

- [Taste Skill](https://www.tasteskill.dev/) orientou a direção visual e a revisão de qualidade.
- [React Bits Count Up](https://reactbits.dev/) anima os indicadores. A licença original está em `frontend/REACT_BITS_LICENSE.md`.
- [Transitions.dev Toast open/close](https://transitions.dev/detail.html?t=toast-open-close) fornece a transição de confirmação em `frontend/src/app.css`.
- [Flask](https://flask.palletsprojects.com/en/stable/) e [OWASP Password Storage](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html) orientaram a implementação de sessão, cabeçalhos e hash de senha.

A tela de login exibe a logo oficial fornecida pelo parceiro. O carro no painel é uma imagem editorial criada para o protótipo.
