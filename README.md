# Relatório de Igualdade Salarial

Este serviço permite a geração de relatórios completos sobre igualdade salarial, com análise por gênero e raça/cor, em conformidade com a legislação brasileira.

## Funcionalidades

- Análise de igualdade salarial por gênero (razão entre salários médios e medianos de homens e mulheres)
- Distribuição de trabalhadores por ocupação (CBO), gênero e raça/cor
- Identificação de possíveis desigualdades através de classificação por semáforo (Vermelho, Âmbar, Verde, Insuficiente)
- Geração de relatórios em múltiplos formatos:
  - Excel (.xlsx) com tabelas e gráficos
  - PDF para apresentações
  - Word (.docx) opcional
- Visualização de dados através de gráficos e tabelas

## Como Usar

### 1. Preparar os Dados

O arquivo de entrada deve ser um CSV ou Excel contendo as seguintes colunas:

- `cnpj_estabelecimento`: CNPJ do estabelecimento
- `cbo_2002`: Código da ocupação (CBO)
- `cbo_titulo`: Nome da ocupação
- `sexo`: Sexo do trabalhador (M/F)
- `raca_cor`: Raça/Cor do trabalhador (Branca, Preta, Parda, Amarela, Indígena)
- `salario_contratual_mensal`: Salário contratual mensal
- `remuneracao_total_mensal`: Remuneração total mensal
- `data_competencia`: Data de competência (AAAA-MM-DD)
- `id_trabalhador_hash`: Identificador único do trabalhador (hash)

### 2. Acessar a Interface Web

Acesse a interface web do serviço para enviar seus dados e configurar as opções de relatório.

### 3. Configurar as Opções

- **Nome da Empresa**: Nome que aparecerá nos relatórios
- **Tamanho Mínimo do Grupo**: Valor de k-anonimato para proteção de dados (padrão: 5)
- **Cores dos Gráficos**: Cores primária e secundária para personalização dos relatórios
- **Gerar Relatório Word**: Opção para incluir relatório em formato Word

### 4. Enviar os Dados

Faça upload do arquivo com os dados de remuneração e clique em "Gerar Relatório".

### 5. Baixar os Resultados

Após o processamento, você receberá um arquivo ZIP contendo:
- Relatório em Excel com análises detalhadas
- Relatório em PDF para apresentações
- Relatório em Word (se solicitado)

## API Endpoints

### Processar Dados

```
POST /process
```

Parâmetros (multipart/form-data):
- `file`: Arquivo CSV ou Excel com os dados
- `company_name`: Nome da empresa (opcional, padrão: "Empresa Demo")
- `k_min`: Tamanho mínimo do grupo (opcional, padrão: 5)
- `primary_color`: Cor primária dos gráficos (opcional, padrão: "#0F6CBD")
- `accent_color`: Cor secundária dos gráficos (opcional, padrão: "#585858")
- `generate_docx`: Gerar relatório Word (opcional, padrão: false)

## Indicadores Calculados

1. **Razão da Diferença do Salário Médio de Contratação**:
   - Soma dos salários de todas as mulheres e de todos os homens de um mesmo grupo de ocupações
   - Divide pelo número de empregados de cada sexo
   - Resultado é a razão entre o salário médio das mulheres e o dos homens

2. **Razão da Diferença da Mediana Salarial**:
   - Mediana salarial por gênero em cada ocupação
   - Razão entre a mediana das mulheres e a dos homens

3. **Distribuição Demográfica**:
   - Quantitativo de pessoas por ocupação, sexo e raça/cor
   - Percentuais de distribuição

4. **Classificação por Semáforo**:
   - Vermelho: Razão < 0.95 (grande desigualdade)
   - Âmbar: Razão entre 0.95 e 0.99 (desigualdade moderada)
   - Verde: Razão ≥ 0.99 (igualdade salarial)
   - Insuficiente: Grupos com menos dados que o mínimo configurado

## Requisitos Técnicos

- Python 3.8+
- Dependências listadas em `requirements.txt`
- Servidor web compatível com FastAPI/uvicorn

## Deploy

O serviço pode ser executado localmente ou implantado em ambientes cloud como Google Cloud Run.