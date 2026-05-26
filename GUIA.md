# Captador de CNPJs — Site da Equipe

Site privado, com **design moderno**, **login**, painel de
**administração** (usuários + chave de API) e **modo de teste** que
busca só 5 CNPJs para você validar tudo gastando centavos.

## Arquivos
- `app.py` — aplicação web
- `db.py` — banco de dados (usuários + chave)
- `requirements.txt` — dependências
- `render.yaml` — configuração de publicação

---

# PARTE 1 — A "API": como obter sua chave (passo a passo)

> **Esclarecimento importante:** você **não cria** uma API. A API é
> da Casa dos Dados e já existe. O que você precisa é da sua **chave
> de acesso** (api-key). Não é programação — é cadastro no site
> deles. O app já está pronto para receber essa chave.

1. Acesse **https://portal.casadosdados.com.br** e crie sua conta
   (ou faça login).
2. Adquira saldo. Duas opções:
   - **Crédito avulso:** ~**R$ 0,01 por empresa consultada** — ideal
     para começar e testar. Buscar 5 CNPJs custa ~R$ 0,05.
   - **Plano mensal:** pacotes de consultas que acumulam enquanto a
     assinatura estiver ativa.
3. No painel, procure a seção de **API / Chave de API**.
4. **Gere/copie a chave** (api-key). Guarde com cuidado — é como uma
   senha. Não compartilhe.
5. Pronto. Essa chave vai no app (Parte 3).

> Navegar no app não consome saldo; só a geração de arquivo consome.

---

# PARTE 2 — Publicar o site (grátis)

> Você cria 2 contas grátis (GitHub e Render). ~10 min, só cliques.
> Não consigo fazer isso por você: envolve suas credenciais.

### 2.1 GitHub
1. Conta em https://github.com
2. **New repository** → nome `captador-cnpj` → **Public** → criar
3. **uploading an existing file** → arraste os 4 arquivos → commit

### 2.2 Render
1. Conta em https://render.com (entre com o GitHub)
2. **New +** → **Blueprint** → escolha o repositório → **Apply**
3. Em **Environment**, defina `ADMIN_SENHA` com uma senha forte
4. Aguarde alguns minutos → link `https://captador-cnpj.onrender.com`

### Testar no seu PC antes (opcional)
    pip install flask requests
    python app.py
Abre em http://localhost:5000

---

# PARTE 3 — Primeiro uso e o teste dos 5 CNPJs

### 3.1 Entrar como admin
- Usuário **admin** / senha definida em `ADMIN_SENHA`
  (no PC local o padrão é `admin123`)
- Troque a senha do admin já: aba Administração → linha do admin →
  botão "Senha"

### 3.2 Colocar a chave de API
Aba **Administração** → campo **Nova chave de API** → cole a chave
da Parte 1 → **Salvar chave**. O indicador no topo fica verde.

### 3.3 Rodar o teste que você pediu (5 CNPJs)
Na aba **Captar**:
1. Ative **🧪 Modo teste rápido** (limita a 5 resultados)
2. **CNAE:** ex `6920601`
3. **Empresas novas:** `30` (recém-criadas)
4. **Estado (UF):** ex `SP`
5. **Município:** ex `SAO PAULO` (sem acento, maiúsculas)
6. **Gerar arquivo de CNPJs** → acompanhe o log → **⬇ Baixar**

Devem vir até 5 empresas batendo CNAE + estado + município +
recém-criadas. Custo: centavos.

> Vazio? Afrouxe um filtro (tire município ou aumente os dias).
> Filtros muito estreitos podem não ter 5 empresas novas.

### 3.4 Adicionar a equipe
Aba Administração → "Adicionar novo usuário". Membros usam o
captador mas **não veem** a chave de API.

---

## Avisos honestos

- **Não testei contra a API real** (não tenho chave). Todo o site —
  login, admin, segurança, geração dos filtros — foi testado e
  funciona. A conversa com a Casa dos Dados segue a documentação
  oficial; algum **nome de campo** pode precisar de ajuste fino na
  primeira execução real. O modo teste (5 CNPJs) existe para você
  descobrir isso gastando centavos. Se algo vier estranho, me mande
  o texto do log que eu corrijo.
- **Render grátis hiberna:** 1º acesso após ~15 min ocioso demora
  ~30-50s. Plano pago (~US$7/mês) remove isso sem mudar código.
- **Persistência:** `render.yaml` já pede disco para o banco. Se sua
  conta exigir upgrade, dá para usar Postgres grátis do Render —
  me avise que adapto o `db.py`.
- **Segurança:** senhas com hash PBKDF2; chave de API só o admin vê,
  mascarada. Use senhas fortes.

## Trocar a chave depois
Login admin → Administração → cole a nova chave → Salvar. Vale para
a equipe na hora, sem republicar.
