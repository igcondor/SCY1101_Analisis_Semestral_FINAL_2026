def drop_muerte_materna(df1):
    df = df1.drop(columns=["muerte_materna_id", "muerte_materna_clasificacion"]).copy()
    # Recuerden usar ese df, ya que df1, tiene muerte_materna_id y muerte_materna_clasificacion,
    # que no nos sirven porque son casi 100% nulos
    # De aqui en adelante df, sera el df normal a usar, con las columnas ya eliminadas
    return df


def normalizar_cie10_upper(df):
    df['cie10_causa_id'] = df['cie10_causa_id'].str.upper()
    return df


def mapear_cie10_faltantes(df):
    map_cie10 = {
        "I84": "Hemorroides",
        "R97": "Hallazgos anormales de marcadores tumorales",
        "U07": "COVID-19",
        "U10": "Síndrome inflamatorio multisistémico asociado con COVID-19",
        "U12": "Evento adverso posterior a inmunización contra COVID-19",
        "P28": "Otros problemas respiratorios del recién nacido, originados en el período perinatal",
        'W74' : 'Ahogamiento y sumersión no especificados',
        'K74' : 'Fibrosis y cirrosis del hígado',
        'K74' : 'Fibrosis y cirrosis del hígado',
        'K74' : 'Fibrosis y cirrosis del hígado',
        'J18' : 'Neumonía, organismo no especificado',
        'I50' : 'Insuficiencia cardíaca',
        'K80' : 'Colelitiasis',
        'B99' : 'Otras enfermedades infecciosas y las no especificadas',
        'C18' : 'Tumor maligno del colon',
        'N18' : 'Enfermedad renal crónica',
        'K83' : 'Otras enfermedades de las vías biliares',
    }

    df["cie10_clasificacion"] = (
        df["cie10_clasificacion"]
          .fillna(df["cie10_causa_id"].map(map_cie10))
    )
    return df


def eliminar_jurisdiccion_nula(df):
    df = df.dropna(subset=['jurisdicion_residencia_nombre'])
    return df


def eliminar_sexo_desconocido(df):
    # Se eliminan para evitar errores al hacer futuros analisis con genero
    df = df[df['Sexo'] != "desconocido"]
    return df


def eliminar_edad_sin_especificar(df):
    # Se eliminan las filas con valor desconocido
    df = df[df['grupo_edad'] != "06.Sin especificar"]
    return df


def limpiar_etiqueta_grupo_edad(df):
    df['grupo_edad'] = df['grupo_edad'].str.replace('  ', ' ', regex=False)
    df['grupo_edad'] = df['grupo_edad'].str[3:]
    return df


def filtrar_buenos_aires(df):
    df = df[df["jurisdicion_residencia_nombre"] == "Buenos Aires"]
    return df
