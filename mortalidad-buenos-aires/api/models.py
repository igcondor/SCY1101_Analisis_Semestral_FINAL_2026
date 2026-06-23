"""Modelos ORM SQLAlchemy (mapean las tablas del init.sql)."""
from sqlalchemy import BigInteger, Column, Integer, Numeric, String
from sqlalchemy.orm import DeclarativeBase

# En Postgres usamos BIGINT (BIGSERIAL); en SQLite el autoincrement solo
# funciona sobre INTEGER, así que damos una variante. Lo usan los tests.
BigIntPK = BigInteger().with_variant(Integer(), "sqlite")


class Base(DeclarativeBase):
    pass


class FactDefuncion(Base):
    __tablename__ = "fact_defunciones"

    id = Column(BigIntPK, primary_key=True, autoincrement=True)
    anio = Column(Integer, nullable=False, index=True)
    sexo = Column(String, nullable=False, index=True)
    grupo_edad = Column(String, nullable=False, index=True)
    jurisdiccion = Column(String, nullable=False)
    cie10_causa_id = Column(String)
    cie10_clasificacion = Column(String, nullable=False)
    supracategoria = Column(String, nullable=False, index=True)
    cantidad = Column(Integer, nullable=False)
    poblacion = Column(BigInteger)
    tasa_por_100k = Column(Numeric(10, 4))


class DimCie10(Base):
    __tablename__ = "dim_cie10"

    letra = Column(String(1), primary_key=True)
    capitulo = Column(String, nullable=False)
    descripcion = Column(String)
