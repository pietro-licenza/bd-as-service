# 🔐 Guia de Autenticação GitHub

## Problema Atual
Você está tentando fazer push com credenciais da conta corporativa (`pietro-licenza-smartfit`) para um repositório da conta pessoal (`pietro-licenza`).

## ✅ Solução: Token Pessoal

### Passo 1: Criar Token Pessoal
1. Acesse: https://github.com/settings/tokens
2. Clique em "Generate new token (classic)"
3. Nome: `bd-as-service-deploy`
4. Permissões: Marque `repo` (acesso completo aos repositórios)
5. Clique em "Generate token"
6. **COPIE O TOKEN** (não vai aparecer novamente!)

### Passo 2: Configurar Credenciais
Quando fizer push, use:
- **Username:** `pietro-licenza`
- **Password:** `[COLE_SEU_TOKEN_AQUI]`

### Passo 3: Fazer Push
```bash
git push -u origin master
```

### Alternativa: Usar GitHub CLI
```bash
# Instalar GitHub CLI
winget install --id GitHub.cli

# Fazer login na conta pessoal
gh auth login

# Depois fazer push normalmente
git push -u origin master
```

## 🔄 Se Ainda Der Erro

### Limpar Credenciais Salvas
```bash
# Windows Credential Manager
# Procure por "git:https://github.com" e delete
```

### Forçar Nova Autenticação
```bash
git push -u origin master
# Quando pedir username: pietro-licenza
# Quando pedir password: [SEU_TOKEN]
```

## ✅ Verificação
Após sucesso, você verá:
```
Enumerating objects: X, done.
Counting objects: 100% (X/X), done.
...
To https://github.com/pietro-licenza/bd-as-service.git
 * [new branch]      master -> master
```