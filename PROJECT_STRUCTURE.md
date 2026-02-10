# 🏗️ BD | AS Platform - Estrutura do Projeto

## 📋 Visão Geral

Este projeto evoluiu de uma **aplicação monolítica** para uma **arquitetura de microserviços profissional**, preparada para crescimento e manutenção em longo prazo.

### O que é o BD | AS Platform?

Uma **plataforma de integração e automação** que centraliza múltiplos serviços de processamento de dados. Atualmente, o primeiro microserviço implementado é o **Sam's Club Image Parser**, que utiliza IA (Google Gemini) para extrair informações de produtos a partir de imagens.

### Mudança Arquitetural

**Antes (Monolito)**:
- Tudo em um único módulo `app/`
- Frontend e backend misturados
- Difícil adicionar novos serviços
- 1200+ linhas de HTML/CSS/JS em um único arquivo

**Depois (Microserviços)**:
- Cada integração é um serviço isolado
- Frontend modular (SPA)
- Backend organizado por contexto
- Assets separados (CSS, JS)
- Configuração centralizada

---

## 🗂️ Estrutura Completa do Projeto

```
bd_as_image_parser/
│
├── app/                                    # 📦 Pacote principal da aplicação
│   ├── __init__.py
│   │
│   ├── core/                              # ⚙️ NÚCLEO - Configurações centralizadas
│   │   ├── __init__.py
│   │   └── config.py                      # Settings (Pydantic BaseSettings)
│   │
│   ├── api/                               # 🌐 API LAYER - Rotas principais
│   │   ├── __init__.py                    # Módulo vazio (removido app antigo)
│   │   └── routes/                        # Rotas organizadas
│   │       ├── __init__.py                # Health check, API info
│   │       └── web.py                     # Serviço de páginas HTML (Jinja2)
│   │
│   ├── services/                          # 🔧 MICROSERVIÇOS
│   │   └── sams_club/                     # Microserviço Sam's Club
│   │       ├── __init__.py
│   │       ├── schemas.py                 # Modelos Pydantic (BatchResponse, etc)
│   │       │
│   │       ├── api/                       # API específica do Sam's Club
│   │       │   ├── __init__.py
│   │       │   └── routes.py              # POST /api/sams-club/process-batch/
│   │       │
│   │       ├── image_parser/              # Processamento de imagens com IA
│   │       │   ├── __init__.py
│   │       │   └── gemini_client.py       # Cliente Google Gemini
│   │       │
│   │       └── cloud/                     # Integração Cloud
│   │           ├── __init__.py
│   │           └── storage_client.py      # Google Cloud Storage
│   │
│   └── shared/                            # 📚 Código compartilhado entre serviços
│       └── __init__.py                    # Utils, helpers, exceptions comuns
│
├── static/                                # 🎨 FRONTEND - Arquivos estáticos
│   ├── css/
│   │   └── main.css                       # Estilos globais (CSS Variables)
│   │
│   └── js/
│       ├── router.js                      # Sistema de roteamento SPA
│       ├── app.js                         # Inicialização e state management
│       └── pages/
│           └── samsClub.js                # Lógica específica Sam's Club
│
├── templates/                             # 📄 TEMPLATES - Jinja2 HTML
│   ├── base.html                          # Template base (sidebar, topbar)
│   ├── home.html                          # Página inicial
│   └── services/                          # Templates de serviços
│       ├── sams_club.html                 # Página Sam's Club
│       └── outras.html                    # Outras integrações (placeholder)
│
├── config/                                # ⚙️ CONFIGURAÇÕES (legado)
│   └── config.yaml                        # Chaves API (substituído por settings)
│
├── exports/                               # 📊 EXPORTS - Arquivos gerados
│   └── *.xlsx                             # Relatórios Excel (gerados dinamicamente)
│
├── backup/                                # 💾 BACKUPS
│   ├── api_init_backup.py                # Versão anterior do app
│   ├── validation_init_backup.py
│   └── RESTORE_INSTRUCTIONS.md
│
├── tests/                                 # 🧪 TESTES
│   └── test_app.py                        # Testes unitários
│
├── frontend/                              # 📁 FRONTEND ANTIGO (deprecated)
│   └── index.html                         # SPA monolítico (1200+ linhas)
│
├── main.py                                # 🚀 ENTRY POINT
├── requirements.txt                       # 📦 Dependências Python
├── PROJECT_STRUCTURE.md                   # 📖 Este arquivo
├── ARCHITECTURE.md                        # 🏛️ Documentação da arquitetura
└── bd_image_parser_service_account.json  # 🔑 Credenciais GCP
```

---

## 🎯 Conceitos Fundamentais

### 1. **Pydantic Settings (app/core/config.py)**

**O que é**: Sistema de configuração centralizada usando `pydantic-settings`.

**Por que usar**:
- ✅ Validação automática de tipos
- ✅ Variáveis de ambiente (.env)
- ✅ Valores padrão
- ✅ Autocomplete no IDE

**Exemplo**:
```python
from app.core.config import settings

# Acesso centralizado
api_key = settings.GEMINI_API_KEY
bucket = settings.GCP_STORAGE_BUCKET
```

**Variáveis configuradas**:
- `APP_NAME`, `APP_VERSION`
- `BASE_DIR`, `STATIC_DIR`, `TEMPLATES_DIR`, `EXPORTS_DIR`
- `CORS_ORIGINS`, `CORS_ALLOW_CREDENTIALS`
- `GEMINI_API_KEY`, `GEMINI_MODEL_TEXT`, `GEMINI_MODEL_MULTIMODAL`
- `GCP_PROJECT_ID`, `GCP_STORAGE_BUCKET`, `GCP_SERVICE_ACCOUNT_KEY_PATH`

---

### 2. **Microserviços (app/services/)**

**O que são**: Módulos independentes que implementam funcionalidades específicas.

**Estrutura de um microserviço**:
```
sams_club/
├── schemas.py           # Modelos de dados (Pydantic)
├── api/routes.py        # Endpoints HTTP
├── image_parser/        # Lógica de negócio (Gemini)
└── cloud/              # Integrações externas (GCS)
```

**Benefícios**:
- ✅ Isolamento de código
- ✅ Escalabilidade independente
- ✅ Fácil manutenção
- ✅ Equipes podem trabalhar em paralelo

**Como adicionar novo serviço (ex: Walmart)**:
```bash
# 1. Criar estrutura
mkdir -p app/services/walmart/{api,processors}

# 2. Criar schemas
# app/services/walmart/schemas.py

# 3. Criar rotas
# app/services/walmart/api/routes.py

# 4. Registrar no main.py
from app.services.walmart.api.routes import router as walmart_router
app.include_router(walmart_router)
```

---

### 3. **SPA - Single Page Application (static/js/)**

**O que é**: Aplicação web que carrega uma única página HTML e atualiza dinamicamente o conteúdo.

**Arquitetura**:
```
router.js       → Gerencia navegação (#/, #/integracoes/sams)
app.js          → Inicializa app, registra rotas, state management
pages/          → Lógica específica de cada página
```

**Fluxo de navegação**:
1. Usuário clica em link `<a href="#/integracoes/sams">`
2. Evento `hashchange` dispara
3. Router detecta hash `#/integracoes/sams`
4. Router renderiza template correspondente
5. Callback `onMount()` executa lógica da página

**Benefícios**:
- ⚡ Navegação instantânea (sem reload)
- 🎨 Transições suaves
- 📱 Experiência mobile-like
- 🔄 Estado preservado

---

### 4. **Jinja2 Templates (templates/)**

**O que é**: Engine de templates server-side para renderizar HTML.

**Estrutura**:
```html
<!-- base.html -->
{% block content %}{% endblock %}

<!-- home.html -->
{% extends "base.html" %}
{% block content %}
  <h1>Home</h1>
{% endblock %}
```

**Por que usar**:
- ✅ Reutilização de código (herança)
- ✅ SEO-friendly (HTML renderizado no servidor)
- ✅ Separação de responsabilidades
- ✅ Fallback para JS desabilitado

**Templates criados**:
- `base.html` - Layout comum (sidebar, topbar, scripts)
- `home.html` - Página inicial
- `services/sams_club.html` - Sam's Club
- `services/outras.html` - Outras integrações

---

### 5. **FastAPI Routers**

**O que são**: Organizadores de endpoints por contexto.

**Routers implementados**:

```python
# app/api/routes/__init__.py
router = APIRouter(prefix="/api", tags=["Health"])
- GET /api/health          → Health check
- GET /api/                → API info

# app/api/routes/web.py
router = APIRouter(tags=["Web"])
- GET /                    → Home page
- GET /integracoes/sams    → Sam's Club page
- GET /integracoes/outras  → Outras integrações

# app/services/sams_club/api/routes.py
router = APIRouter(prefix="/api/sams-club", tags=["Sam's Club"])
- POST /api/sams-club/process-batch/  → Processar imagens
```

**Registro no main.py**:
```python
app.include_router(api_router)           # /api/*
app.include_router(sams_club_router)     # /api/sams-club/*
app.include_router(web_router)           # /, /integracoes/*
```

---

## 🔄 Fluxo Completo de Funcionamento

### 1️⃣ **Inicialização do Servidor**

```bash
uvicorn main:app --reload
```

**O que acontece**:
1. `main.py` importa `FastAPI`
2. Carrega `Settings` de `app/core/config.py`
3. Configura CORS middleware
4. Inclui 3 routers (api, sams_club, web)
5. Monta diretórios estáticos (`/static/`, `/exports/`)
6. Servidor inicia em `http://localhost:8000`

---

### 2️⃣ **Usuário Acessa Homepage**

**Request**: `GET http://localhost:8000/`

**Fluxo backend**:
```python
# app/api/routes/web.py
@router.get("/")
async def home(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})
```

**Fluxo frontend**:
1. Browser recebe `templates/home.html`
2. HTML herda de `templates/base.html`
3. Carrega CSS: `/static/css/main.css`
4. Carrega JS: `/static/js/router.js`, `app.js`, `pages/samsClub.js`
5. Router.js detecta hash `#/` (ou vazio)
6. Renderiza homepage dinamicamente

---

### 3️⃣ **Usuário Navega para Sam's Club**

**Ação**: Clica em "Sam's Club" no menu

**Fluxo**:
1. Link: `<a href="#/integracoes/sams">`
2. Browser muda URL para `#/integracoes/sams`
3. Evento `hashchange` dispara
4. `router.js` → `navigate()`
5. Busca rota registrada `/integracoes/sams`
6. Renderiza `SamsClubTemplate()`
7. Chama `initSamsClubPage()` (onMount)
8. Página exibe interface de upload

---

### 4️⃣ **Processamento de Imagens**

**Ação**: Usuário adiciona imagens e clica "Processar Todos"

**Fluxo frontend** (`static/js/pages/samsClub.js`):
```javascript
// 1. Renomeia arquivos
product1_img1.jpg
product1_img2.jpg
product2_img1.jpg

// 2. Cria FormData
const formData = new FormData();
formData.append('files', file1);
formData.append('files', file2);

// 3. Envia POST
fetch('/api/sams-club/process-batch/', {
    method: 'POST',
    body: formData
})
```

**Fluxo backend** (`app/services/sams_club/api/routes.py`):
```python
@router.post("/process-batch/")
async def process_batch(files: List[UploadFile]):
    # 1. Agrupa imagens por produto (regex)
    groups = group_files_by_product(files)
    
    # 2. Para cada grupo, processa
    for group in groups:
        # Salva temporariamente
        temp_paths = save_temp_files(group)
        
        # Envia para Gemini
        result = send_to_gemini(temp_paths)
        
        # Armazena resultado
        results.append(result)
    
    # 3. Gera Excel
    excel_path = generate_excel_report(results)
    
    # 4. Retorna JSON
    return BatchResponse(
        products=results,
        excel_download_url=excel_path
    )
```

**Fluxo Gemini** (`app/services/sams_club/image_parser/gemini_client.py`):
```python
class GeminiClient:
    def extract_product_data(self, image_paths):
        # Carrega imagens
        images = [PIL.Image.open(path) for path in image_paths]
        
        # Monta prompt
        prompt = "Extraia: nome, preço, EAN..."
        
        # Chama API Gemini
        model = genai.GenerativeModel(settings.GEMINI_MODEL_TEXT)
        response = model.generate_content([prompt] + images)
        
        # Retorna JSON
        return json.loads(response.text)
```

---

### 5️⃣ **Resultado Exibido**

**Response JSON**:
```json
{
  "products": [
    {
      "num_images": 3,
      "filenames": ["product1_img1.jpg", ...],
      "gemini_response": {...},
      "error": null
    }
  ],
  "excel_download_url": "/exports/resultado_20260205_143022.xlsx"
}
```

**Frontend**:
1. Recebe JSON
2. Exibe card para cada produto
3. Mostra botão de download Excel
4. Anima inserção de resultados

---

## 🎨 Design System

### CSS Variables (static/css/main.css)

```css
:root {
    /* Gradientes */
    --primary-gradient: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    --secondary-gradient: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
    --success-gradient: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
    
    /* Cores sólidas */
    --primary-color: #667eea;
    --success-color: #10b981;
    --danger-color: #ef4444;
    
    /* Texto */
    --text-primary: #1f2937;
    --text-secondary: #6b7280;
    
    /* Background */
    --bg-primary: #ffffff;
    --bg-secondary: #f9fafb;
    
    /* Dimensões */
    --sidebar-width: 280px;
    
    /* Sombras */
    --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
}
```

**Benefícios**:
- 🎨 Tema consistente
- 🔄 Fácil customização
- 🌓 Preparado para dark mode
- ♿ Acessibilidade

### Componentes

**Sidebar**:
- Largura fixa 280px
- Background gradient escuro
- Navegação hierárquica
- Submenu expansível

**Cards**:
- Border-radius 16px
- Hover effects
- Borda lateral colorida
- Sombra suave

**Botões**:
- Gradientes vibrantes
- Transform hover (-3px)
- Estados disabled
- Icons + texto

---

## 📦 Tecnologias Utilizadas

### Backend

| Tecnologia | Versão | Uso |
|------------|--------|-----|
| **FastAPI** | Latest | Framework web assíncrono |
| **Pydantic** | 2.x | Validação de dados |
| **pydantic-settings** | Latest | Gerenciamento de configurações |
| **Jinja2** | Latest | Templates HTML server-side |
| **google-generativeai** | Latest | API Google Gemini (IA) |
| **google-cloud-storage** | Latest | Upload de imagens geradas |
| **Pillow** | Latest | Processamento de imagens |
| **openpyxl** | Latest | Geração de Excel |
| **uvicorn** | Latest | Servidor ASGI |

### Frontend

| Tecnologia | Uso |
|------------|-----|
| **Vanilla JavaScript** | SPA router, DOM manipulation |
| **CSS3** | Estilização (Variables, Grid, Flexbox) |
| **HTML5** | Markup semântico |
| **Google Fonts (Inter)** | Tipografia profissional |

### DevOps

| Tool | Uso |
|------|-----|
| **Git** | Controle de versão |
| **VS Code** | Editor |
| **Python venv** | Ambiente virtual |

---

## 🏗️ Padrões de Design Aplicados

### 1. **Separation of Concerns**
- Backend separado do frontend
- Lógica de negócio isolada da API
- Estilos separados do HTML

### 2. **Repository Pattern**
- `gemini_client.py` - Abstração da API Gemini
- `storage_client.py` - Abstração do GCS

### 3. **Dependency Injection**
- Settings injetadas via `app.core.config`
- Routers registrados dinamicamente

### 4. **Factory Pattern**
- `Router()` cria instância única
- `Settings()` singleton de configurações

### 5. **MVC (adaptado)**
- **Model**: `schemas.py` (Pydantic)
- **View**: `templates/` (Jinja2)
- **Controller**: `routes.py` (FastAPI)

---

## 🚀 Como Executar

### 1. **Instalar Dependências**
```bash
pip install -r requirements.txt
```

### 2. **Configurar Variáveis de Ambiente** (opcional)
```bash
# .env
GEMINI_API_KEY=sua_chave_aqui
GCP_STORAGE_BUCKET=seu_bucket
```

### 3. **Iniciar Servidor**
```bash
uvicorn main:app --reload
```

### 4. **Acessar Aplicação**
```
http://localhost:8000
```

### 5. **Endpoints Disponíveis**
- `GET /` - Homepage
- `GET /integracoes/sams` - Sam's Club
- `GET /api/health` - Health check
- `POST /api/sams-club/process-batch/` - Processar imagens
- `GET /docs` - Documentação Swagger automática

---

## 📚 Próximos Passos

### Curto Prazo
- [ ] Implementar testes unitários
- [ ] Adicionar logging estruturado
- [ ] Validação de inputs mais robusta
- [ ] Error handling padronizado

### Médio Prazo
- [ ] Autenticação JWT
- [ ] Rate limiting
- [ ] Cache com Redis
- [ ] Websockets para progresso em tempo real

### Longo Prazo
- [ ] Docker containerization
- [ ] CI/CD pipeline (GitHub Actions)
- [ ] Deploy em Cloud Run / AWS Lambda
- [ ] Monitoramento (Prometheus + Grafana)
- [ ] Novos microserviços (Walmart, Amazon, etc)

---

## 📖 Materiais de Estudo Recomendados

### FastAPI
- [Documentação Oficial](https://fastapi.tiangolo.com/)
- Tutorial de routers e dependency injection

### Pydantic
- [Pydantic V2 Docs](https://docs.pydantic.dev/latest/)
- Settings management

### JavaScript SPA
- Hash-based routing
- Fetch API
- ES6 modules

### CSS Moderno
- CSS Variables
- Grid e Flexbox
- Animações performáticas

### Arquitetura
- Microservices patterns
- Clean Architecture
- Domain-Driven Design (DDD)

---

## 🤝 Contribuindo

### Estrutura de Commit
```
feat: adiciona novo microserviço Walmart
fix: corrige agrupamento de imagens
docs: atualiza PROJECT_STRUCTURE.md
refactor: extrai lógica de Excel para helper
```

### Adicionando Microserviço
1. Crie pasta em `app/services/nome_servico/`
2. Implemente `schemas.py`, `api/routes.py`
3. Registre router no `main.py`
4. Crie página em `templates/services/`
5. Adicione rota no `static/js/app.js`
6. Atualize documentação

---

## 📝 Notas Importantes

### Diferenças entre estrutura antiga e nova:

**Antes**:
```
app/
  api/__init__.py  ← App FastAPI aqui (REMOVIDO)
  api/routes.py    ← Endpoint /process-batch/
  validation/gemini_client.py
  cloud/storage_client.py
  models/schemas.py
frontend/index.html  ← 1200 linhas monolíticas
```

**Depois**:
```
app/
  core/config.py                          ← Settings centralizadas
  api/routes/__init__.py                  ← Health check
  api/routes/web.py                       ← Páginas HTML
  services/sams_club/api/routes.py        ← /api/sams-club/process-batch/
  services/sams_club/image_parser/gemini_client.py
  services/sams_club/cloud/storage_client.py
  services/sams_club/schemas.py
static/css/main.css                       ← CSS separado
static/js/{router,app,pages/samsClub}.js  ← JS modular
templates/{base,home,services/*}.html     ← Jinja2 templates
main.py                                   ← App FastAPI aqui (NOVO)
```

### Por que essa mudança?

1. **Escalabilidade**: Adicionar Walmart, Amazon, etc sem modificar código existente
2. **Manutenibilidade**: Cada serviço tem seu próprio contexto
3. **Performance**: Assets otimizados, SPA rápido
4. **Profissionalismo**: Padrões de mercado, code quality
5. **Colaboração**: Times podem trabalhar em serviços diferentes

---

**Desenvolvido por Pietro Martins com ❤️**  
**Plataforma BD | AS - Fevereiro 2026**

**Propósito**: Extração de texto e códigos de barras das imagens.

**Arquivos**:
- `processor.py`:
  - `extract_barcodes()`: Detecta códigos de barras com pyzbar
  - `extract_text_from_image()`: OCR com Tesseract
  - `process_images()`: Processa múltiplas imagens

- `utils.py`:
  - `preprocess_image()`: Melhora qualidade da imagem (grayscale, contraste)
  - `clean_text()`: Limpa e normaliza texto extraído
  - `extract_patterns()`: Extrai padrões (preços, EANs)

**Por que existe**: Separação de responsabilidades - processamento vs. utilidades.

---

### 4. **app/validation/** - Validação com IA

**Propósito**: Integração com Google Gemini para extração inteligente de dados.

**Arquivos**:
- `gemini_client.py`:
  - `GeminiClient`: Classe cliente (Singleton pattern)
  - `extract_product_data()`: Envia imagens + OCR para Gemini
  - `send_to_gemini()`: Função conveniente para uso direto

**Por que existe**: Encapsulamento da lógica de IA, reutilização da conexão.

**Como funciona**:
1. Recebe múltiplas imagens do mesmo produto
2. Consolida dados de OCR e códigos de barras
3. Envia tudo junto para Gemini
4. Retorna JSON com nome, preço e EAN

---

### 5. **config/** - Configurações

**Arquivos**:
- `config.yaml`: 
  - Chave da API do Gemini
  - Configurações futuras

**Por que existe**: Separar credenciais do código, facilitar deploy.

---

## 🔄 Fluxo de Processamento

```
Cliente envia imagens
    ↓
POST /process-images/
    ↓
[routes.py] Recebe múltiplas imagens
    ↓
[ocr/processor.py] Extrai texto + códigos de barras de cada imagem
    ↓
[ocr/utils.py] Pré-processa e limpa dados
    ↓
[validation/gemini_client.py] Envia TODAS as imagens juntas para Gemini
    ↓
Gemini analisa e retorna JSON estruturado
    ↓
[models/schemas.py] Valida resposta
    ↓
Retorna ProductResponse ao cliente
```

---

## 🛠️ Tecnologias Utilizadas

- **FastAPI**: Framework web moderno e assíncrono
- **Tesseract OCR**: Extração de texto de imagens
- **pyzbar**: Detecção de códigos de barras
- **Pillow (PIL)**: Manipulação de imagens
- **Google Gemini API**: IA para extração inteligente de dados
- **Pydantic**: Validação de dados
- **PyYAML**: Configurações em YAML
- **Uvicorn**: Servidor ASGI

---

## 🎯 Funcionalidades Implementadas

✅ **Upload múltiplo de imagens** (mesmo produto)
✅ **OCR com Tesseract** (português)
✅ **Detecção de códigos de barras** (EAN-13, etc.)
✅ **Pré-processamento de imagens** (melhora precisão)
✅ **Integração com Gemini AI** (extração inteligente)
✅ **API REST documentada** (Swagger automático)
✅ **Validação de dados** (Pydantic schemas)
✅ **Estrutura profissional** (seguindo padrões do mercado)

---

## 📝 Funcionalidades Planejadas (Futuras)

- [ ] Agrupamento automático de imagens por produto
- [ ] Geração de descrições comerciais (app/descriptions)
- [ ] Testes unitários e de integração
- [ ] Logging estruturado
- [ ] Cache de respostas
- [ ] Frontend para interface visual
- [ ] Autenticação/Autorização
- [ ] Rate limiting
- [ ] Métricas e monitoramento

---

## 🚀 Como Executar

```bash
# Ativar ambiente virtual
.\venv\Scripts\activate

# Instalar dependências
pip install -r requirements.txt

# Rodar servidor
uvicorn main:app --reload
```

**Acessar documentação**: http://localhost:8000/docs

---

## 📖 Padrões e Boas Práticas Implementadas

✅ **Separation of Concerns**: Cada módulo tem uma responsabilidade clara
✅ **Clean Code**: Funções pequenas, nomes descritivos
✅ **Type Hints**: Tipagem em todas as funções
✅ **Docstrings**: Documentação em cada função/classe
✅ **Singleton Pattern**: GeminiClient reutilizável
✅ **Pydantic Models**: Validação automática de dados
✅ **Async/Await**: Código assíncrono eficiente
✅ **Error Handling**: Tratamento robusto de erros
✅ **Config Management**: Separação de credenciais

---

## 📌 Notas Importantes

1. **Uma request = Um produto**: Cada chamada ao `/process-images/` processa múltiplas imagens do MESMO produto
2. **Ordem não importa**: As imagens são analisadas em conjunto
3. **Backups disponíveis**: Versões anteriores salvas em `/backup/`
4. **Gemini Free Tier**: ~15-60 requests/minuto grátis

---

**Última atualização**: 01/02/2026
**Versão**: 1.0.0
**Autor**: Pietro