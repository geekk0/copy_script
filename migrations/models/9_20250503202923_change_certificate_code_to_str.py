from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "enhancetasks" ALTER COLUMN "yclients_certificate_code" TYPE VARCHAR(100) USING "yclients_certificate_code"::VARCHAR(100);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "enhancetasks" ALTER COLUMN "yclients_certificate_code" TYPE INT USING "yclients_certificate_code"::INT;"""
