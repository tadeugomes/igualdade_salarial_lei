# Script de deploy automatizado para o serviço Equality Report Service (Windows PowerShell)

# Variáveis de configuração
$PROJECT_ID = "salarialmte"
$REGION = "southamerica-east1"
$SERVICE_NAME = "equality-report-service"

Write-Host "=== Script de Deploy do Equality Report Service ===" -ForegroundColor Green
Write-Host "Projeto: $PROJECT_ID"
Write-Host "Região: $REGION"
Write-Host "Serviço: $SERVICE_NAME"
Write-Host ""

# Verificar autenticação
Write-Host "Verificando autenticação com Google Cloud..." -ForegroundColor Yellow
try {
    $authCheck = gcloud auth list --filter=status:ACTIVE --format="value(account)" 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "Erro na verificação de autenticação"
    }
} catch {
    Write-Host "ERRO: Não autenticado no Google Cloud. Execute 'gcloud auth login' primeiro." -ForegroundColor Red
    exit 1
}

Write-Host "Autenticação OK" -ForegroundColor Green
Write-Host ""

# Verificar projeto
Write-Host "Verificando projeto Google Cloud..." -ForegroundColor Yellow
try {
    $currentProject = gcloud config list project --format="value(core.project)" 2>$null
    if ($currentProject -ne $PROJECT_ID) {
        Write-Host "Configurando projeto para $PROJECT_ID..." -ForegroundColor Yellow
        gcloud config set project $PROJECT_ID
    }
} catch {
    Write-Host "ERRO: Falha ao configurar o projeto." -ForegroundColor Red
    exit 1
}

Write-Host "Projeto configurado: $PROJECT_ID" -ForegroundColor Green
Write-Host ""

# Construção da imagem
Write-Host "Construindo imagem Docker..." -ForegroundColor Yellow
gcloud builds submit --tag "gcr.io/$PROJECT_ID/$SERVICE_NAME" .

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERRO: Falha na construção da imagem Docker." -ForegroundColor Red
    exit 1
}

Write-Host "Imagem construída com sucesso!" -ForegroundColor Green
Write-Host ""

# Deploy no Cloud Run
Write-Host "Realizando deploy no Cloud Run..." -ForegroundColor Yellow
gcloud run deploy $SERVICE_NAME `
  --image "gcr.io/$PROJECT_ID/$SERVICE_NAME" `
  --region $REGION `
  --platform managed `
  --allow-unauthenticated

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERRO: Falha no deploy do serviço." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Deploy concluído com sucesso!" -ForegroundColor Green

# Obter URL do serviço
try {
    $serviceUrl = gcloud run services describe $SERVICE_NAME --region $REGION --format="value(status.url)" 2>$null
    Write-Host "URL do serviço: $serviceUrl" -ForegroundColor Cyan
} catch {
    Write-Host "Não foi possível obter a URL do serviço." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=== Testando serviço ===" -ForegroundColor Yellow

# Teste básico
Write-Host "Testando acesso à documentação..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "$serviceUrl/docs" -UseBasicParsing -TimeoutSec 10
    if ($response.StatusCode -eq 200 -and $response.Content -like "*Swagger UI*") {
        Write-Host "✓ Serviço acessível" -ForegroundColor Green
    } else {
        Write-Host "✗ Erro ao acessar serviço" -ForegroundColor Red
    }
} catch {
    Write-Host "✗ Erro ao acessar serviço: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host ""
Write-Host "=== Deploy finalizado ===" -ForegroundColor Green
Write-Host "Pressione qualquer tecla para sair..."
$host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")