# Captador CNPJ — Prospecta+

Sistema de captação e gestão de CNPJs via API Casa dos Dados.

## Funcionalidades
- Captação de CNPJs com filtros (CNAE, UF, município, situação)
- **Leads Salvos** — base persistente, consulte e exporte sem gastar créditos
- Importação de CSV / salvamento automático da prévia
- Busca avançada com paginação
- Exportação CSV dos leads filtrados
- Gerenciamento de usuários (admin/operador)
- Logs e diagnóstico

## Deploy no Render
1. Suba este repositório no GitHub
2. No Render: New → Blueprint → conecte o repo
3. Ele detecta o `render.yaml` e cria o serviço + banco Postgres automaticamente
4. Defina a senha do admin quando solicitado
5. Acesse a URL gerada e configure a API KEY da Casa dos Dados

## Dados persistentes
Com Postgres (configurado no render.yaml), seus dados **nunca se perdem** — mesmo quando o Render hiberna.
"# ProspectaMais"  
"# ProspectaMais"  
