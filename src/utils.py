def see_data(df, name="DataFrame"):
    """Función para mostrar información básica de un DataFrame."""
    print(f"\n{name} - FILAS/COLUMNAS: {df.shape}")
    print(f"\n{name} - FILAS DUPLICADAS: {df.duplicated().sum().item()}")
    print(f"\n{name} - TIPOS DE DATOS:")
    print(df.dtypes)
    print(f"\n{name} - CONTEO DE NULOS:")
    print(df.isnull().sum().sort_values(ascending=False))
    print(f"\n{name} - HEAD:")
    print(df.head())
    print("\n" + "=" * 50 + "\n")
