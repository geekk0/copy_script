from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "enhancetasks" ADD "yclients_certificate_code" INT;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "enhancetasks" DROP COLUMN "yclients_certificate_code";"""
