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
    df.to_excel(writer, sheet_name="Dados_Sinteticos", index=False)
    data_sheet = writer.sheets["Dados_Sinteticos"]
    for col_num, col_name in enumerate(df.columns):
        data_sheet.write(0, col_num, col_name, header_fmt)
    # Summary sheet
    result_df.to_excel(writer, sheet_name="Resumo_CBO_Sexo", index=False)
    sheet_sum = writer.sheets["Resumo_CBO_Sexo"]
    for col_num, col_name in enumerate(result_df.columns):
        sheet_sum.write(0, col_num, col_name, header_fmt)
    # Chart for ratios
    chart = workbook.add_chart({"type": "column"})
    ratio_med_col = result_df.columns.get_loc("razao_mediana_F_M")
    ratio_mean_col = result_df.columns.get_loc("razao_media_F_M")
    chart.add_series({
        "name": "Razão Mediana F/M",
        "categories": ["Resumo_CBO_Sexo", 1, 1, len(result_df), 1],
        "values": ["Resumo_CBO_Sexo", 1, ratio_med_col, len(result_df), ratio_med_col],
        "fill": {"color": primary_color},
    })
    chart.add_series({
        "name": "Razão Média F/M",
        "categories": ["Resumo_CBO_Sexo", 1, 1, len(result_df), 1],
        "values": ["Resumo_CBO_Sexo", 1, ratio_mean_col, len(result_df), ratio_mean_col],
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
    trends_loc.to_excel(writer, sheet_name="Tendencias_12m", index=False)
    sheet_tr = writer.sheets["Tendencias_12m"]
    for col_num, col_name in enumerate(trends_loc.columns):
        sheet_tr.write(0, col_num, col_name, header_fmt)
    chart2 = workbook.add_chart({"type": "line"})
    ratio_col = trends_loc.columns.get_loc("razao_F_M")
    chart2.add_series({
        "name": "Razão F/M",
        "categories": ["Tendencias_12m", 1, 0, len(trends_loc), 0],
        "values": ["Tendencias_12m", 1, ratio_col, len(trends_loc), ratio_col],
        "line": {"color": primary_color},
    })
    chart2.set_title({"name": "Tendência da Razão F/M (12m)"})
    chart2.set_x_axis({"name": "Mês"})
    chart2.set_y_axis({"name": "Razão F/M"})
    chart2.set_legend({"position": "bottom"})
    sheet_tr.insert_chart("E2", chart2, {"x_scale": 1.5, "y_scale": 1.5})
    # Distribution sheet with sex distribution
    dist_cbo.to_excel(writer, sheet_name="Distribuicao_CBO", index=False)
    sheet_dist = writer.sheets["Distribuicao_CBO"]
    # Apply header formatting to the first row
    for col_num, col_name in enumerate(dist_cbo.columns):
        sheet_dist.write(0, col_num, col_name, header_fmt)
    
    # Chart for overall distribution
    chart3 = workbook.add_chart({"type": "column"})
    total_col = dist_cbo.columns.get_loc("total_trabalhadores")
    chart3.add_series({
        "name": "Trabalhadores",
        "categories": ["Distribuicao_CBO", 1, 1, len(dist_cbo), 1],
        "values": ["Distribuicao_CBO", 1, total_col, len(dist_cbo), total_col],
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
    
    # Define colors for F and M (Purple for F, Yellow for M)
    female_color = "#9966CC"  # Purple
    male_color = "#FFD700"    # Yellow
    
    if f_col >= 0:
        chart4.add_series({
            "name": "Mulheres",
            "categories": ["Distribuicao_CBO", 1, 1, len(dist_cbo), 1],
            "values": ["Distribuicao_CBO", 1, f_col, len(dist_cbo), f_col],
            "fill": {"color": female_color},
        })
    
    if m_col >= 0:
        chart4.add_series({
            "name": "Homens",
            "categories": ["Distribuicao_CBO", 1, 1, len(dist_cbo), 1],
            "values": ["Distribuicao_CBO", 1, m_col, len(dist_cbo), m_col],
            "fill": {"color": male_color},
        })
    
    chart4.set_title({"name": "Distribuição de Trabalhadores por CBO e Sexo"})
    chart4.set_x_axis({"name": "CBO"})
    chart4.set_y_axis({"name": "# Trabalhadores"})
    chart4.set_legend({"position": "bottom"})
    sheet_dist.insert_chart("H20", chart4, {"x_scale": 1.5, "y_scale": 1.5})
    
    # NEW: Distribution sheet with sex and race distribution
    dist_cbo_sexo_raca.to_excel(writer, sheet_name="Distribuicao_CBO_Sexo_Raca", index=False)
    sheet_dist_sexo_raca = writer.sheets["Distribuicao_CBO_Sexo_Raca"]
    # Apply header formatting to the first row
    for col_num, col_name in enumerate(dist_cbo_sexo_raca.columns):
        sheet_dist_sexo_raca.write(0, col_num, col_name, header_fmt)
    
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
    start_row_pivot = len(dist_cbo_sexo_raca) + 3
    dist_cbo_raca_pivot.to_excel(writer, sheet_name="Distribuicao_CBO_Sexo_Raca", index=False, startrow=start_row_pivot)
    
    # Add header for pivot table
    for col_num, col_name in enumerate(dist_cbo_raca_pivot.columns):
        sheet_dist_sexo_raca.write(start_row_pivot, col_num, col_name, header_fmt)
    
    # Create chart for CBO vs Raça/Cor distribution
    chart_raca = workbook.add_chart({"type": "column", "subtype": "stacked"})
    
    # Add series for each race/color category (skip first two columns: cbo_2002 and cbo_titulo)
    for i, col_name in enumerate(dist_cbo_raca_pivot.columns[2:], start=2):  # Start from index 2 to skip cbo_2002 and cbo_titulo
        if dist_cbo_raca_pivot[col_name].sum() > 0:  # Only add series if there are values
            chart_raca.add_series({
                "name": col_name,
                "categories": ["Distribuicao_CBO_Sexo_Raca", start_row_pivot+1, 1, start_row_pivot+len(dist_cbo_raca_pivot), 1],  # CBO titles
                "values": ["Distribuicao_CBO_Sexo_Raca", start_row_pivot+1, i, start_row_pivot+len(dist_cbo_raca_pivot), i],
            })
    
    chart_raca.set_title({"name": "Distribuição de Trabalhadores por CBO e Raça/Cor"})
    chart_raca.set_x_axis({"name": "CBO"})
    chart_raca.set_y_axis({"name": "Número de Trabalhadores"})
    chart_raca.set_legend({"position": "bottom"})
    sheet_dist_sexo_raca.insert_chart("A{}".format(start_row_pivot + len(dist_cbo_raca_pivot) + 3), chart_raca, {"x_scale": 2, "y_scale": 1.5})
    
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
