# MIGRAÇÃO PARA POSTGRES GRÁTIS — Passo a passo

## O que esta atualização corrige

1. **502 ao baixar arquivos** — o servidor não baixa mais o arquivo
   pela memória dele; ele te redireciona direto para o link da Casa
   dos Dados. Sem passar pelo Render, sem 502.

2. **Travamento ao gerar** — o "Gerar arquivo" agora só dispara o
   pedido (resposta em segundos) e te manda para "Minhas
   solicitações". O worker do Render fica livre.

3. **Chave e usuários sumindo** — com Postgres, os dados ficam
   PERMANENTES. Não somem mais ao hibernar/reiniciar.

---

## Passos

### 1) Subir os arquivos novos no GitHub
Suba `app.py`, `db.py` e `requirements.txt` no repositório
`Prospecta-` (mesma forma de sempre — substitui os existentes).

O `render.yaml` não mudou, não precisa subir.

### 2) Criar o banco Postgres grátis no Render

1. No painel do Render, clique em **New +** → **Postgres**
2. **Name**: `captador-db` (ou outro nome)
3. **Database**: deixe o padrão
4. **User**: deixe o padrão
5. **Region**: a mesma do seu app (provavelmente Oregon)
6. **Plan**: **Free**
7. Clique em **Create Database**
8. Aguarde alguns minutos até o status ficar **Available**

### 3) Conectar o banco ao seu app

1. Na página do banco criado, role até a seção **"Connections"**
2. Copie o valor de **"Internal Database URL"**
   (algo como `postgresql://user:senha@host/db`)
3. Vá no seu serviço `captador-cnpj` → **Environment** (no menu lateral)
4. Clique em **Add Environment Variable**
5. **Key**: `DATABASE_URL`
6. **Value**: cole o valor que você copiou
7. Clique em **Save Changes**

O Render vai reimplantar sozinho. Quando ficar **Live** de novo, o
app já estará usando o Postgres.

### 4) Primeiro acesso após a migração

Os usuários e a chave que você havia configurado no SQLite **NÃO**
migram automaticamente (são bancos diferentes). Você precisa
reconfigurar UMA VEZ:

1. Acesse o site, faça login como `admin` com a senha que você
   definiu em `ADMIN_SENHA`
2. Vá em **Administração** → cole a chave de API → **Salvar chave**
3. (Opcional) Cadastre os usuários da equipe

**A partir daqui, esses dados ficam permanentes.** O Render pode
reiniciar, hibernar, atualizar — tudo continua lá.

---

## Como o app funciona agora

- **Gerar arquivo de CNPJs**: clica → em segundos aparece "ID:
  abc123 — vá em Minhas solicitações". Pronto.
- **Minhas solicitações**: clica "Atualizar lista" de vez em
  quando. Quando o status virar **"processado"**, clica em
  **Baixar** — o navegador baixa direto da Casa dos Dados
  (sem 502, sem passar pelo Render).
- **Modo teste**: continua mostrando a prévia de 5 na tela.

---

## Aviso honesto

- O plano Postgres grátis do Render expira em **90 dias** e exige
  você criar outro depois (gratuito também). Antes disso o Render
  avisa por e-mail.
- O Postgres grátis suspende após **30 dias sem uso**, mas como
  você vai usar o app regularmente, isso não deve ser problema.
- Se preferir um banco permanente sem essas regras, o plano pago
  começa em ~US$7/mês.
