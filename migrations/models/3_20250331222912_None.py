from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "clients" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "chat_id" BIGINT NOT NULL UNIQUE,
    "yclients_id" BIGINT NOT NULL UNIQUE,
    "phone_number" TEXT NOT NULL,
    "username" TEXT
);
CREATE TABLE IF NOT EXISTS "packages" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "name" TEXT NOT NULL,
    "photos_number" INT NOT NULL,
    "price" INT NOT NULL,
    "published" BOOL NOT NULL DEFAULT False
);
CREATE TABLE IF NOT EXISTS "enhancetasks" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "folder_path" TEXT NOT NULL,
    "yclients_record_id" BIGINT NOT NULL,
    "status" VARCHAR(10) NOT NULL DEFAULT 'pending',
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "enhanced_files_count" INT NOT NULL DEFAULT 0,
    "files_list" JSONB NOT NULL,
    "client_id" INT NOT NULL REFERENCES "clients" ("id") ON DELETE CASCADE,
    "package_id" INT NOT NULL REFERENCES "packages" ("id") ON DELETE CASCADE
);
COMMENT ON COLUMN "enhancetasks"."status" IS 'PENDING: pending\nQUEUED: queued\nPROCESSING: processing\nCOMPLETED: completed\nFAILED: failed';
CREATE TABLE IF NOT EXISTS "orders" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "photo_path" TEXT NOT NULL,
    "status" VARCHAR(10) NOT NULL DEFAULT 'pending',
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "client_id" INT NOT NULL REFERENCES "clients" ("id") ON DELETE CASCADE,
    "package_id" INT NOT NULL REFERENCES "packages" ("id") ON DELETE CASCADE
);
COMMENT ON COLUMN "orders"."status" IS 'PENDING: pending\nQUEUED: queued\nPROCESSING: processing\nCOMPLETED: completed\nFAILED: failed';
CREATE TABLE IF NOT EXISTS "aerich" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "version" VARCHAR(255) NOT NULL,
    "app" VARCHAR(100) NOT NULL,
    "content" JSONB NOT NULL
);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        """
