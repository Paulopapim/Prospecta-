# DEPLOY — Passo a passo (plano grátis Render)

> **Importante, leia antes:** você escolheu o plano grátis sem
> persistência. Consequência real: quando o Render hibernar e
> reiniciar (acontece sozinho após ~15 min ocioso), **os usuários
> cadastrados e a chave de API somem**. O site continua acessível
> (o admin é recriado sozinho), mas você terá que **recolocar a
> chave de API e recadastrar a equipe** após cada reinício.
> Quando cansar disso, me peça a versão com Postgres grátis — o
> código já está preparado para migrar sem reescrever tudo.

---

## O que eu NÃO consigo fazer por você

Criar as contas e autorizar acessos. Isso usa suas credenciais e,
por segurança, é você quem faz. Abaixo está cada clique.

## Arquivos que vão para o deploy
Da pasta `C:\Prospecta+\prospecta+`, vão estes 4:
- `app.py`
- `db.py`
- `requirements.txt`
- `render.yaml`

(O `GUIA.md` e o arquivo `captador.db`, se existir, NÃO precisam ir.
Se houver uma pasta `__pycache__`, também não precisa.)

---

## PASSO 1 — Conta no GitHub e subir o código

1. Crie conta em https://github.com (se ainda não tem)
2. Clique no **+** (canto superior direito) → **New repository**
3. Nome: `captador-cnpj` · deixe **Public** · **Create repository**
4. Na página seguinte, clique no link
   **"uploading an existing file"**
5. Abra a pasta `C:\Prospecta+\prospecta+` no Windows, selecione
   os 4 arquivos (`app.py`, `db.py`, `requirements.txt`,
   `render.yaml`) e arraste para a área do navegador
6. Clique no botão verde **Commit changes**

## PASSO 2 — Conta no Render e publicar

1. Crie conta em https://render.com — clique em
   **"Get Started"** e escolha **entrar com o GitHub**
   (mais simples; autoriza os dois de uma vez)
2. No painel do Render, clique em **New +** (azul, topo) →
   **Blueprint**
3. Render lista seus repositórios do GitHub. Escolha
   **captador-cnpj** → **Connect**
4. Ele detecta o `render.yaml` automaticamente e mostra o serviço
   `captador-cnpj`. Vai aparecer um campo pedindo o valor de
   **ADMIN_SENHA** (a variável marcada como "sync: false")
5. Digite ali uma **senha forte** — será a senha do usuário
   `admin`. Anote essa senha.
6. Clique em **Apply** (ou **Create Resources**)
7. Aguarde o build. A primeira vez leva alguns minutos. Quando
   o status ficar **"Live"**, no topo da página do serviço estará
   a URL pública: algo como
   `https://captador-cnpj.onrender.com`

**Essa URL é o seu site.** Abra no navegador.

---

## PASSO 3 — Primeiro acesso

1. Acesse a URL → tela de login
2. Usuário: **admin** · Senha: a que você definiu em ADMIN_SENHA
3. Vá na aba **Administração** → cole sua **chave de API** da
   Casa dos Dados → **Salvar chave**
4. (Opcional) Ainda em Administração, cadastre os usuários da
   equipe
5. Pronto para captar.

> Lembre-se: após um reinício do Render (hibernação), repita os
> passos 3.3 e 3.4 (rechave + recadastro). É o efeito da opção
> grátis sem persistência que você escolheu.

---

## Dicas de uso já sabendo do comportamento

- **Geração demora:** a Casa dos Dados leva minutos para gerar o
  arquivo. Não fique esperando na tela. Mande gerar, e depois vá
  na aba **"Minhas solicitações"** — lista o que você pediu, com
  status, e deixa baixar quando estiver "processado". Consultar
  ali **não gasta crédito**.
- **Primeiro acesso após ocioso:** ~30-50s para o site "acordar".
  Normal no plano grátis.
- **Recuperar o teste anterior:** se você já tinha mandado gerar
  algo antes, ele pode estar na aba "Minhas solicitações" —
  baixe de lá sem gastar novo crédito.

---

## Quando quiser eliminar o problema de "dados somem"

Me peça a **versão Postgres grátis**. O Render oferece um banco
Postgres gratuito; com ele os usuários e a chave ficam
permanentes. Exige 2 passos a mais no setup (uma vez só) e eu
adapto o `db.py` e o `requirements.txt` — tudo testado antes de
entregar, como temos feito.
