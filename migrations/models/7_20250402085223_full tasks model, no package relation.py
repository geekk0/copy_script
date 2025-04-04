from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "enhancetasks" DROP CONSTRAINT IF EXISTS "fk_enhancet_packages_a3dfa4ca";
        ALTER TABLE "enhancetasks" ADD "price" INT NULL;
        ALTER TABLE "enhancetasks" ADD "max_photo_amount" INT NULL;
        ALTER TABLE "enhancetasks" ADD "yclients_certificate_type_id" INT NULL;
        ALTER TABLE "enhancetasks" DROP COLUMN "package_id";"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "enhancetasks" ADD "package_id" INT NOT NULL;
        ALTER TABLE "enhancetasks" DROP COLUMN "price";
        ALTER TABLE "enhancetasks" DROP COLUMN "max_photo_amount";
        ALTER TABLE "enhancetasks" DROP COLUMN "yclients_certificate_type_id";
        ALTER TABLE "enhancetasks" ADD CONSTRAINT "fk_enhancet_packages_a3dfa4ca" FOREIGN KEY ("package_id") REFERENCES "packages" ("id") ON DELETE CASCADE;"""
