from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "packages" ADD "purchase_url" TEXT NULL DEFAULT NULL;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "packages" DROP COLUMN "purchase_url";"""
