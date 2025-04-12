from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "enhancetasks" ALTER COLUMN "status" SET DEFAULT 'Задача создана';
        ALTER TABLE "enhancetasks" ALTER COLUMN "status" TYPE VARCHAR(29) USING "status"::VARCHAR(29);
        COMMENT ON COLUMN "enhancetasks"."status" IS 'PENDING: Задача создана
QUEUED: Обработка добавлена в очередь
PROCESSING: Идет обработка
COMPLETED: Обработка завершена
FAILED: Ошибка обработки';
        ALTER TABLE "orders" ALTER COLUMN "status" SET DEFAULT 'Задача создана';
        ALTER TABLE "orders" ALTER COLUMN "status" TYPE VARCHAR(29) USING "status"::VARCHAR(29);
        COMMENT ON COLUMN "orders"."status" IS 'PENDING: Задача создана
QUEUED: Обработка добавлена в очередь
PROCESSING: Идет обработка
COMPLETED: Обработка завершена
FAILED: Ошибка обработки';"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "orders" ALTER COLUMN "status" SET DEFAULT 'pending';
        COMMENT ON COLUMN "orders"."status" IS 'PENDING: pending
QUEUED: queued
PROCESSING: processing
COMPLETED: completed
FAILED: failed';
        ALTER TABLE "orders" ALTER COLUMN "status" TYPE VARCHAR(10) USING "status"::VARCHAR(10);
        ALTER TABLE "enhancetasks" ALTER COLUMN "status" SET DEFAULT 'pending';
        COMMENT ON COLUMN "enhancetasks"."status" IS 'PENDING: pending
QUEUED: queued
PROCESSING: processing
COMPLETED: completed
FAILED: failed';
        ALTER TABLE "enhancetasks" ALTER COLUMN "status" TYPE VARCHAR(10) USING "status"::VARCHAR(10);"""
