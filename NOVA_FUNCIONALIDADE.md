## Novo Relatório Quantitativo por CBO, Sexo e Raça/Cor

Foi adicionada uma nova funcionalidade ao sistema que gera um relatório quantitativo de pessoas por ocupação (CBO), sexo e raça/cor.

### Funcionalidades:

1. **Planilha "Distribuicao_Detalhada"**: 
   - Contém dados quantitativos de pessoas agrupados por CBO, sexo e raça/cor
   - Cada linha representa uma combinação única de CBO, sexo e raça/cor com a contagem de trabalhadores

2. **Gráficos por CBO**:
   - Para cada CBO no conjunto de dados, é gerado um gráfico separado
   - Os gráficos mostram a distribuição de trabalhadores por sexo e raça/cor
   - Os gráficos são posicionados na mesma planilha "Distribuicao_Detalhada"

### Alterações Realizadas:

1. **processor.py**:
   - Adicionado `dist_cbo_detailed` aos dados agregados na função `process_data`
   - Modificado a função `create_excel` para incluir a nova planilha e gráficos

### Teste:

Para testar a funcionalidade, execute:
```
python test_quantitative_report_manual.py
```

Isso irá gerar um arquivo `relatorio_teste.xlsx` no diretório do projeto que pode ser inspecionado.