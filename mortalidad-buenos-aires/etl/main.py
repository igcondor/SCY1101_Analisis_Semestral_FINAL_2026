from etl.extract.load_data import load_defunciones
from etl.transform.cleaning import (
    drop_muerte_materna,
    normalizar_cie10_upper,
    mapear_cie10_faltantes,
    eliminar_jurisdiccion_nula,
    eliminar_sexo_desconocido,
    eliminar_edad_sin_especificar,
    limpiar_etiqueta_grupo_edad,
    filtrar_buenos_aires,
)
from etl.transform.feature_engineering import (
    clasificar_cie10,
    transformacion_manual,
    transformacion_pipeline,
)


def run(csv_path="data/raw/defunciones-ocurridas-y-registradas-en-la-republica-argentina-entre-los-anos-2005-2022.csv"):
    df1 = load_defunciones(csv_path)
    df = drop_muerte_materna(df1)
    df = normalizar_cie10_upper(df)
    df = mapear_cie10_faltantes(df)
    df = eliminar_jurisdiccion_nula(df)
    df = eliminar_sexo_desconocido(df)
    df = eliminar_edad_sin_especificar(df)
    df = limpiar_etiqueta_grupo_edad(df)
    df = filtrar_buenos_aires(df)
    df["supracategoria"] = df["cie10_causa_id"].apply(clasificar_cie10)
    return df


if __name__ == "__main__":
    df = run()
    print(df.shape)
    print(df.head())
