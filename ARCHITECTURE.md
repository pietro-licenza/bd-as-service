
# Arquitetura e Funcionamento do Projeto (FastAPI)

## O que é FastAPI?

FastAPI é um framework moderno, rápido (high performance) para construção de APIs com Python 3.7+ baseado em padrões do tipo Python type hints. Ele é muito utilizado no mercado por sua simplicidade, performance e recursos nativos como validação automática de dados, documentação interativa e suporte a autenticação JWT.

### Como funciona o FastAPI?

- **Roteamento**: Você define endpoints (rotas) usando decoradores (@app.get, @app.post, etc). Cada rota é uma função Python que recebe requisições HTTP e retorna respostas (JSON, HTML, arquivos, etc).
- **Validação de dados**: Utiliza Pydantic para validar e serializar dados de entrada e saída automaticamente.
- **Documentação automática**: Gera docs interativas (Swagger/OpenAPI) em `/docs` e `/redoc`.
- **Injeção de dependências**: Permite declarar dependências (ex: autenticação, banco) de forma simples e reutilizável.
- **Performance**: Baseado em Starlette e Uvicorn, é um dos frameworks Python mais rápidos.
- **Assíncrono**: Suporte nativo a async/await para alta performance em I/O.

### Como o FastAPI está aplicado neste projeto?

#### 1. main.py (Ponto de entrada)
O arquivo `main.py` inicializa a aplicação FastAPI, configura CORS, inclui todos os routers (rotas) dos serviços e monta arquivos estáticos e de exportação. Exemplo:

```python
from fastapi import FastAPI
from app.services.sams_club.api.routes import router as sams_club_router

app = FastAPI()
app.include_router(sams_club_router)
```

#### 2. Routers e Modularização
Cada microserviço (ex: sams_club, leroy_merlin, sodimac) tem seu próprio arquivo/pasta de rotas (routes.py), schemas (modelos de dados), e integrações (ex: client.py para APIs externas). Isso facilita manutenção, testes e escalabilidade.

#### 3. Schemas (Pydantic)
Todos os dados recebidos/enviados pela API são validados por modelos Pydantic. Isso garante segurança e padronização dos dados.

#### 4. Configuração Centralizada
O arquivo `app/core/config.py` centraliza variáveis de ambiente, diretórios, chaves e configurações globais.

#### 5. Templates e Frontend
Templates HTML (Jinja2) ficam em `templates/` e arquivos estáticos (JS, CSS) em `static/`. O FastAPI serve essas páginas e arquivos, permitindo integração entre backend e frontend.

#### 6. Shared
Funções/utilitários usados por vários serviços ficam em `app/shared/` (ex: geração de Excel, clientes de IA).

### Hierarquia de Pastas Explicada

- **app/**: Código principal do backend.
  - **core/**: Configurações globais, autenticação, utilitários centrais.
  - **api/**: Rotas principais, autenticação, web (HTML), health check.
  - **services/**: Cada integração/microserviço tem sua pasta (sams_club, leroy_merlin, sodimac), com subpastas para API, schemas, integrações externas, etc.
  - **models/**: Schemas e modelos de dados globais.
  - **shared/**: Utilitários e clientes compartilhados.
- **config/**: Arquivos de configuração YAML.
- **static/**: Frontend (JS, CSS, imagens).
- **templates/**: Templates HTML (Jinja2).
- **exports/**: Arquivos gerados para download (Excel, etc).

### Fluxo de uma Requisição FastAPI
1. Usuário faz requisição (ex: POST /api/sams-club/process-batch/)
2. FastAPI roteia para a função Python correta (definida em routes.py)
3. Dados são validados automaticamente por Pydantic
4. Lógica de negócio é executada (ex: processamento de imagens, chamada à IA)
5. Resposta é serializada e enviada ao frontend

### Dicas para quem está começando com FastAPI
- Use e abuse dos modelos Pydantic para garantir dados corretos.
- Explore a documentação automática em `/docs` (Swagger UI) e `/redoc`.
- Modularize: cada domínio/serviço em sua pasta, com rotas, schemas e integrações separados.
- Centralize configs sensíveis em `.env` e `config.py`.
- Use async/await para endpoints que fazem I/O intenso.
- Consulte sempre a documentação oficial: https://fastapi.tiangolo.com/pt/

---

# Estrutura Profissional - BD | AS Platform

## 📋 Visão Geral

Esta aplicação foi reestruturada de uma arquitetura monolítica para uma arquitetura de microserviços profissional, preparada para escalabilidade e manutenção a longo prazo.

## 🏗️ Arquitetura

### Backend (FastAPI)

```
app/
├── core/
│   ├── __init__.py
│   └── config.py                    # Configurações centralizadas (Settings)
├── api/
│   ├── __init__.py
│   └── routes/
│       ├── __init__.py              # Health check, API root
│       └── web.py                   # Rotas para servir páginas HTML (Jinja2)
├── services/
│   └── sams_club/                   # Microserviço Sam's Club
│       ├── __init__.py
│       ├── schemas.py               # Modelos Pydantic
│       ├── api/
│       │   ├── __init__.py
│       │   └── routes.py            # API endpoints (/api/sams-club/)
│       ├── image_parser/
│       │   ├── __init__.py
│       │   └── gemini_client.py     # Integração com Gemini AI
│       └── cloud/
│           ├── __init__.py
│           └── storage_client.py    # Google Cloud Storage
└── shared/                          # Código compartilhado entre serviços
    └── __init__.py
```

### Frontend (SPA - Single Page Application)

```
static/
├── css/
│   └── main.css                     # Estilos globais
└── js/
    ├── router.js                    # Sistema de roteamento SPA
    ├── app.js                       # Inicialização e state management
    └── pages/
        └── samsClub.js              # Lógica específica Sam's Club

templates/
├── base.html                        # Template base Jinja2
├── home.html                        # Página home
└── services/
    ├── sams_club.html               # Página Sam's Club
    └── outras.html                  # Outras integrações
```

## 🔄 Fluxo de Funcionamento

### 1. Servidor Inicia (main.py)
- FastAPI app criada
- CORS configurado
- Routers incluídos:
  - `/api/` - Health check e info
  - `/api/sams-club/` - Endpoints Sam's Club
  - `/`, `/integracoes/sams`, `/integracoes/outras` - Páginas HTML
- Arquivos estáticos montados em `/static/`
- Exports montados em `/exports/`

### 2. Usuário Acessa Homepage (/)
- FastAPI serve `templates/home.html` via Jinja2
- Template carrega:
  - `static/css/main.css` - Estilos
  - `static/js/router.js` - Router SPA
  - `static/js/pages/samsClub.js` - Lógica Sam's Club
  - `static/js/app.js` - Inicialização

### 3. Navegação SPA
- JavaScript router detecta hash changes (#/)
- Renderiza conteúdo dinamicamente no `#app-content`
- Atualiza título da página
- Chama callbacks `onMount()` se necessário

### 4. Processamento de Imagens
- Usuário adiciona produtos e imagens
- JavaScript renomeia arquivos: `product1_img1.jpg`, `product2_img1.jpg`
- POST para `/api/sams-club/process-batch/`
- Backend:
  - Agrupa imagens por produto (regex pattern)
  - Envia para Gemini AI via `gemini_client.py`
  - Gera Excel via `generate_excel_report()`
  - Retorna JSON com resultados

### 5. Resultado
- Frontend recebe JSON
- Exibe resultados em cards
- Mostra link para download do Excel

## 📊 Endpoints

### Web Routes (HTML)
- `GET /` - Home page
- `GET /integracoes/sams` - Sam's Club page
- `GET /integracoes/outras` - Outras integrações page

### API Routes
- `GET /api/health` - Health check
- `GET /api/` - API info

### Sam's Club Routes
- `POST /api/sams-club/process-batch/` - Processar lote de imagens

## 🎨 Design System

### Cores (CSS Variables)
- **Primary**: Gradiente roxo (#667eea → #764ba2)
- **Secondary**: Gradiente rosa (#f093fb → #f5576c)
- **Success**: Gradiente azul (#4facfe → #00f2fe)

### Tipografia
- Fonte: Inter (Google Fonts)
- Pesos: 300, 400, 500, 600, 700

### Componentes
- **Sidebar**: Navegação lateral fixa, 280px width
- **Cards**: Border-radius 16px, sombra suave
- **Botões**: Gradientes, animações hover
- **Loading**: Spinner animado
- **Results**: Cards expansíveis com JSON formatado

## 🔧 Configuração

### Variáveis de Ambiente (.env)
```env
GOOGLE_GENAI_API_KEY=your_key_here
GCS_BUCKET_NAME=your_bucket
GCS_CREDENTIALS_PATH=./bd_image_parser_service_account.json
```

### Arquivo de Configuração (config/config.yaml)
```yaml
gemini:
  model: gemini-2.0-flash-exp
  temperature: 0.7
  max_tokens: 2048
```

## 🚀 Como Executar

1. **Instalar dependências**:
```bash
pip install -r requirements.txt
```

2. **Configurar variáveis de ambiente**:
```bash
# Criar arquivo .env na raiz do projeto
```

3. **Iniciar servidor**:
```bash
uvicorn main:app --reload
```

4. **Acessar aplicação**:
```
http://localhost:8000
```

## 📦 Adicionando Novos Microserviços

Para adicionar uma nova integração (ex: "Walmart"):

1. **Criar estrutura**:
```bash
mkdir -p app/services/walmart/{api,cloud,parsers}
```

2. **Criar schemas**:
```python
# app/services/walmart/schemas.py
from pydantic import BaseModel

class WalmartProduct(BaseModel):
    name: str
    price: float
```

3. **Criar routes**:
```python
# app/services/walmart/api/routes.py
from fastapi import APIRouter

router = APIRouter(prefix="/api/walmart", tags=["Walmart"])

@router.post("/process/")
async def process_walmart_data():
    pass
```

4. **Incluir no main.py**:
```python
from app.services.walmart.api.routes import router as walmart_router
app.include_router(walmart_router)
```

5. **Criar página frontend**:
```html
<!-- templates/services/walmart.html -->
{% extends "base.html" %}
```

6. **Adicionar rota SPA**:
```javascript
// static/js/app.js
router.addRoute('/integracoes/walmart', {
    title: 'Integrações - Walmart',
    render: WalmartTemplate,
    onMount: initWalmartPage
});
```

## 🎯 Benefícios desta Arquitetura

1. **Separação de Responsabilidades**
   - Cada serviço é independente
   - Fácil manutenção e debug

2. **Escalabilidade**
   - Adicionar novos serviços sem modificar existentes
   - Code reuse via `app/shared/`

3. **Organização Profissional**
   - Estrutura clara e documentada
   - Padrões consistentes

4. **Performance**
   - SPA: Navegação instantânea sem reloads
   - Assets otimizados (CSS/JS separados)

5. **Manutenibilidade**
   - Código modular
   - Templates reutilizáveis
   - Configuração centralizada

## 📝 Notas Importantes

- **Roteamento**: Híbrido (FastAPI para páginas iniciais + SPA para navegação)
- **Estado**: Gerenciado no cliente via `AppState` global
- **API**: RESTful, JSON responses
- **Autenticação**: A implementar (futuro)
- **Testes**: A implementar (futuro)

## 🔒 Segurança

- CORS configurado via `app/core/config.py`
- Credenciais via variáveis de ambiente
- Validação com Pydantic schemas
- (Future) Autenticação JWT
- (Future) Rate limiting

## 📚 Próximos Passos

1. ✅ Estrutura de microserviços implementada
2. ✅ Frontend modular criado
3. ✅ Templates Jinja2 configurados
4. 🔄 Testes da aplicação
5. ⏳ Adicionar autenticação
6. ⏳ Implementar logging centralizado
7. ⏳ Docker containerization
8. ⏳ CI/CD pipeline

---

**Desenvolvido com ❤️ para BD | AS Platform**
