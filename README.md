# GP Agenda

MVP para a GP Estética Automotiva: clientes, catálogo de serviços, orçamento imprimível por atendimento, agenda sem horários sobrepostos e acompanhamento do status das ordens de serviço.

## Estado do projeto

- Interface React, backend Flask e banco SQLite implementados.
- Testes automatizados de autenticação, CSRF, cadastro, orçamento, agendamento, conflito de horários e mudança de status.
- CI configurada em `.github/workflows/ci.yml`; execução remota depende da publicação do repositório.
- Dados da conversa inicial com Ronaldo: 12/11/2026, presencial. Ainda faltam material de evidência e validação do MVP por Ronaldo.
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

## Executar testes

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
cd frontend
npm run build
```

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

O carro na interface é uma imagem editorial gerada para este protótipo. Não representa a garagem real nem um veículo de cliente.
