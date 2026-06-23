"""Tests de los modelos ORM contra SQLite (smoke)."""
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from api.models import Base, DimCie10, FactDefuncion


def test_orm_create_and_query(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path/'orm.db'}", future=True)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, future=True)

    with Session() as s:
        s.add(DimCie10(letra="I", capitulo="Circulatorio"))
        s.add(FactDefuncion(
            anio=2020, sexo="varon", grupo_edad="x", jurisdiccion="BA",
            cie10_clasificacion="x", supracategoria="x", cantidad=5,
        ))
        s.commit()
        rows = s.scalars(select(FactDefuncion)).all()
        assert len(rows) == 1
        assert rows[0].sexo == "varon"
