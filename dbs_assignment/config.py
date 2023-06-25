from pydantic import BaseSettings


class Settings(BaseSettings):
    class Config:
        case_sensitive = True

    DATABASE_NAME: str
    DATABASE_HOST: str
    DATABASE_PORT: int
    DATABASE_USER: str
    DATABASE_PASSWORD: str


settings = Settings()
