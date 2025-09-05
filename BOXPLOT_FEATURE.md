# Implementação de Boxplots no Relatório Excel

## Descrição

Adicionei uma nova aba ao relatório Excel gerado pelo serviço chamada "Boxplots_Salarios" que contém:

1. Boxplots de distribuição salarial por CBO e sexo (F/M)
2. Labels com os valores das medianas para cada grupo
3. Cores profissionais: roxo para mulheres (F) e amarelo para homens (H)
4. Dados brutos usados para os cálculos em formato de tabela para reproducibilidade

## Detalhes Técnicos

### Cores Utilizadas
- Mulheres (F): Roxo (#9966CC)
- Homens (M): Amarelo (#FFD700)

### Estrutura da Nova Aba
- Título descritivo
- Gráficos de dispersão simulando boxplots para cada CBO
- Labels com valores das medianas
- Tabela com dados brutos usados para cálculos:
  - CBO
  - Título
  - Sexo
  - Salário
  - Quartis (Q1, Q2/Mediana, Q3)
  - Valores mínimos e máximos

## Arquivos Modificados

1. `processor.py` - Adicionada a geração da nova aba com boxplots
2. `test_boxplot.py` - Script de teste para validação local
3. `test_boxplot_api.py` - Script de teste para validação via API

## Testes Realizados

1. Teste local com dados de amostra
2. Geração de relatório Excel com a nova aba
3. Verificação das cores e labels

O relatório agora oferece uma visualização mais rica dos dados salariais, permitindo uma análise mais detalhada das distribuições de salários por ocupação e gênero.