# Atualização: Distribuição de Trabalhadores por CBO e Sexo

## Descrição da Alteração

Esta atualização modifica a aba "Distribuicao_CBO" no relatório Excel para incluir a distribuição de trabalhadores por sexo, além da distribuição total por CBO.

## Alterações Realizadas

### 1. Modificação na Função `process_data`

A função `process_data` no arquivo `processor.py` foi atualizada para incluir informações de distribuição por sexo:

```python
# Antes: Apenas distribuição total por CBO
dist_cbo = df_proc.groupby([\"cbo_2002\", \"cbo_titulo\"]) [\"id_trabalhador_hash\"].nunique().reset_index()
dist_cbo = dist_cbo.rename(columns={\"id_trabalhador_hash\": \"count_workers\"})

# Depois: Distribuição por CBO e sexo, com pivot para facilitar visualização
# Distribution by CBO and sexo
dist_cbo_sexo = df_proc.groupby([\"cbo_2002\", \"cbo_titulo\", \"sexo\"]) [\"id_trabalhador_hash\"].nunique().reset_index()
dist_cbo_sexo = dist_cbo_sexo.rename(columns={\"id_trabalhador_hash\": \"count_workers\"})

# Pivot dist_cbo_sexo to get sex distribution
dist_cbo_sex_pivot = dist_cbo_sexo.pivot_table(
    index=[\"cbo_2002\", \"cbo_titulo\"], 
    columns=\"sexo\", 
    values=\"count_workers\", 
    fill_value=0
).reset_index()

# Add total column
dist_cbo_sex_pivot[\"Total\"] = dist_cbo_sex_pivot.get(\"F\", 0) + dist_cbo_sex_pivot.get(\"M\", 0)

# Inclusão no dicionário de resultados
return {
    # ... outros resultados ...
    \"dist_cbo_sexo\": dist_cbo_sex_pivot,  # NEW: Include sex distribution
}
```

### 2. Modificação na Função `create_excel`

A função `create_excel` foi atualizada para incluir uma nova aba "Distribuicao_CBO_Sexo" com a distribuição por sexo:

```python
# NEW: Distribution by CBO and Sexo sheet
# Pivot the sex distribution data for easier viewing in the main distribution sheet
dist_cbo_sexo_pivot = dist_cbo_sexo.pivot_table(
    index=[\"cbo_2002\", \"cbo_titulo\"], 
    columns=\"sexo\", 
    values=\"count_workers\", 
    fill_value=0
).reset_index()

# Add total column
dist_cbo_sexo_pivot[\"Total\"] = dist_cbo_sexo_pivot.get(\"F\", 0) + dist_cbo_sexo_pivot.get(\"M\", 0)

dist_cbo_sexo_pivot.to_excel(writer, sheet_name=\"Distribuicao_CBO_Sexo\", index=False)
sheet_dist_sexo = writer.sheets[\"Distribuicao_CBO_Sexo\"]
for col_num, col_name in enumerate(dist_cbo_sexo_pivot.columns):
    sheet_dist_sexo.write(0, col_num, col_name, header_fmt)

# Chart for sex distribution
chart4 = workbook.add_chart({\"type\": \"column\"})
f_col = list(dist_cbo_sexo_pivot.columns).index(\"F\") if \"F\" in dist_cbo_sexo_pivot.columns else -1
m_col = list(dist_cbo_sexo_pivot.columns).index(\"M\") if \"M\" in dist_cbo_sexo_pivot.columns else -1

if f_col >= 0:
    chart4.add_series({
        \"name\": \"Mulheres\",
        \"categories\": [\"Distribuicao_CBO_Sexo\", 1, 1, len(dist_cbo_sexo_pivot), 1],
        \"values\": [\"Distribuicao_CBO_Sexo\", 1, f_col, len(dist_cbo_sexo_pivot), f_col],
        \"fill\": {\"color\": primary_color},
    })

if m_col >= 0:
    chart4.add_series({
        \"name\": \"Homens\",
        \"categories\": [\"Distribuicao_CBO_Sexo\", 1, 1, len(dist_cbo_sexo_pivot), 1],
        \"values\": [\"Distribuicao_CBO_Sexo\", 1, m_col, len(dist_cbo_sexo_pivot), m_col],
        \"fill\": {\"color\": accent_color},
    })

chart4.set_title({\"name\": \"Distribuição de Trabalhadores por CBO e Sexo\"})
chart4.set_x_axis({\"name\": \"CBO\"})
chart4.set_y_axis({\"name\": \"# Trabalhadores\"})
chart4.set_legend({\"position\": \"bottom\"})
sheet_dist_sexo.insert_chart(\"F2\", chart4, {\"x_scale\": 1.5, \"y_scale\": 1.5})
```

## Resultados

Com esta atualização, o relatório Excel agora inclui:

1. **Aba "Distribuicao_CBO"** - Mantém a distribuição total de trabalhadores por CBO
2. **Nova aba "Distribuicao_CBO_Sexo"** - Mostra a distribuição de trabalhadores por CBO e sexo:
   - Colunas separadas para homens (M) e mulheres (F)
   - Coluna "Total" com a soma
   - Gráfico de barras comparando a distribuição por sexo

## Benefícios

Esta atualização permite uma análise mais detalhada da composição de gênero em diferentes cargos e áreas da empresa, facilitando a identificação de possíveis disparidades na distribuição de trabalhadores por sexo em cada grupo ocupacional.