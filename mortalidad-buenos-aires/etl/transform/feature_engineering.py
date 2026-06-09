from sklearn.preprocessing import MinMaxScaler, StandardScaler, LabelEncoder, OneHotEncoder, OrdinalEncoder
from sklearn.compose import ColumnTransformer


def clasificar_cie10(codigo):
  """Clasifica un código CIE-10 en su capítulo oficial según la OMS."""
  if not isinstance(codigo, str) or len(codigo) < 1:
    return "Desconocido"
  letra = codigo[0]
  # Caso especial D: distinguir por número
  if letra == "D":
    try:
      num = int(codigo[1:3])
      return "Neoplasias" if num <= 48 else "Sangre e inmunidad"
    except:
      return "Desconocido"

  if letra == "H":
    try:
      num = int(codigo[1:3])
      return "Enfermedades del ojo" if num <= 59 else "Enfermedades del oído"
    except:
      return "Desconocido"
  mapa = {
    "A": "Infecciosas y parasitarias",
    "B": "Infecciosas y parasitarias",
    "C": "Neoplasias",
    "E": "Endocrinas y metabólicas",
    "F": "Trastornos mentales",
    "G": "Sistema nervioso",
    "H": "Ojo / Oído",    # H00-H95 cubre ambos
    "I": "Aparato circulatorio",
    "J": "Aparato respiratorio",
    "K": "Aparato digestivo",
    "L": "Piel y tejido subcutáneo",
    "M": "Osteomuscular",
    "N": "Aparato genitourinario",
    "O": "Embarazo y parto",
    "P": "Afecciones perinatales",
    "Q": "Malformaciones congénitas",
    "R": "Síntomas y signos inespecíficos",
    "S": "Traumatismos y envenenamientos",
    "T": "Traumatismos y envenenamientos",
    "V": "Causas externas",
    "W": "Causas externas",
    "X": "Causas externas",
    "Y": "Causas externas",
    "Z": "Factores de salud",
    "U": "Códigos especiales",
  }
  return mapa.get(letra, "Desconocido")


def transformacion_manual(df):
    df_manual = df.copy()

    ordenEdad = ['De a 0 a 14 anios','De 15 a 34 anios',
                'De 35 a 54 anios','De 55 a 74 anios',
                'De 75 anios y mas']

    le = LabelEncoder()
    df_manual['cie10_clasificacion'] = le.fit_transform(df_manual['cie10_clasificacion'])
    df_manual['Sexo'] = le.fit_transform(df_manual['Sexo'])

    # Se usa OrdinalEncoder para establecerle un orden a las variables ordinales

    ordEdad = OrdinalEncoder(categories=[ordenEdad])
    df_manual['grupo_edad'] = ordEdad.fit_transform(df_manual[['grupo_edad']])


    mm_scaler = MinMaxScaler()
    df_manual['anio'] = mm_scaler.fit_transform(df_manual[['anio']]) # No hace falta timestamp ya que esta solo el año, sin mes ni dia
    df_manual['cantidad'] = mm_scaler.fit_transform(df_manual[['cantidad']])

    # "jurisdicion_residencia_nombre"
    df_manual = df_manual.drop(columns=["jurisdiccion_de_residencia_id", "sexo_id", 'cie10_causa_id', "jurisdicion_residencia_nombre"]).copy()
    return df_manual


def transformacion_pipeline(df):
    df_auto = df.copy()

    pipeline = ColumnTransformer(transformers=[
    ('cat', OneHotEncoder(), ["cie10_clasificacion", "Sexo", "grupo_edad"]),
    ('num', StandardScaler(), ["anio", "cantidad"])
    ])

    X_transf = pipeline.fit_transform(df_auto)
    return X_transf, pipeline
