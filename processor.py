"""
Core data processing and report generation for the equality report service.

This module exposes functions to load the input dataset, compute the
statistics required by the Brazilian salary equality legislation, and
generate output artifacts (Excel workbook and PDF report). The functions
here are designed to be reused both by the API layer (FastAPI) and by
standalone scripts for debugging or local execution.
"""

import os
import sys
import tempfile
import zipfile
from typing import Dict, List, Tuple, Union, Any

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import xlsxwriter


def load_input(file_path: str) -> pd.DataFrame:
    """Load the input payroll data from CSV or Excel.

    Parameters
    ----------
    file_path : str
        Path to the uploaded file. Supported extensions are .csv and .xlsx.

    Returns
    -------
    DataFrame
        The loaded dataset with columns as string type.

    Raises
    ------
    ValueError
        If the file extension is not supported.
    """
    _, ext = os.path.splitext(file_path.lower())
    if ext == ".csv":
        df = pd.read_csv(file_path)
    elif ext in (".xlsx", ".xlsm"):
        df = pd.read_excel(file_path, engine="openpyxl")
    else:
        raise ValueError(f"Unsupported file type: {ext}")
    # Ensure expected columns exist or raise an error early
    expected = {
        "cnpj_estabelecimento",
        "cbo_2002",
        "cbo_titulo",
        "sexo",
        "raca_cor",
        "salario_contratual_mensal",
        "remuneracao_total_mensal",
        "data_competencia",
        "id_trabalhador_hash",
    }
    missing = expected - set(map(str.lower, df.columns))
    # If some columns missing due to case differences, attempt to normalise
    df.columns = [c.strip() for c in df.columns]
    lower_columns = {c.lower(): c for c in df.columns}
    for col in list(expected):
        if col.lower() in lower_columns:
            continue
        else:
            missing.add(col)
    if missing:
        raise ValueError(
            f"Missing required columns: {', '.join(sorted(missing))}."
        )
    return df


def process_data(df: pd.DataFrame, k_min: int = 5) -> Dict[str, object]:
    """Compute aggregated indicators required for the report.

    Parameters
    ----------
    df : DataFrame
        Raw dataset containing the required columns.
    k_min : int
        Minimum group size for k‑anonymity. Groups smaller than this
        threshold are marked as "Insuficiente" in the semáforo.

    Returns
    -------
    dict
        A dictionary containing the aggregated tables and metrics.
    """
    df_proc = df.copy()
    # Convert competence date to monthly period
    df_proc["data_competencia"] = pd.to_datetime(
        df_proc["data_competencia"], errors="coerce"
    ).dt.to_period("M")
    # Group by CBO and sexo
    group = df_proc.groupby(["cbo_2002", "cbo_titulo", "sexo"])
    summary = group.agg(
        mediana_sal=("salario_contratual_mensal", "median"),
        media_rem=("remuneracao_total_mensal", "mean"),
        count=("id_trabalhador_hash", pd.Series.nunique),
    ).reset_index()
    # Pivot to separate sexes
    pivot_med = summary.pivot(index=["cbo_2002", "cbo_titulo"], columns="sexo", values="mediana_sal")
    pivot_mean = summary.pivot(index=["cbo_2002", "cbo_titulo"], columns="sexo", values="media_rem")
    counts_pivot = summary.pivot(index=["cbo_2002", "cbo_titulo"], columns="sexo", values="count")
    # Compute ratios
    pivot_med["ratio_med"] = pivot_med["F"] / pivot_med["M"]
    pivot_mean["ratio_mean"] = pivot_mean["F"] / pivot_mean["M"]
    # Classify groups
    classifications = []
    for idx in pivot_med.index:
        n_f = counts_pivot.loc[idx, "F"]
        n_m = counts_pivot.loc[idx, "M"]
        ratio = pivot_med.loc[idx, "ratio_med"]
        if n_f < k_min or n_m < k_min:
            classifications.append("Insuficiente")
        elif ratio < 0.95:
            classifications.append("Vermelho")
        elif ratio < 0.99:
            classifications.append("Âmbar")
        else:
            classifications.append("Verde")
    result_df = pd.DataFrame({
        "cbo_2002": [idx[0] for idx in pivot_med.index],
        "cbo_titulo": [idx[1] for idx in pivot_med.index],
        "mediana_sal_F": pivot_med["F"],
        "mediana_sal_M": pivot_med["M"],
        "razao_mediana_F_M": pivot_med["ratio_med"],
        "media_rem_F": pivot_mean["F"],
        "media_rem_M": pivot_mean["M"],
        "razao_media_F_M": pivot_mean["ratio_mean"],
        "n_F": counts_pivot["F"],
        "n_M": counts_pivot["M"],
        "classificacao": classifications,
    }).reset_index(drop=True)
    # Trend per month
    trends = df_proc.groupby(["data_competencia", "sexo"]) ["remuneracao_total_mensal"].mean().unstack()
    trends["razao_F_M"] = trends["F"] / trends["M"]
    trends = trends.reset_index().rename(columns={"data_competencia": "data_competencia"})
    # Distribution by CBO (total)
    dist_cbo_grouped = df_proc.groupby(['cbo_2002', 'cbo_titulo'])
    dist_cbo_total = dist_cbo_grouped['id_trabalhador_hash'].nunique().reset_index()
    dist_cbo_total = dist_cbo_total.rename(columns={'id_trabalhador_hash': 'total_trabalhadores'})
    
    # Distribution by CBO and sexo
    dist_cbo_sexo = df_proc.groupby(['cbo_2002', 'cbo_titulo', 'sexo']) ['id_trabalhador_hash'].nunique().reset_index()
    dist_cbo_sexo = dist_cbo_sexo.rename(columns={'id_trabalhador_hash': 'contagem_trabalhadores'})
    
    # Distribution by CBO, sexo, and raca_cor
    dist_cbo_sexo_raca = df_proc.groupby(['cbo_2002', 'cbo_titulo', 'sexo', 'raca_cor']) ['id_trabalhador_hash'].nunique().reset_index()
    dist_cbo_sexo_raca = dist_cbo_sexo_raca.rename(columns={'id_trabalhador_hash': 'contagem_trabalhadores'})
    
    # Pivot dist_cbo_sexo to get sex distribution
    dist_cbo_sex_pivot = dist_cbo_sexo.pivot_table(
        index=['cbo_2002', 'cbo_titulo'], 
        columns='sexo', 
        values='contagem_trabalhadores', 
        fill_value=0
    ).reset_index()
    
    # Merge total and sex distributions
    dist_cbo = dist_cbo_total.merge(dist_cbo_sex_pivot, on=['cbo_2002', 'cbo_titulo'], how='left')
    dist_cbo = dist_cbo.fillna(0)
    
    # Ensure F and M columns exist
    if 'F' not in dist_cbo.columns:
        dist_cbo['F'] = 0
    if 'M' not in dist_cbo.columns:
        dist_cbo['M'] = 0
        
    # Add percentage columns
    dist_cbo['percentual_F'] = (dist_cbo['F'] / dist_cbo['total_trabalhadores'] * 100).round(2)
    dist_cbo['percentual_M'] = (dist_cbo['M'] / dist_cbo['total_trabalhadores'] * 100).round(2)
    
    # Semaforo counts
    semaforo_counts = pd.Series(classifications).value_counts()
    # Top positive/negative (by razao_mediana_F_M)
    top_pos = result_df.sort_values('razao_mediana_F_M', ascending=False).head(3)
    top_neg = result_df.sort_values('razao_mediana_F_M', ascending=True).head(3)
    # KPIs
    kpi_ratio_med_mean = result_df['razao_mediana_F_M'].mean()
    kpi_ratio_media_mean = result_df['razao_media_F_M'].mean()
    # Plan of action for Vermelho
    plan_df = result_df[result_df['classificacao'] == 'Vermelho'].copy()
    plan_df['medida'] = 'Revisar faixas salariais'
    plan_df['meta'] = 'Atingir paridade (1.0)'
    plan_df['prazo'] = 'Próximo semestre'
    return {
        'result_df': result_df,
        'trends': trends,
        'dist_cbo': dist_cbo,
        'dist_cbo_sexo': dist_cbo_sexo,  # Include sex distribution
        'dist_cbo_sexo_raca': dist_cbo_sexo_raca,  # Include sex and race distribution
        'semaforo_counts': semaforo_counts,
        'top_pos': top_pos,
        'top_neg': top_neg,
        'kpi_ratio_med_mean': kpi_ratio_med_mean,
        'kpi_ratio_media_mean': kpi_ratio_media_mean,
        'plan_df': plan_df,
        'dist_cbo_total': dist_cbo_total,  # Include total distribution
    }


def create_excel(
    df: pd.DataFrame,
    aggregates: Dict[str, object],
    excel_path: str,
    primary_color: str = "#0F6CBD",
    accent_color: str = "#585858",
) -> None:
    """Generate an Excel workbook with tables and charts.

    Parameters
    ----------
    df : DataFrame
        Raw dataset used for boxplots.
    aggregates : dict
        Aggregated results returned from ``process_data``.
    excel_path : str
        Path to write the Excel workbook.
    primary_color : str
        Hex colour used for primary elements (headers, first series).
    accent_color : str
        Hex colour used for secondary elements (second series).
    """
    # Create a copy of the original dataframe for processing
    df_proc = df.copy()
    # Convert competence date to monthly period
    df_proc["data_competencia"] = pd.to_datetime(
        df_proc["data_competencia"], errors="coerce"
    ).dt.to_period("M")
    
    # Ensure df_proc is available for median analysis
    if 'df_proc' not in locals():
        df_proc = df.copy()
        df_proc["data_competencia"] = pd.to_datetime(
            df_proc["data_competencia"], errors="coerce"
        ).dt.to_period("M")
    
    result_df = aggregates["result_df"]
    trends = aggregates["trends"].copy()
    dist_cbo = aggregates["dist_cbo"]
    dist_cbo_sexo = aggregates["dist_cbo_sexo"]  # NEW: Get sex distribution
    dist_cbo_sexo_raca = aggregates["dist_cbo_sexo_raca"]  # Get sex and race distribution
    dist_cbo_total = aggregates["dist_cbo_total"]  # Get total distribution
    semaforo_counts = aggregates["semaforo_counts"]
    top_pos = aggregates["top_pos"]
    top_neg = aggregates["top_neg"]
    kpi_ratio_med_mean = aggregates["kpi_ratio_med_mean"]
    kpi_ratio_media_mean = aggregates["kpi_ratio_media_mean"]
    plan_df = aggregates["plan_df"]

    writer = pd.ExcelWriter(excel_path, engine="xlsxwriter")
    workbook = writer.book
    header_fmt = workbook.add_format({
        "bold": True,
        "bg_color": primary_color,
        "font_color": "white",
        "border": 1,
    })
    
    # Raw data
    df.to_excel(writer, sheet_name="Dados_Originais", index=False)
    data_sheet = writer.sheets["Dados_Originais"]
    for col_num, col_name in enumerate(df.columns):
        data_sheet.write(0, col_num, col_name, header_fmt)
    # Summary sheet
    result_df.to_excel(writer, sheet_name="razao_salarial_cbo", index=False)
    sheet_sum = writer.sheets["razao_salarial_cbo"]
    for col_num, col_name in enumerate(result_df.columns):
        sheet_sum.write(0, col_num, col_name, header_fmt)
    # Chart for ratios
    chart = workbook.add_chart({"type": "column"})
    ratio_med_col = result_df.columns.get_loc("razao_mediana_F_M")
    ratio_mean_col = result_df.columns.get_loc("razao_media_F_M")
    chart.add_series({
        "name": "Razão Mediana F/M",
        "categories": ["razao_salarial_cbo", 1, 1, len(result_df), 1],
        "values": ["razao_salarial_cbo", 1, ratio_med_col, len(result_df), ratio_med_col],
        "fill": {"color": primary_color},
    })
    chart.add_series({
        "name": "Razão Média F/M",
        "categories": ["razao_salarial_cbo", 1, 1, len(result_df), 1],
        "values": ["razao_salarial_cbo", 1, ratio_mean_col, len(result_df), ratio_mean_col],
        "fill": {"color": accent_color},
    })
    chart.set_title({"name": "Razões F/M por CBO"})
    chart.set_x_axis({"name": "CBO"})
    chart.set_y_axis({"name": "Razão F/M"})
    chart.set_legend({"position": "bottom"})
    sheet_sum.insert_chart("L2", chart, {"x_scale": 1.5, "y_scale": 1.5})
    # Trend sheet
    trends_loc = trends.copy()
    trends_loc["data_competencia"] = trends_loc["data_competencia"].astype(str)
    trends_loc.to_excel(writer, sheet_name="Evolucao_Mensal", index=False)
    sheet_tr = writer.sheets["Evolucao_Mensal"]
    for col_num, col_name in enumerate(trends_loc.columns):
        sheet_tr.write(0, col_num, col_name, header_fmt)
    chart2 = workbook.add_chart({"type": "line"})
    ratio_col = trends_loc.columns.get_loc("razao_F_M")
    chart2.add_series({
        "name": "Razão F/M",
        "categories": ["Evolucao_Mensal", 1, 0, len(trends_loc), 0],
        "values": ["Evolucao_Mensal", 1, ratio_col, len(trends_loc), ratio_col],
        "line": {"color": primary_color},
    })
    chart2.set_title({"name": "Tendência da Razão F/M (12m)"})
    chart2.set_x_axis({"name": "Mês"})
    chart2.set_y_axis({"name": "Razão F/M"})
    chart2.set_legend({"position": "bottom"})
    sheet_tr.insert_chart("E2", chart2, {"x_scale": 1.5, "y_scale": 1.5})
    # Distribution sheet with sex distribution
    dist_cbo.to_excel(writer, sheet_name="Distribuicao_por_Ocupacao", index=False)
    sheet_dist = writer.sheets["Distribuicao_por_Ocupacao"]
    # Apply header formatting to the first row
    for col_num, col_name in enumerate(dist_cbo.columns):
        sheet_dist.write(0, col_num, col_name, header_fmt)
    
    # Chart for overall distribution
    chart3 = workbook.add_chart({"type": "column"})
    total_col = dist_cbo.columns.get_loc("total_trabalhadores")
    chart3.add_series({
        "name": "Trabalhadores",
        "categories": ["Distribuicao_por_Ocupacao", 1, 1, len(dist_cbo), 1],
        "values": ["Distribuicao_por_Ocupacao", 1, total_col, len(dist_cbo), total_col],
        "fill": {"color": primary_color},
    })
    chart3.set_title({"name": "Distribuição de Trabalhadores por CBO"})
    chart3.set_x_axis({"name": "CBO"})
    chart3.set_y_axis({"name": "# Trabalhadores"})
    chart3.set_legend({"position": "bottom"})
    sheet_dist.insert_chart("H2", chart3, {"x_scale": 1.5, "y_scale": 1.5})
    
    # Chart for sex distribution by CBO
    chart4 = workbook.add_chart({"type": "column"})
    f_col = list(dist_cbo.columns).index("F") if "F" in dist_cbo.columns else -1
    m_col = list(dist_cbo.columns).index("M") if "M" in dist_cbo.columns else -1
    
    # Define colors for F and M (use user-selected colors with defaults)
    female_color = primary_color if primary_color != "#0F6CBD" else "#9966CC"  # Use primary_color or default purple
    male_color = accent_color if accent_color != "#585858" else "#FFD700"    # Use accent_color or default yellow
    
    if f_col >= 0:
        chart4.add_series({
            "name": "Mulheres",
            "categories": ["Distribuicao_por_Ocupacao", 1, 1, len(dist_cbo), 1],
            "values": ["Distribuicao_por_Ocupacao", 1, f_col, len(dist_cbo), f_col],
            "fill": {"color": female_color},
        })
    
    if m_col >= 0:
        chart4.add_series({
            "name": "Homens",
            "categories": ["Distribuicao_por_Ocupacao", 1, 1, len(dist_cbo), 1],
            "values": ["Distribuicao_por_Ocupacao", 1, m_col, len(dist_cbo), m_col],
            "fill": {"color": male_color},
        })
    
    chart4.set_title({"name": "Distribuição de Trabalhadores por CBO e Sexo"})
    chart4.set_x_axis({"name": "CBO"})
    chart4.set_y_axis({"name": "# Trabalhadores"})
    chart4.set_legend({"position": "bottom"})
    sheet_dist.insert_chart("H20", chart4, {"x_scale": 1.5, "y_scale": 1.5})
    
    # NEW: Distribution sheet with sex and race distribution
    dist_cbo_sexo_raca.to_excel(writer, sheet_name="Analise_Demografica", index=False)
    sheet_dist_sexo_raca = writer.sheets["Analise_Demografica"]
    # Apply header formatting to the first row
    for col_num, col_name in enumerate(dist_cbo_sexo_raca.columns):
        sheet_dist_sexo_raca.write(0, col_num, col_name, header_fmt)
    
    # Add totals by CBO
    start_row_totals = len(dist_cbo_sexo_raca) + 1
    current_total_row = start_row_totals
    
    # Calculate totals by CBO
    unique_cbos = dist_cbo_sexo_raca[['cbo_2002', 'cbo_titulo']].drop_duplicates()
    
    for _, cbo_row in unique_cbos.iterrows():
        cbo_codigo = cbo_row['cbo_2002']
        cbo_titulo = cbo_row['cbo_titulo']
        
        # Filter data for this CBO
        cbo_data = dist_cbo_sexo_raca[
            (dist_cbo_sexo_raca['cbo_2002'] == cbo_codigo) & 
            (dist_cbo_sexo_raca['cbo_titulo'] == cbo_titulo)
        ]
        
        # Calculate totals for this CBO
        total_funcionarios = cbo_data['contagem_trabalhadores'].sum()
        total_mulheres = cbo_data[cbo_data['sexo'] == 'F']['contagem_trabalhadores'].sum()
        total_homens = cbo_data[cbo_data['sexo'] == 'M']['contagem_trabalhadores'].sum()
        
        # Write CBO total
        sheet_dist_sexo_raca.write(current_total_row, 0, f"TOTAL CBO {cbo_codigo}", header_fmt)
        sheet_dist_sexo_raca.write(current_total_row, 1, cbo_titulo)
        sheet_dist_sexo_raca.write(current_total_row, 2, "TOTAL")
        sheet_dist_sexo_raca.write(current_total_row, 3, total_funcionarios)
        sheet_dist_sexo_raca.write(current_total_row, 4, f"Mulheres: {total_mulheres} | Homens: {total_homens}")
        current_total_row += 1
    
    # Add overall totals
    overall_total = dist_cbo_sexo_raca['contagem_trabalhadores'].sum()
    overall_mulheres = dist_cbo_sexo_raca[dist_cbo_sexo_raca['sexo'] == 'F']['contagem_trabalhadores'].sum()
    overall_homens = dist_cbo_sexo_raca[dist_cbo_sexo_raca['sexo'] == 'M']['contagem_trabalhadores'].sum()
    
    # Write overall totals
    sheet_dist_sexo_raca.write(current_total_row, 0, "TOTAL GERAL", header_fmt)
    sheet_dist_sexo_raca.write(current_total_row, 3, overall_total)
    sheet_dist_sexo_raca.write(current_total_row, 4, f"Mulheres: {overall_mulheres} | Homens: {overall_homens}")
    
    # Add totals by race
    current_total_row += 2
    sheet_dist_sexo_raca.write(current_total_row, 0, "TOTAL POR RAÇA/COR", header_fmt)
    current_total_row += 1
    
    race_totals = dist_cbo_sexo_raca.groupby('raca_cor')['contagem_trabalhadores'].sum()
    for race, total in race_totals.items():
        race_mulheres = dist_cbo_sexo_raca[
            (dist_cbo_sexo_raca['raca_cor'] == race) & 
            (dist_cbo_sexo_raca['sexo'] == 'F')
        ]['contagem_trabalhadores'].sum()
        race_homens = dist_cbo_sexo_raca[
            (dist_cbo_sexo_raca['raca_cor'] == race) & 
            (dist_cbo_sexo_raca['sexo'] == 'M')
        ]['contagem_trabalhadores'].sum()
        
        sheet_dist_sexo_raca.write(current_total_row, 0, race)
        sheet_dist_sexo_raca.write(current_total_row, 3, total)
        sheet_dist_sexo_raca.write(current_total_row, 4, f"Mulheres: {race_mulheres} | Homens: {race_homens}")
        current_total_row += 1
    
    # Create a pivot table for charting: CBO vs Raça/Cor with sex as series
    dist_cbo_raca_pivot = dist_cbo_sexo_raca.pivot_table(
        index=['cbo_2002', 'cbo_titulo'], 
        columns=['raca_cor'], 
        values='contagem_trabalhadores', 
        aggfunc='sum',
        fill_value=0
    ).reset_index()
    
    # Flatten column names if they are multi-level
    if isinstance(dist_cbo_raca_pivot.columns, pd.MultiIndex):
        dist_cbo_raca_pivot.columns = ['_'.join(map(str, col)).strip() for col in dist_cbo_raca_pivot.columns.values]
    
    # Write pivot table to the sheet for charting
    start_row_pivot = current_total_row + 3
    dist_cbo_raca_pivot.to_excel(writer, sheet_name="Analise_Demografica", index=False, startrow=start_row_pivot)
    
    # Add header for pivot table
    for col_num, col_name in enumerate(dist_cbo_raca_pivot.columns):
        sheet_dist_sexo_raca.write(start_row_pivot, col_num, col_name, header_fmt)
    
    # Create individual charts for each CBO with Race x Gender distribution
    # Create a new sheet for individual CBO charts
    chart_sheet_name = "Graficos_Detalhados_por_CBO"
    workbook.add_worksheet(chart_sheet_name)
    chart_sheet = workbook.get_worksheet_by_name(chart_sheet_name)
    
    # Write header for the charts sheet
    chart_sheet.write(0, 0, "Gráficos Detalhados por CBO - Distribuição Raça/Cor x Sexo", header_fmt)
    
    current_row = 2
    
    # Get unique CBOs
    unique_cbos = dist_cbo_sexo_raca[['cbo_2002', 'cbo_titulo']].drop_duplicates()
    
    for _, cbo_row in unique_cbos.iterrows():
        cbo_codigo = cbo_row['cbo_2002']
        cbo_titulo = cbo_row['cbo_titulo']
        
        # Filter data for this CBO
        cbo_data = dist_cbo_sexo_raca[
            (dist_cbo_sexo_raca['cbo_2002'] == cbo_codigo) & 
            (dist_cbo_sexo_raca['cbo_titulo'] == cbo_titulo)
        ]
        
        if len(cbo_data) > 0:  # Only create chart if there are values
            # Write CBO title
            chart_sheet.write(current_row, 0, f"CBO {cbo_codigo} - {cbo_titulo}", header_fmt)
            current_row += 1
            
            # Create pivot table for this CBO: Race x Gender
            cbo_pivot = cbo_data.pivot_table(
                index='raca_cor', 
                columns='sexo', 
                values='contagem_trabalhadores', 
                aggfunc='sum', 
                fill_value=0
            )
            
            # Write headers for the data table
            chart_sheet.write(current_row, 0, "Raça/Cor")
            chart_sheet.write(current_row, 1, "Mulheres (F)")
            chart_sheet.write(current_row, 2, "Homens (M)")
            chart_sheet.write(current_row, 3, "Total")
            current_row += 1
            
            # Write data for this CBO
            for race in cbo_pivot.index:
                f_count = cbo_pivot.loc[race, 'F'] if 'F' in cbo_pivot.columns else 0
                m_count = cbo_pivot.loc[race, 'M'] if 'M' in cbo_pivot.columns else 0
                total = f_count + m_count
                
                chart_sheet.write(current_row, 0, race)
                chart_sheet.write(current_row, 1, f_count)
                chart_sheet.write(current_row, 2, m_count)
                chart_sheet.write(current_row, 3, total)
                current_row += 1
            
            # Create grouped column chart for this specific CBO
            chart_cbo = workbook.add_chart({"type": "column"})
            
            # Add series for women
            if 'F' in cbo_pivot.columns:
                chart_cbo.add_series({
                    "name": "Mulheres (F)",
                    "categories": [chart_sheet_name, current_row - len(cbo_pivot.index), 0, current_row - 1, 0],
                    "values": [chart_sheet_name, current_row - len(cbo_pivot.index), 1, current_row - 1, 1],
                    "fill": {"color": primary_color if primary_color != "#0F6CBD" else "#9966CC"},  # Use user-selected color or default purple
                    "overlap": -10,
                    "gap": 20,
                })
            
            # Add series for men
            if 'M' in cbo_pivot.columns:
                chart_cbo.add_series({
                    "name": "Homens (M)",
                    "categories": [chart_sheet_name, current_row - len(cbo_pivot.index), 0, current_row - 1, 0],
                    "values": [chart_sheet_name, current_row - len(cbo_pivot.index), 2, current_row - 1, 2],
                    "fill": {"color": accent_color if accent_color != "#585858" else "#FFD700"},  # Use user-selected color or default yellow
                    "overlap": -10,
                    "gap": 20,
                })
            
            # Set chart properties
            chart_cbo.set_title({"name": f"Distribuição por Raça/Cor x Sexo - {cbo_titulo}"})
            chart_cbo.set_x_axis({"name": "Raça/Cor"})
            chart_cbo.set_y_axis({"name": "Número de Trabalhadores"})
            chart_cbo.set_legend({"position": "bottom"})
            
            # Insert chart
            chart_sheet.insert_chart(current_row, 5, chart_cbo, {"x_scale": 1.5, "y_scale": 1.2})
            
            current_row += 3  # Space for next chart
    
    # Create new sheet for median salary analysis by CBO with column charts
    median_sheet_name = "Analise_Mediana_Salarial_CBO"
    workbook.add_worksheet(median_sheet_name)
    median_sheet = workbook.get_worksheet_by_name(median_sheet_name)
    
    # Write header for the median analysis sheet
    median_sheet.write(0, 0, "Análise da Mediana Salarial por CBO - Homens vs Mulheres", header_fmt)
    
    # Ensure df_proc is available for median analysis
    if 'df_proc' not in locals():
        df_proc = df.copy()
        df_proc["data_competencia"] = pd.to_datetime(
            df_proc["data_competencia"], errors="coerce"
        ).dt.to_period("M")
    
    # Prepare data for median analysis
    chart_start_row = 3
    current_row = chart_start_row
    
    for cbo_codigo, cbo_titulo in zip(result_df["cbo_2002"], result_df["cbo_titulo"]):
        # Filter data for this CBO
        cbo_df = df_proc[
            (df_proc["cbo_2002"] == cbo_codigo) & 
            (df_proc["cbo_titulo"] == cbo_titulo)
        ]
        
        if len(cbo_df) > 0:
            # Write CBO title
            median_sheet.write(current_row, 0, f"CBO {cbo_codigo} - {cbo_titulo}", header_fmt)
            current_row += 1
            
            # Calculate statistics by gender
            female_data = cbo_df[cbo_df["sexo"] == "F"]["salario_contratual_mensal"].dropna()
            male_data = cbo_df[cbo_df["sexo"] == "M"]["salario_contratual_mensal"].dropna()
            
            # Write summary statistics data
            data_row = current_row
            median_sheet.write(data_row, 0, "Gênero", header_fmt)
            median_sheet.write(data_row, 1, "Mediana", header_fmt)
            median_sheet.write(data_row, 2, "Média", header_fmt)
            median_sheet.write(data_row, 3, "Q1", header_fmt)
            median_sheet.write(data_row, 4, "Q3", header_fmt)
            median_sheet.write(data_row, 5, "Contagem", header_fmt)
            
            # Women statistics
            if len(female_data) > 0:
                female_median = female_data.median()
                female_mean = female_data.mean()
                female_q1 = female_data.quantile(0.25)
                female_q3 = female_data.quantile(0.75)
                female_count = len(female_data)
                
                median_sheet.write(data_row + 1, 0, "Mulheres")
                median_sheet.write(data_row + 1, 1, female_median)
                median_sheet.write(data_row + 1, 2, female_mean)
                median_sheet.write(data_row + 1, 3, female_q1)
                median_sheet.write(data_row + 1, 4, female_q3)
                median_sheet.write(data_row + 1, 5, female_count)
            
            # Men statistics
            if len(male_data) > 0:
                male_median = male_data.median()
                male_mean = male_data.mean()
                male_q1 = male_data.quantile(0.25)
                male_q3 = male_data.quantile(0.75)
                male_count = len(male_data)
                
                median_sheet.write(data_row + 2, 0, "Homens")
                median_sheet.write(data_row + 2, 1, male_median)
                median_sheet.write(data_row + 2, 2, male_mean)
                median_sheet.write(data_row + 2, 3, male_q1)
                median_sheet.write(data_row + 2, 4, male_q3)
                median_sheet.write(data_row + 2, 5, male_count)
            
            # Create column chart showing medians with quartile ranges
            chart_median = workbook.add_chart({"type": "column"})
            
            # Define colors using user-selected colors with defaults
            female_color = primary_color if primary_color != "#0F6CBD" else "#9966CC"  # Use primary_color or default purple
            male_color = accent_color if accent_color != "#585858" else "#FFD700"    # Use accent_color or default yellow
            
            # Add series for women median
            if len(female_data) > 0:
                chart_median.add_series({
                    "name": f"Mulheres (Mediana: R$ {female_median:,.2f})",
                    "categories": [median_sheet_name, data_row + 1, 0, data_row + 1, 0],
                    "values": [median_sheet_name, data_row + 1, 1, data_row + 1, 1],
                    "fill": {"color": female_color},
                    "error_bars": {
                        "type": "custom",
                        "plus_values": [female_q3 - female_median],
                        "minus_values": [female_median - female_q1],
                        "line_color": "#333333",
                        "line_width": 2,
                    },
                })
            
            # Add series for men median
            if len(male_data) > 0:
                chart_median.add_series({
                    "name": f"Homens (Mediana: R$ {male_median:,.2f})",
                    "categories": [median_sheet_name, data_row + 2, 0, data_row + 2, 0],
                    "values": [median_sheet_name, data_row + 2, 1, data_row + 2, 1],
                    "fill": {"color": male_color},
                    "error_bars": {
                        "type": "custom",
                        "plus_values": [male_q3 - male_median],
                        "minus_values": [male_median - male_q1],
                        "line_color": "#333333",
                        "line_width": 2,
                    },
                })
            
            # Set chart properties
            chart_median.set_title({"name": f"Mediana Salarial com Intervalo Interquartil - {cbo_titulo}"})
            chart_median.set_x_axis({"name": "Gênero"})
            chart_median.set_y_axis({"name": "Salário Contratual Mensal (R$)"})
            chart_median.set_legend({"position": "bottom"})
            
            # Insert chart
            median_sheet.insert_chart(data_row, 7, chart_median, {"x_scale": 1.8, "y_scale": 1.5})
            
            # Move to next position
            current_row = data_row + 8  # Space for next chart
    
    # Save workbook
    writer.close()


def generate_reports(
    df: pd.DataFrame,
    tmpdir: str,
    company_name: str,
    k_min: int = 5,
    primary_color: str = "#0F6CBD",
    accent_color: str = "#585858",
    generate_docx: bool = False,
) -> Dict[str, str]:
    """Generate Excel report in a temporary directory.

    Parameters
    ----------
    df : DataFrame
        Data to process.
    tmpdir : str
        Directory where the output files will be written.
    company_name : str
        Name of the company, used in the Excel.
    k_min : int
        Minimum group size for k‑anonymity.
    primary_color : str
        Primary colour for charts and headers.
    accent_color : str
        Secondary colour for charts and headers.
    generate_docx : bool
        Parameter kept for compatibility but ignored.

    Returns
    -------
    dict
        Mapping with key 'excel' pointing to the generated file path.
    """
    aggregates = process_data(df, k_min=k_min)
    excel_path = os.path.join(tmpdir, "relatorio.xlsx")
    create_excel(df, aggregates, excel_path, primary_color=primary_color, accent_color=accent_color)
    outputs = {"excel": excel_path}
    return outputs


def create_zip_bundle(files: Dict[str, str], zip_path: str) -> None:
    """Create a zip bundle containing the provided files.

    Parameters
    ----------
    files : dict
        Mapping of keys to file paths. The key will be used as the name inside
        the zip if not the actual file name.
    zip_path : str
        Path to the resulting zip file.
    """
    print(f"Creating zip bundle at: {zip_path}")
    print(f"Files to include: {files}")
    
    # Ensure the directory for the zip file exists
    os.makedirs(os.path.dirname(zip_path), exist_ok=True)
    
    # Check if all files exist before creating the zip
    missing_files = []
    for name, path in files.items():
        if not os.path.exists(path):
            missing_files.append((name, path))
            print(f"Warning: File {path} does not exist")
        else:
            print(f"File {path} exists")
    
    if missing_files:
        print(f"Missing files: {missing_files}")
        # We'll still create the zip with the files that exist
    
    with zipfile.ZipFile(zip_path, "w") as zf:
        for name, path in files.items():
            # Check if the file exists before trying to add it
            if os.path.exists(path):
                # Use the key as the base name and preserve the original file extension
                arcname = f"{name}{os.path.splitext(path)[1]}"
                print(f"Adding {path} as {arcname} to zip")
                zf.write(path, arcname=arcname)
            else:
                # Log a warning if the file doesn't exist
                print(f"Warning: File {path} does not exist and will not be added to the zip bundle.")
    
    # Verify that the zip file was created
    if not os.path.exists(zip_path):
        raise FileNotFoundError(f"ZIP file was not created: {zip_path}")
    else:
        print(f"ZIP file created successfully: {zip_path}")
        # Check the contents of the zip file
        with zipfile.ZipFile(zip_path, "r") as zf:
            print(f"ZIP contents: {zf.namelist()}")
