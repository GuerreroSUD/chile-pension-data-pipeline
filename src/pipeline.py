from pathlib import Path

import duckdb

from src.utils import see_data


class Ruta:
    BASE_DIR = Path(__file__).resolve().parent.parent
    CCICO_RAW = "data/raw/informacion_mensual_ccico.csv"
    AFILIADOS_RAW = "data/raw/caracteristicas_afiliados.csv"
    CCICO_CURATED = "data/curated/ccico.parquet"
    AFILIADOS_CURATED = "data/curated/afiliados.parquet"
    DATASET_ANALYTIC = "data/processed/dataset_analitico.parquet"


def run_pipeline():
    con = duckdb.connect()
    # validate_inputs()
    df_ccico = build_ccico(con, Ruta.CCICO_RAW, Ruta.CCICO_CURATED)
    df_afiliados = build_afiliados(con, Ruta.AFILIADOS_RAW, Ruta.AFILIADOS_CURATED)
    con.close()

    # Código de prueba para ver los DataFrames resultantes y verificar que se hayan
    #  transformado correctamente
    see_data(df_ccico, "CCICO")
    see_data(df_afiliados, "Afiliados")


def build_ccico(con: duckdb.DuckDBPyConnection, ccico_raw: Path, ccico_curated: Path):
    """Definir y ejecutar una consulta SQL para CCICO transformando los datos según sea necesario.

    Explicación de la Consulta:
    - Se usa DISTINCT debido a duplicados detectados en el dataset original.
    - correl se castea a INTEGER porque el CSV lo trae como string.
    - rem_imp se castea a INTEGER porque el CSV lo trae como string.
    - Se mapea el código de afp a su nombre completo para mayor claridad.
    - No se incluye ELSE en CASE de afp, ya que valores fueron validados previamente.
    - Se filtran remuneraciones <= 0 y nulas por no ser relevantes para análisis.
    - Se ordena por id_afiliado y fecha de cotización para facilitar análisis temporal."""

    query = f"""--sql
        SELECT DISTINCT
            correl::INTEGER AS id_afiliado
            ,strptime(agno || '-' || mes || '-01', '%Y-%m-%d') as f_cotizacion
            ,CASE afp
                WHEN 'cup' THEN 'CUPRUM'
                WHEN 'prv' THEN 'PROVIDA'
                WHEN 'hab' THEN 'HABITAT'
                WHEN 'cap' THEN 'CAPITAL'
                WHEN 'pli' THEN 'PLANVITAL'
                WHEN 'mod' THEN 'MODELO'
                WHEN 'uno' THEN 'UNO'
            END as afp
            ,rem_imp::INTEGER AS remuneracion
        FROM read_csv_auto('{str(ccico_raw)}')
        WHERE rem_imp IS NOT NULL AND rem_imp::INTEGER > 0
        ORDER BY id_afiliado, f_cotizacion
        """

    ccico = con.sql(query)
    ccico.to_parquet(str(ccico_curated))

    return ccico.to_df()


def build_afiliados(con: duckdb.DuckDBPyConnection, afiliados_raw: Path, afiliados_curated: Path):
    """Definir y ejecutar una consulta SQL para Afiliados transformando los datos según sea necesario.

    Explicación de la Consulta:
    - No es neccesario usar DISTINCT debido a que no se detectaron duplicados en el dataset original.
    - correl se castea a INTEGER porque el CSV lo trae como string.
    - Se mapea el código de nacionalidad para mayor claridad.
    - Se mapea el código de región a sus nombres completos para mayor claridad.
    - Se incluye ELSE en CASE de regiion, ya que existían valores nulos.
    - Se formatean campos de fecha de nacimiento y fallecimiento a formato fecha.
    - Se calcula el saldo total sumando los saldos de los distintos fondos, considerando nulos como 0.
    - Se filtran fechas de nacimiento nulas por que podrían ser registros incompletos o erróneos.
    - Se filtran registros que indican que el afiliado estaría vivo con una edad mayor a 110 años por ser poco probables.
    - Se ordena por id_afiliado para facilitar análisis temporal."""

    query = f"""--sql
        WITH afiliados_clean AS (
            SELECT
                correl::INTEGER AS id_afiliado,
                sexo,
                CASE nac
                    WHEN 'C' THEN 'chilena'
                    WHEN 'E' THEN 'extranjera'
                END AS nacionalidad,
                CASE region
                    WHEN '01' THEN 'Tarapacá'
                    WHEN '02' THEN 'Antofagasta'
                    WHEN '03' THEN 'Atacama'
                    WHEN '04' THEN 'Coquimbo'
                    WHEN '05' THEN 'Valparaíso'
                    WHEN '06' THEN 'O''Higgins'
                    WHEN '07' THEN 'Maule'
                    WHEN '08' THEN 'Biobío'
                    WHEN '09' THEN 'La Araucanía'
                    WHEN '10' THEN 'Los Lagos'
                    WHEN '11' THEN 'Aysén'
                    WHEN '12' THEN 'Magallanes'
                    WHEN '13' THEN 'Metropolitana'
                    WHEN '14' THEN 'Los Ríos'
                    WHEN '15' THEN 'Arica y Parinacota'
                    WHEN '16' THEN 'Ñuble'
                    ELSE 'Desconocida'
                END AS region,
                strptime(fecha_nac || '01', '%Y%m%d') AS f_nacimiento,
                try_strptime(fecha_fall || '01', '%Y%m%d') AS f_fallecimiento,
                afp AS afp_actual,
                (
                    COALESCE(saldoA_pesos::INTEGER, 0) +
                    COALESCE(saldoB_pesos::INTEGER, 0) +
                    COALESCE(saldoC_pesos::INTEGER, 0) +
                    COALESCE(saldoD_pesos::INTEGER, 0) +
                    COALESCE(saldoE_pesos::INTEGER, 0)
                ) AS saldo_pesos
            FROM read_csv_auto('{str(afiliados_raw)}')
            WHERE fecha_nac IS NOT NULL
        )

        SELECT *
        FROM afiliados_clean
        WHERE NOT (
            f_fallecimiento IS NULL
            AND DATE_DIFF('year', f_nacimiento, CURRENT_DATE) > 110
        )
        ORDER BY id_afiliado
        """

    afiliados = con.sql(query)
    afiliados.to_parquet(str(afiliados_curated))

    return afiliados.to_df()
