# Processo de Construção e Deploy na Cloud

Este documento descreve o processo completo de construção e deploy da aplicação "Equality Report Service" no Google Cloud Run.

## 1. Pré-requisitos

Antes de iniciar o processo de construção e deploy, certifique-se de ter:

1. **Google Cloud SDK instalado**:
   ```bash
   gcloud version
   ```

2. **Autenticação com o Google Cloud**:
   ```bash
   gcloud auth login
   ```

3. **Projeto Google Cloud configurado**:
   ```bash
   gcloud config set project [PROJECT_ID]
   ```

4. **Permissões adequadas** no projeto Google Cloud para:
   - Cloud Build
   - Cloud Run

## 2. Estrutura do Projeto

O projeto contém os seguintes arquivos principais:

- `app.py`: Aplicação FastAPI principal
- `processor.py`: Lógica de processamento de dados e geração de relatórios
- `Dockerfile`: Definição do container
- `requirements.txt`: Dependências Python
- `README.md`: Documentação do projeto

## 3. Processo de Construção

### 3.1. Construção do Container

O processo utiliza o Google Cloud Build para construir a imagem Docker:

```bash
gcloud builds submit --tag gcr.io/[PROJECT_ID]/equality-report-service .
```

Este comando:
1. Compacta os arquivos do projeto
2. Envia para o Google Cloud Build
3. Constrói a imagem Docker usando o Dockerfile
4. Armazena a imagem no Google Container Registry

### 3.2. Dockerfile

O Dockerfile define um container otimizado:

```dockerfile
# syntax=docker/dockerfile:1
FROM python:3.10-slim
WORKDIR /app

# Instala dependências do sistema
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libfreetype6-dev libpng-dev \
  && rm -rf /var/lib/apt/lists/*

# Instala dependências Python
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copia código da aplicação
COPY . .

# Configura porta e comando de execução
ENV PORT=8080
EXPOSE 8080
CMD ["uvicorn", "app:app", "--host","0.0.0.0","--port","8080"]
```

## 4. Processo de Deploy

### 4.1. Deploy no Cloud Run

Após a construção da imagem, o deploy é realizado com:

```bash
gcloud run deploy equality-report-service \
  --image gcr.io/[PROJECT_ID]/equality-report-service \
  --region [REGION] \
  --platform managed \
  --allow-unauthenticated
```

Parâmetros:
- `--image`: Imagem Docker a ser usada
- `--region`: Região do Google Cloud (ex: southamerica-east1)
- `--platform managed`: Usa o Cloud Run gerenciado
- `--allow-unauthenticated`: Permite acesso público

### 4.2. Configurações do Deploy

O Cloud Run configura automaticamente:
- Escalonamento automático (0 a N instâncias)
- HTTPS automático
- Balanceamento de carga
- Monitoramento integrado

## 5. Verificação do Deploy

### 5.1. Verificação do Serviço

Para verificar se o deploy foi bem-sucedido:

```bash
# Verificar status do serviço
gcloud run services describe equality-report-service --region [REGION]

# Verificar logs
gcloud run services logs read equality-report-service --region [REGION] --limit 20
```

### 5.2. Teste de Funcionamento

Teste o endpoint da API:

```bash
# Acessar documentação
curl https://[SERVICE_URL]/docs

# Testar endpoint de processamento
curl -X POST https://[SERVICE_URL]/process \
  -F "file=@dados.csv" \
  -F "company_name=Empresa Exemplo" \
  -o relatorio.zip
```

## 6. Pipeline Completo de CI/CD

### 6.1. Script de Deploy Automatizado

```bash
#!/bin/bash
# deploy.sh

PROJECT_ID="seu-project-id"
REGION="southamerica-east1"
SERVICE_NAME="equality-report-service"

echo "Construindo imagem..."
gcloud builds submit --tag gcr.io/$PROJECT_ID/$SERVICE_NAME .

echo "Fazendo deploy..."
gcloud run deploy $SERVICE_NAME \
  --image gcr.io/$PROJECT_ID/$SERVICE_NAME \
  --region $REGION \
  --platform managed \
  --allow-unauthenticated

echo "Deploy concluído!"
```

### 6.2. Processo Manual Completo

1. **Autenticação**:
   ```bash
   gcloud auth login
   gcloud config set project [PROJECT_ID]
   ```

2. **Construção**:
   ```bash
   gcloud builds submit --tag gcr.io/[PROJECT_ID]/equality-report-service .
   ```

3. **Deploy**:
   ```bash
   gcloud run deploy equality-report-service \
     --image gcr.io/[PROJECT_ID]/equality-report-service \
     --region southamerica-east1 \
     --platform managed \
     --allow-unauthenticated
   ```

4. **Verificação**:
   ```bash
   gcloud run services describe equality-report-service --region southamerica-east1
   ```

## 7. Monitoramento e Manutenção

### 7.1. Logs

Visualizar logs em tempo real:
```bash
gcloud run services logs read equality-report-service --region [REGION] --follow
```

### 7.2. Métricas

Monitorar métricas no Google Cloud Console:
- Latência das requisições
- Taxa de erros
- Utilização de CPU e memória
- Número de instâncias ativas

### 7.3. Atualizações

Para atualizar o serviço:
1. Fazer alterações no código
2. Reconstruir a imagem:
   ```bash
   gcloud builds submit --tag gcr.io/[PROJECT_ID]/equality-report-service .
   ```
3. Redeploy automático (Cloud Run detecta nova imagem)

## 8. Troubleshooting

### 8.1. Problemas Comuns

1. **Erro "File not found"**:
   - Causa: Diretório temporário sendo deletado antes do envio da resposta
   - Solução: Ler o conteúdo do arquivo antes de retornar a resposta

2. **Erro de permissões**:
   - Causa: Falta de permissões no projeto Google Cloud
   - Solução: Verificar permissões do usuário e APIs ativadas

3. **Erro de memória**:
   - Causa: Processamento de arquivos grandes
   - Solução: Ajustar limites de memória no Cloud Run

### 8.2. Comandos Úteis

```bash
# Listar serviços
gcloud run services list

# Ver detalhes de um serviço
gcloud run services describe [SERVICE_NAME] --region [REGION]

# Ver logs
gcloud run services logs read [SERVICE_NAME] --region [REGION]

# Deletar serviço
gcloud run services delete [SERVICE_NAME] --region [REGION]
```

## 9. Boas Práticas

### 9.1. Segurança
- Usar variáveis de ambiente para credenciais
- Limitar permissões do serviço
- Usar HTTPS (automático no Cloud Run)

### 9.2. Performance
- Otimizar tamanho da imagem Docker
- Usar caching apropriado
- Monitorar uso de recursos

### 9.3. Manutenibilidade
- Manter README atualizado
- Versionar código e configurações
- Documentar processo de deploy

## 10. Funcionalidades Específicas

### 10.1. Cálculo da Razão do Salário Contratual Mediano

A aplicação implementa corretamente o cálculo da "Razão do Salário Contratual Mediano":

1. **Mediana Salarial por Grupo Ocupacional e Sexo**:
   - Calcula a mediana do campo `salario_contratual_mensal` para cada grupo ocupacional (CBO) separadamente por sexo
   
2. **Razão Mediana F/M**:
   - Divide a mediana feminina pela mediana masculina para obter a razão
   - Armazena o resultado no campo `ratio_mediana_F_M`

3. **Campos Inclusos nos Relatórios**:
   - `mediana_sal_F`: Mediana salarial feminina
   - `mediana_sal_M`: Mediana salarial masculina  
   - `ratio_mediana_F_M`: Razão (Mediana F / Mediana M)
   - `media_rem_F`: Média remuneração feminina
   - `media_rem_M`: Média remuneração masculina
   - `ratio_media_F_M`: Razão (Média F / Média M)

### 10.2. Distribuição de Trabalhadores por CBO e Sexo

A aba "Distribuicao_CBO" no relatório Excel agora inclui:
- Distribuição total de trabalhadores por CBO
- Distribuição por sexo (colunas F e M)
- Percentuais por sexo (%F e %M)
- Gráficos comparativos

Esta implementação permite análises detalhadas da composição de gênero em diferentes cargos e áreas da empresa.