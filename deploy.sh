#!/bin/bash
# Script de deploy automatizado para o serviço Equality Report Service

# Variáveis de configuração
PROJECT_ID="salarialmte"
REGION="southamerica-east1"
SERVICE_NAME="equality-report-service"

echo "=== Script de Deploy do Equality Report Service ==="
echo "Projeto: $PROJECT_ID"
echo "Região: $REGION"
echo "Serviço: $SERVICE_NAME"
echo ""

# Verificar autenticação
echo "Verificando autenticação com Google Cloud..."
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" >/dev/null 2>&1; then
    echo "ERRO: Não autenticado no Google Cloud. Execute 'gcloud auth login' primeiro."
    exit 1
fi

echo "Autenticação OK"
echo ""

# Verificar projeto
echo "Verificando projeto Google Cloud..."
CURRENT_PROJECT=$(gcloud config list project --format="value(core.project)" 2>/dev/null)
if [ "$CURRENT_PROJECT" != "$PROJECT_ID" ]; then
    echo "Configurando projeto para $PROJECT_ID..."
    gcloud config set project $PROJECT_ID
fi

echo "Projeto configurado: $PROJECT_ID"
echo ""

# Construção da imagem
echo "Construindo imagem Docker..."
gcloud builds submit --tag gcr.io/$PROJECT_ID/$SERVICE_NAME .

if [ $? -ne 0 ]; then
    echo "ERRO: Falha na construção da imagem Docker."
    exit 1
fi

echo "Imagem construída com sucesso!"
echo ""

# Deploy no Cloud Run
echo "Realizando deploy no Cloud Run..."
gcloud run deploy $SERVICE_NAME \
  --image gcr.io/$PROJECT_ID/$SERVICE_NAME \
  --region $REGION \
  --platform managed \
  --allow-unauthenticated

if [ $? -ne 0 ]; then
    echo "ERRO: Falha no deploy do serviço."
    exit 1
fi

echo ""
echo "Deploy concluído com sucesso!"

# Obter URL do serviço
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region $REGION --format="value(status.url)")
echo "URL do serviço: $SERVICE_URL"

echo ""
echo "=== Testando serviço ==="

# Teste básico
echo "Testando acesso à documentação..."
curl -s $SERVICE_URL/docs | grep -q "Swagger UI" && echo "✓ Serviço acessível" || echo "✗ Erro ao acessar serviço"

echo ""
echo "=== Deploy finalizado ==="