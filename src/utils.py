import pandas as pd

# Diccionarios para mapear números a nombres de meses y días en español
MESES = {
    1: "Enero",
    2: "Febrero",
    3: "Marzo",
    4: "Abril",
    5: "Mayo",
    6: "Junio",
    7: "Julio",
    8: "Agosto",
    9: "Septiembre",
    10: "Octubre",
    11: "Noviembre",
    12: "Diciembre",
}

DIAS = {
    0: "Lunes",
    1: "Martes",
    2: "Miércoles",
    3: "Jueves",
    4: "Viernes",
    5: "Sábado",
    6: "Domingo",
}


def build_dim_calendario(start_date: str, end_date: str):
    """
    Construye un dataframe de tabla de fechas (DimCalendario).

    Args:
        start_date (str): Fecha inicio (YYYY-MM-DD)
        end_date (str): Fecha fin (YYYY-MM-DD)
    Returns:
        pd.DataFrame: DataFrame con la tabla de calendario."""

    fechas = pd.date_range(start=start_date, end=end_date, freq="D")
    df = pd.DataFrame({"fecha": fechas})
    df["fecha_key"] = df["fecha"].dt.strftime("%Y%m%d").astype(int)
    df["anio"] = df["fecha"].dt.year
    df["mes"] = df["fecha"].dt.month
    df["dia"] = df["fecha"].dt.day
    df["mes_anio"] = df["anio"] * 100 + df["mes"]
    df["nombre_mes"] = df["mes"].map(MESES)
    df["nombre_dia"] = df["fecha"].dt.weekday.map(DIAS)
    df["trimestre"] = df["fecha"].dt.quarter
    df["es_fin_de_semana"] = (df["fecha"].dt.weekday >= 5).astype(int)
    df = df.sort_values("fecha")
    return df


def see_data(df, name="DataFrame"):
    """Función para mostrar información básica de un DataFrame. (Solo para debugging)"""
    print(f"\n{name} - FILAS/COLUMNAS: {df.shape}")
    print(f"\n{name} - FILAS DUPLICADAS: {df.duplicated().sum().item()}")
    print(f"\n{name} - TIPOS DE DATOS:")
    print(df.dtypes)
    print(f"\n{name} - CONTEO DE NULOS:")
    print(df.isnull().sum().sort_values(ascending=False))
    print(f"\n{name} - HEAD:")
    print(df.head())
    print("\n" + "=" * 50 + "\n")
