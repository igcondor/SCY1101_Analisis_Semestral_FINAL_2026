import pandas as pd


def load_defunciones(path="defunciones-ocurridas-y-registradas-en-la-republica-argentina-entre-los-anos-2005-2022.csv"):
    # 1. Cargamos el dataset indicando que la columna de muerte materna es de tipo texto (object/str)
    df1 = pd.read_csv(
        path, dtype={'muerte_materna_id': str}
        )
    return df1
