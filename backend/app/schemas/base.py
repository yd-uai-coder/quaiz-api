from pydantic import BaseModel, ConfigDict


class ORMReadModel(BaseModel):
    """ORMオブジェクトからそのまま変換できるReadスキーマの共通基底(from_attributes=True)。"""

    model_config = ConfigDict(from_attributes=True)
