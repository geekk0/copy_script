from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "enhancetasks" ALTER COLUMN "yclients_record_id" DROP NOT NULL;
        ALTER TABLE "orders" ADD "yclients_certificate_type_id" INT NULL DEFAULT NULL;
        ALTER TABLE "orders" ADD "amount" INT NULL DEFAULT NULL;
        ALTER TABLE "orders" ADD "yclients_certificate_code" INT NULL DEFAULT NULL;
        ALTER TABLE "packages" ADD "yclients_certificate_type_id" INT NULL DEFAULT NULL;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "orders" DROP COLUMN "yclients_certificate_type_id";
        ALTER TABLE "orders" DROP COLUMN "amount";
        ALTER TABLE "orders" DROP COLUMN "yclients_certificate_code";
        ALTER TABLE "packages" DROP COLUMN "yclients_certificate_type_id";
        ALTER TABLE "enhancetasks" ALTER COLUMN "yclients_record_id" SET NOT NULL;"""
