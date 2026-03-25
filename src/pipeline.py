import time
from pathlib import Path

import duckdb
from loguru import logger

from src.utils import build_dim_calendario


class Paths:
    """Clase para centralizar las rutas de archivos usados en el pipeline, facilitando su gestión y mantenimiento."""

    BASE_DIR = Path(__file__).resolve().parent.parent
    LOG_FILE = BASE_DIR / "logs/app.log"
    CCICO_RAW = BASE_DIR / "data/raw/informacion_mensual_ccico.csv"
    AFILIADOS_RAW = BASE_DIR / "data/raw/caracteristicas_afiliados.csv"
    CCICO_CURATED = BASE_DIR / "data/curated/ccico.parquet"
    AFILIADOS_CURATED = BASE_DIR / "data/curated/afiliados.parquet"
    CALENDARIO = BASE_DIR / "data/curated/calendario.parquet"
    DATASET_ANALYTIC = BASE_DIR / "data/processed/dataset_analitico.parquet"


# Configurar loguru para mostrar mensajes en consola y escribirlos en un archivo de log
logger.add(
    str(Paths.LOG_FILE),
    rotation="10 MB",
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
)


def run_pipeline():
    """Función principal para ejecutar el pipeline de procesamiento de datos de pensiones chilenas."""
    start_time = time.perf_counter()
    try:
        logger.info("Iniciando pipeline de procesamiento de datos de pensiones chilenas.")
        con = duckdb.connect(database=":memory:")
        validate_inputs()
        build_ccico(con)
        build_afiliados(con)
        fecha_min, fecha_max = build_dataset_analitico(con)
        build_calendario(fecha_min, fecha_max)
        con.close()
        logger.info("Pipeline completado exitosamente.")
    finally:
        elapsed_time = time.perf_counter() - start_time
        logger.info(f"Tiempo total del proceso: {elapsed_time:.2f} segundos.\n")


def validate_inputs():
    """Función para validar la existencia de los archivos de entrada antes de ejecutar el pipeline."""
    logger.info("Validando archivos de entrada...")
    for path in [Paths.CCICO_RAW, Paths.AFILIADOS_RAW]:
        if not path.exists():
            logger.error(f"Archivo no encontrado: {path}")
            raise FileNotFoundError(f"Archivo no encontrado: {path}")


def build_ccico(con: duckdb.DuckDBPyConnection):
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
        FROM read_csv_auto('{str(Paths.CCICO_RAW)}')
        WHERE rem_imp IS NOT NULL AND rem_imp::INTEGER > 0
        ORDER BY id_afiliado, f_cotizacion
        """

    ccico = con.sql(query)
    ccico.to_parquet(str(Paths.CCICO_CURATED))
    logger.info("Archivo CCICO transformado y guardado en formato parquet.")


def build_afiliados(con: duckdb.DuckDBPyConnection):
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
            FROM read_csv_auto('{str(Paths.AFILIADOS_RAW)}')
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
    afiliados.to_parquet(str(Paths.AFILIADOS_CURATED))
    logger.info("Archivo Afiliados transformado y guardado en formato parquet.")


def build_dataset_analitico(con: duckdb.DuckDBPyConnection):
    """Se construye un dataset analítico uniendo afiliados y cotizaciones (CCICO)."""

    query = f"""
    SELECT
        a.*,
        c.f_cotizacion,
        c.afp,
        c.remuneracion
    FROM read_parquet('{str(Paths.AFILIADOS_CURATED)}') a
    LEFT JOIN read_parquet('{str(Paths.CCICO_CURATED)}') c
        ON a.id_afiliado = c.id_afiliado
    """

    analitico = con.sql(query)
    analitico.to_parquet(str(Paths.DATASET_ANALYTIC))
    logger.info("Dataset analítico construido y guardado en formato parquet.")

    # Obtener la fecha mínima y máxima de cotización para construir calendario
    rangos = (
        analitico.aggregate("""MIN(CAST(f_cotizacion AS DATE))::VARCHAR AS fecha_min,
                  MAX(CAST(f_cotizacion AS DATE))::VARCHAR AS fecha_max""")
        .to_df()
        .iloc[0]
    )
    fecha_min = rangos["fecha_min"]
    fecha_max = rangos["fecha_max"]
    return fecha_min, fecha_max


def build_calendario(fecha_min, fecha_max):
    """Construye una tabla de fechas (DimCalendario) y la guarda en formato parquet."""
    df_calendario = build_dim_calendario(fecha_min, fecha_max)
    df_calendario.to_parquet(Paths.CALENDARIO)
    logger.info("Tabla de calendario construida y guardada en formato parquet.")
