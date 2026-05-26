# Captador de CNPJs — Site da Equipe

Site privado com **login**, **painel de administração** para gerenciar
usuários e **trocar a chave de API** sem mexer em código.

## Arquivos

- `app.py` — a aplicação web
- `db.py` — banco de dados (usuários + chave de API)
- `requirements.txt` — dependências
- `render.yaml` — configuração de publicação

Mantenha todos juntos na mesma pasta.

---

## Como funciona

- **Admin** (você): faz login, cadastra/remove pessoas da equipe e
  define/troca a chave de API da Casa dos Dados pela própria tela.
- **Membros** da equipe: fazem login e usam o captador. Eles **não
  veem nem mexem** na chave de API — só usam.
- A chave fica guardada **uma vez só**, de forma central. Quando ela
  vencer ou você quiser trocar, é um campo na aba Administração.

### Primeiro acesso
Usuário: **admin** — Senha: **admin123**

> **TROQUE essa senha imediatamente** no primeiro login: aba
> Administração → na linha do admin, botão "Senha".

---

## Testar no seu computador (opcional)

    pip install flask requests
    python app.py

Abre sozinho em http://localhost:5000

---

## Publicar online (grátis) — passo a passo

> Você precisa criar 2 contas grátis: GitHub e Render. ~10 minutos.
> Não consigo fazer isso por você (envolve suas credenciais), mas
> abaixo está cada clique.

### 1. Subir no GitHub
1. Conta em https://github.com
2. **New repository** → nome `captador-cnpj` → **Public** → criar
3. **uploading an existing file** → arraste os 4 arquivos → commit

### 2. Publicar no Render
1. Conta em https://render.com (entre com o GitHub)
2. **New +** → **Blueprint** → escolha o repositório → **Apply**
3. O Render lê o `render.yaml` sozinho, inclusive criando um disco
   persistente (assim os usuários e a chave **não se perdem**)
4. Em **Environment**, defina `ADMIN_SENHA` com uma senha forte
   (essa será a senha inicial do admin)
5. Aguarde alguns minutos → você recebe um link
   `https://captador-cnpj.onrender.com`

**Esse link é o site da sua equipe.**

---

## Avisos honestos

- **Disco persistente:** o `render.yaml` já pede 1 GB de disco para
  o banco. No plano gratuito do Render isso normalmente está incluso;
  se a sua conta pedir upgrade para usar disco, a alternativa grátis
  é usar o Postgres free do Render (posso adaptar o código se for o
  caso — me avise).
- **Plano grátis hiberna:** após ~15 min sem uso, o primeiro acesso
  demora ~30-50s para acordar. O plano pago (a partir de ~US$7/mês)
  remove isso — é o "pagar futuramente" que você mencionou, e dá
  para migrar sem trocar nada do código.
- **Não testei contra a API real da Casa dos Dados** (não tenho
  chave). Toda a lógica de login, admin e segurança foi testada e
  está funcionando. A parte que conversa com a Casa dos Dados segue
  a documentação oficial, mas pode precisar de um pequeno ajuste de
  nome de campo na primeira execução real — algo rápido.
- **Segurança:** senhas são guardadas com hash forte (PBKDF2), nunca
  em texto puro. A chave de API fica no banco; só o admin a vê (e
  mascarada). Ainda assim, por ser um site na internet, use senhas
  fortes e considere o plano pago se os dados forem sensíveis.

---

## Trocar a chave de API depois (o que você pediu)

1. Faça login como admin
2. Aba **⚙️ Administração**
3. Campo **Nova chave de API** → cole a nova → **Salvar chave**

Pronto. Toda a equipe passa a usar a chave nova na hora, sem
republicar nada.
