from pydantic import BaseModel


class Language(BaseModel):
    """Pydantic schema for representing a language with its code and name."""
    code: str
    name: str
