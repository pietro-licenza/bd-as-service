# BD | AS Platform - Image Parser Service

Uma plataforma profissional de integração e automação para processamento de dados com IA.

## 🚀 Deploy no Cloud Run

### Pré-requisitos
1. Conta Google Cloud Platform
2. Projeto GCP configurado
3. Secret Manager com chave do service account

### Deploy Rápido
```bash
# Clone o repositório
git clone https://github.com/pietro-licenza/bd-as-service.git
cd bd-as-service

# Execute o script de deploy
./deploy.sh
```

### Configuração Manual
1. Build da imagem:
```bash
gcloud builds submit --tag gcr.io/SEU_PROJECT/bd-as-platform
```

2. Deploy no Cloud Run:
```bash
gcloud run deploy bd-as-platform \
  --image gcr.io/SEU_PROJECT/bd-as-platform \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --port 8080
```

## 🏗️ Arquitetura

- **Backend:** FastAPI (Python)
- **Frontend:** SPA (Vanilla JS)
- **IA:** Google Gemini
- **Cloud:** Google Cloud Storage & Secret Manager
- **Container:** Docker + Cloud Run

## 📁 Estrutura do Projeto

```
bd-as-service/
├── app/                    # Backend FastAPI
├── static/                 # Frontend assets
├── templates/              # Jinja2 templates
├── Dockerfile             # Container config
├── deploy.sh              # Deploy script
└── cloudbuild.yaml        # CI/CD config
```

## 🔧 Desenvolvimento Local

```bash
# Instalar dependências
pip install -r requirements.txt

# Executar aplicação
uvicorn main:app --reload

# Acessar: http://localhost:8000
```

## 📡 API Endpoints

- `GET /` - Página inicial
- `GET /api/health` - Health check
- `POST /api/sams-club/process` - Processar imagens Sam's Club
- `GET /docs` - Documentação Swagger

## 🤝 Contribuição

1. Fork o projeto
2. Crie uma branch (`git checkout -b feature/nova-feature`)
3. Commit suas mudanças (`git commit -am 'Adiciona nova feature'`)
4. Push para a branch (`git push origin feature/nova-feature`)
5. Abra um Pull Request

## 📄 Licença

Este projeto está sob a licença MIT.