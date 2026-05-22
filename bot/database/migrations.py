from __future__ import annotations

from sqlalchemy import text


def _has_column_sqlite(conn, table: str, column: str) -> bool:
    rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
    return any(r[1] == column for r in rows)  # r[1] = name


def migrate_drop_time_slots_price(engine) -> None:
    """
    Removes `price` column from `time_slots`.
    - Postgres: ALTER TABLE ... DROP COLUMN IF EXISTS
    - SQLite: recreate table without column (copy data)
    """
    dialect = engine.dialect.name
    with engine.begin() as conn:
        if dialect.startswith("postgres"):
            conn.execute(text("ALTER TABLE time_slots DROP COLUMN IF EXISTS price"))
            return

        if dialect == "sqlite":
            if not _has_column_sqlite(conn, "time_slots", "price"):
                return

            conn.execute(text("PRAGMA foreign_keys=OFF"))
            conn.execute(text("ALTER TABLE time_slots RENAME TO time_slots_old"))

            conn.execute(
                text(
                    """
                    CREATE TABLE time_slots (
                        id INTEGER NOT NULL PRIMARY KEY,
                        datetime DATETIME NOT NULL,
                        is_available BOOLEAN,
                        client_id INTEGER,
                        status VARCHAR(50),
                        currency VARCHAR(3),
                        FOREIGN KEY(client_id) REFERENCES users (id)
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    INSERT INTO time_slots (id, datetime, is_available, client_id, status, currency)
                    SELECT id, datetime, is_available, client_id, status, currency
                    FROM time_slots_old
                    """
                )
            )
            conn.execute(text("DROP TABLE time_slots_old"))
            conn.execute(text("PRAGMA foreign_keys=ON"))


def migrate_add_booking_meta_charged_amount(engine) -> None:
    """Adds `charged_amount` column to `booking_meta` for correct refunds."""
    dialect = engine.dialect.name
    with engine.begin() as conn:
        if dialect.startswith("postgres"):
            conn.execute(text("ALTER TABLE booking_meta ADD COLUMN IF NOT EXISTS charged_amount NUMERIC(10,2)"))
            return

        if dialect == "sqlite":
            if _has_column_sqlite(conn, "booking_meta", "charged_amount"):
                return
            conn.execute(text("ALTER TABLE booking_meta ADD COLUMN charged_amount NUMERIC(10,2)"))


def migrate_add_booking_meta_client_fields(engine) -> None:
    """Adds client_name/client_phone to booking_meta."""
    dialect = engine.dialect.name
    with engine.begin() as conn:
        if dialect.startswith("postgres"):
            conn.execute(text("ALTER TABLE booking_meta ADD COLUMN IF NOT EXISTS client_name VARCHAR(255)"))
            conn.execute(text("ALTER TABLE booking_meta ADD COLUMN IF NOT EXISTS client_phone VARCHAR(32)"))
            conn.execute(text("ALTER TABLE booking_meta ADD COLUMN IF NOT EXISTS booked_service_id INTEGER"))
            conn.execute(text("ALTER TABLE booking_meta ADD COLUMN IF NOT EXISTS reminder_sent BOOLEAN DEFAULT FALSE"))
            return

        if dialect == "sqlite":
            if not _has_column_sqlite(conn, "booking_meta", "client_name"):
                conn.execute(text("ALTER TABLE booking_meta ADD COLUMN client_name VARCHAR(255)"))
            if not _has_column_sqlite(conn, "booking_meta", "client_phone"):
                conn.execute(text("ALTER TABLE booking_meta ADD COLUMN client_phone VARCHAR(32)"))
            if not _has_column_sqlite(conn, "booking_meta", "booked_service_id"):
                conn.execute(text("ALTER TABLE booking_meta ADD COLUMN booked_service_id INTEGER"))
            if not _has_column_sqlite(conn, "booking_meta", "reminder_sent"):
                conn.execute(text("ALTER TABLE booking_meta ADD COLUMN reminder_sent BOOLEAN DEFAULT 0"))


def migrate_booking_meta_reschedule_fields(engine) -> None:
    """
    Adds reschedule-tracking fields to booking_meta and a unique guard index.
    """
    dialect = engine.dialect.name
    with engine.begin() as conn:
        if dialect.startswith("postgres"):
            conn.execute(text("ALTER TABLE booking_meta ADD COLUMN IF NOT EXISTS business_id INTEGER NOT NULL DEFAULT 1"))
            conn.execute(text("ALTER TABLE booking_meta ADD COLUMN IF NOT EXISTS client_id BIGINT"))
            conn.execute(text("ALTER TABLE booking_meta ADD COLUMN IF NOT EXISTS old_slot_id INTEGER"))
            conn.execute(text("ALTER TABLE booking_meta ADD COLUMN IF NOT EXISTS new_slot_id INTEGER"))
            conn.execute(text("ALTER TABLE booking_meta ADD COLUMN IF NOT EXISTS status VARCHAR(20)"))
            conn.execute(text("ALTER TABLE booking_meta ADD COLUMN IF NOT EXISTS created_by BIGINT"))
            conn.execute(text("ALTER TABLE booking_meta ADD COLUMN IF NOT EXISTS new_appointment_id INTEGER"))
            # prevent double pending reschedule for the same old_slot_id in a business
            conn.execute(
                text(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_booking_meta_active
                    ON booking_meta (business_id, old_slot_id)
                    WHERE status = 'pending' AND old_slot_id IS NOT NULL
                    """
                )
            )
            return

        if dialect == "sqlite":
            if not _has_column_sqlite(conn, "booking_meta", "business_id"):
                conn.execute(text("ALTER TABLE booking_meta ADD COLUMN business_id INTEGER NOT NULL DEFAULT 1"))
            if not _has_column_sqlite(conn, "booking_meta", "client_id"):
                conn.execute(text("ALTER TABLE booking_meta ADD COLUMN client_id INTEGER"))
            if not _has_column_sqlite(conn, "booking_meta", "old_slot_id"):
                conn.execute(text("ALTER TABLE booking_meta ADD COLUMN old_slot_id INTEGER"))
            if not _has_column_sqlite(conn, "booking_meta", "new_slot_id"):
                conn.execute(text("ALTER TABLE booking_meta ADD COLUMN new_slot_id INTEGER"))
            if not _has_column_sqlite(conn, "booking_meta", "status"):
                conn.execute(text("ALTER TABLE booking_meta ADD COLUMN status VARCHAR(20)"))
            if not _has_column_sqlite(conn, "booking_meta", "created_by"):
                conn.execute(text("ALTER TABLE booking_meta ADD COLUMN created_by INTEGER"))
            if not _has_column_sqlite(conn, "booking_meta", "new_appointment_id"):
                conn.execute(text("ALTER TABLE booking_meta ADD COLUMN new_appointment_id INTEGER"))

            conn.execute(
                text(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_booking_meta_active
                    ON booking_meta (business_id, old_slot_id)
                    WHERE status = 'pending' AND old_slot_id IS NOT NULL
                    """
                )
            )


def _table_exists(conn, table: str) -> bool:
    dialect = conn.engine.dialect.name
    if dialect == "sqlite":
        row = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name=:t"), {"t": table}).fetchone()
        return row is not None
    # postgres
    row = conn.execute(
        text("SELECT to_regclass(:t)"),
        {"t": table},
    ).fetchone()
    return bool(row and row[0])


def migrate_add_time_slots_service_id(engine) -> None:
    """
    Adds `service_id` column to `time_slots` and tries to backfill from `slot_services` if it exists.
    """
    dialect = engine.dialect.name
    with engine.begin() as conn:
        if dialect.startswith("postgres"):
            conn.execute(text("ALTER TABLE time_slots ADD COLUMN IF NOT EXISTS service_id INTEGER"))
            conn.execute(text("ALTER TABLE time_slots ADD CONSTRAINT IF NOT EXISTS fk_time_slots_service_id FOREIGN KEY (service_id) REFERENCES services(id)"))
            if _table_exists(conn, "slot_services"):
                conn.execute(text("UPDATE time_slots SET service_id = s.service_id FROM slot_services s WHERE s.slot_id = time_slots.id AND time_slots.service_id IS NULL"))
                conn.execute(text("DROP TABLE IF EXISTS slot_services"))
            return

        if dialect == "sqlite":
            if not _has_column_sqlite(conn, "time_slots", "service_id"):
                conn.execute(text("ALTER TABLE time_slots ADD COLUMN service_id INTEGER"))
            if _table_exists(conn, "slot_services"):
                conn.execute(text("UPDATE time_slots SET service_id = (SELECT service_id FROM slot_services WHERE slot_id = time_slots.id) WHERE service_id IS NULL"))
                conn.execute(text("DROP TABLE slot_services"))


def migrate_add_time_slots_confirmation_fields(engine) -> None:
    """
    Adds confirmation fields to time_slots:
    - is_confirmed BOOLEAN (default false)
    - confirmed_at DATETIME
    - confirmation_deadline DATETIME
    """
    dialect = engine.dialect.name
    with engine.begin() as conn:
        if dialect.startswith("postgres"):
            conn.execute(text("ALTER TABLE time_slots ADD COLUMN IF NOT EXISTS is_confirmed BOOLEAN NOT NULL DEFAULT FALSE"))
            conn.execute(text("ALTER TABLE time_slots ADD COLUMN IF NOT EXISTS confirmed_at TIMESTAMP NULL"))
            conn.execute(text("ALTER TABLE time_slots ADD COLUMN IF NOT EXISTS confirmation_deadline TIMESTAMP NULL"))
            return

        if dialect == "sqlite":
            if not _has_column_sqlite(conn, "time_slots", "is_confirmed"):
                conn.execute(text("ALTER TABLE time_slots ADD COLUMN is_confirmed BOOLEAN NOT NULL DEFAULT 0"))
            if not _has_column_sqlite(conn, "time_slots", "confirmed_at"):
                conn.execute(text("ALTER TABLE time_slots ADD COLUMN confirmed_at DATETIME"))
            if not _has_column_sqlite(conn, "time_slots", "confirmation_deadline"):
                conn.execute(text("ALTER TABLE time_slots ADD COLUMN confirmation_deadline DATETIME"))


def migrate_time_slots_business_and_uniques(engine) -> None:
    """
    Adds business_id to time_slots and creates unique constraints to avoid duplicate *available* slots.

    NOTE: We keep history rows (cancelled/rescheduled/etc.) in the same table.
    Therefore uniqueness must be scoped to "available" rows only.
    """
    dialect = engine.dialect.name
    with engine.begin() as conn:
        if dialect.startswith("postgres"):
            conn.execute(text("ALTER TABLE time_slots ADD COLUMN IF NOT EXISTS business_id INTEGER NOT NULL DEFAULT 1"))
            # unique_slot_datetime_business for available slots only
            conn.execute(
                text(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS unique_slot_datetime_business
                    ON time_slots (business_id, datetime)
                    WHERE status = 'available' AND is_available = TRUE
                    """
                )
            )
            return

        if dialect == "sqlite":
            if not _has_column_sqlite(conn, "time_slots", "business_id"):
                conn.execute(text("ALTER TABLE time_slots ADD COLUMN business_id INTEGER NOT NULL DEFAULT 1"))
            # Partial unique index is supported by modern SQLite.
            conn.execute(
                text(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS unique_slot_datetime_business
                    ON time_slots (business_id, datetime)
                    WHERE status = 'available' AND is_available = 1
                    """
                )
            )


def migrate_create_booking_reschedules(engine) -> None:
    """
    Creates booking_reschedules table for reschedule history and rollback.
    """
    dialect = engine.dialect.name
    with engine.begin() as conn:
        if dialect.startswith("postgres"):
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS booking_reschedules (
                        id SERIAL PRIMARY KEY,
                        old_slot_id INTEGER NOT NULL REFERENCES time_slots(id) ON DELETE CASCADE,
                        new_slot_id INTEGER NOT NULL REFERENCES time_slots(id) ON DELETE CASCADE,
                        actor_chat_id BIGINT NULL,
                        created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                        rolled_back BOOLEAN NOT NULL DEFAULT FALSE,
                        rolled_back_at TIMESTAMP NULL
                    )
                    """
                )
            )
            return

        if dialect == "sqlite":
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS booking_reschedules (
                        id INTEGER NOT NULL PRIMARY KEY,
                        old_slot_id INTEGER NOT NULL,
                        new_slot_id INTEGER NOT NULL,
                        actor_chat_id INTEGER NULL,
                        created_at DATETIME NOT NULL DEFAULT (CURRENT_TIMESTAMP),
                        rolled_back BOOLEAN NOT NULL DEFAULT 0,
                        rolled_back_at DATETIME NULL,
                        FOREIGN KEY(old_slot_id) REFERENCES time_slots (id) ON DELETE CASCADE,
                        FOREIGN KEY(new_slot_id) REFERENCES time_slots (id) ON DELETE CASCADE
                    )
                    """
                )
            )


def migrate_support_schema(engine) -> None:
    """
    Migrates support tables to the new schema:
    - support_messages(id, business_id, client_id, client_username, admin_id, message, is_from_client, is_read, reply_to_id, created_at)
    - support_conversations(business_id, client_id, unread_count, last_message_at, is_active)

    If an old support_messages table exists, it will be recreated and data will be mapped.
    """
    dialect = engine.dialect.name
    with engine.begin() as conn:
        if dialect.startswith("postgres"):
            # Conversations
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS support_conversations (
                        business_id INTEGER NOT NULL,
                        client_id BIGINT NOT NULL,
                        unread_count INTEGER NOT NULL DEFAULT 0,
                        last_message_at TIMESTAMP NOT NULL DEFAULT NOW(),
                        is_active BOOLEAN NOT NULL DEFAULT TRUE,
                        PRIMARY KEY (business_id, client_id)
                    )
                    """
                )
            )

            # If old schema present, try to rename columns; otherwise create new
            # We detect old columns via information_schema.
            cols = conn.execute(
                text(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name='support_messages'
                    """
                )
            ).fetchall()
            col_names = {c[0] for c in cols}
            if col_names and "user_chat_id" in col_names and "text" in col_names:
                # Recreate table to avoid complex partial-alter edge cases
                conn.execute(text("ALTER TABLE support_messages RENAME TO support_messages_old"))
                conn.execute(
                    text(
                        """
                        CREATE TABLE support_messages (
                            id SERIAL PRIMARY KEY,
                            business_id INTEGER NOT NULL,
                            client_id BIGINT NOT NULL,
                            client_username VARCHAR(255) NULL,
                            admin_id BIGINT NULL,
                            message TEXT NOT NULL,
                            is_from_client BOOLEAN NOT NULL,
                            is_read BOOLEAN NOT NULL DEFAULT FALSE,
                            reply_to_id INTEGER NULL,
                            created_at TIMESTAMP NOT NULL DEFAULT NOW()
                        )
                        """
                    )
                )
                conn.execute(
                    text(
                        """
                        INSERT INTO support_messages (id, business_id, client_id, client_username, admin_id, message, is_from_client, is_read, reply_to_id, created_at)
                        SELECT
                            id,
                            1 as business_id,
                            user_chat_id as client_id,
                            user_username as client_username,
                            admin_chat_id as admin_id,
                            text as message,
                            (direction = 'user') as is_from_client,
                            TRUE as is_read,
                            NULL as reply_to_id,
                            created_at
                        FROM support_messages_old
                        """
                    )
                )
                conn.execute(text("DROP TABLE support_messages_old"))
            else:
                # Create if not exists
                conn.execute(
                    text(
                        """
                        CREATE TABLE IF NOT EXISTS support_messages (
                            id SERIAL PRIMARY KEY,
                            business_id INTEGER NOT NULL,
                            client_id BIGINT NOT NULL,
                            client_username VARCHAR(255) NULL,
                            admin_id BIGINT NULL,
                            message TEXT NOT NULL,
                            is_from_client BOOLEAN NOT NULL,
                            is_read BOOLEAN NOT NULL DEFAULT FALSE,
                            reply_to_id INTEGER NULL,
                            created_at TIMESTAMP NOT NULL DEFAULT NOW()
                        )
                        """
                    )
                )
            return

        # SQLite
        if dialect == "sqlite":
            # Conversations
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS support_conversations (
                        business_id INTEGER NOT NULL,
                        client_id INTEGER NOT NULL,
                        unread_count INTEGER NOT NULL DEFAULT 0,
                        last_message_at DATETIME NOT NULL DEFAULT (CURRENT_TIMESTAMP),
                        is_active BOOLEAN NOT NULL DEFAULT 1,
                        PRIMARY KEY (business_id, client_id)
                    )
                    """
                )
            )

            # Recreate support_messages if old schema detected
            exists = conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name='support_messages'")
            ).fetchone()
            if not exists:
                conn.execute(
                    text(
                        """
                        CREATE TABLE support_messages (
                            id INTEGER NOT NULL PRIMARY KEY,
                            business_id INTEGER NOT NULL,
                            client_id INTEGER NOT NULL,
                            client_username VARCHAR(255) NULL,
                            admin_id INTEGER NULL,
                            message TEXT NOT NULL,
                            is_from_client BOOLEAN NOT NULL,
                            is_read BOOLEAN NOT NULL DEFAULT 0,
                            reply_to_id INTEGER NULL,
                            created_at DATETIME NOT NULL DEFAULT (CURRENT_TIMESTAMP)
                        )
                        """
                    )
                )
                return

            # check for old columns
            cols = conn.execute(text("PRAGMA table_info(support_messages)")).fetchall()
            col_names = {c[1] for c in cols}
            if "user_chat_id" in col_names and "text" in col_names:
                conn.execute(text("PRAGMA foreign_keys=OFF"))
                conn.execute(text("ALTER TABLE support_messages RENAME TO support_messages_old"))
                conn.execute(
                    text(
                        """
                        CREATE TABLE support_messages (
                            id INTEGER NOT NULL PRIMARY KEY,
                            business_id INTEGER NOT NULL,
                            client_id INTEGER NOT NULL,
                            client_username VARCHAR(255) NULL,
                            admin_id INTEGER NULL,
                            message TEXT NOT NULL,
                            is_from_client BOOLEAN NOT NULL,
                            is_read BOOLEAN NOT NULL DEFAULT 0,
                            reply_to_id INTEGER NULL,
                            created_at DATETIME NOT NULL DEFAULT (CURRENT_TIMESTAMP)
                        )
                        """
                    )
                )
                conn.execute(
                    text(
                        """
                        INSERT INTO support_messages (id, business_id, client_id, client_username, admin_id, message, is_from_client, is_read, reply_to_id, created_at)
                        SELECT
                            id,
                            1 as business_id,
                            user_chat_id as client_id,
                            user_username as client_username,
                            admin_chat_id as admin_id,
                            text as message,
                            CASE WHEN direction = 'user' THEN 1 ELSE 0 END as is_from_client,
                            1 as is_read,
                            NULL as reply_to_id,
                            created_at
                        FROM support_messages_old
                        """
                    )
                )
                conn.execute(text("DROP TABLE support_messages_old"))
                conn.execute(text("PRAGMA foreign_keys=ON"))
            else:
                # New schema already (or partially) - ensure missing columns
                required = [
                    ("business_id", "INTEGER NOT NULL DEFAULT 1"),
                    ("client_id", "INTEGER NOT NULL DEFAULT 0"),
                    ("client_username", "VARCHAR(255)"),
                    ("admin_id", "INTEGER"),
                    ("message", "TEXT"),
                    ("is_from_client", "BOOLEAN NOT NULL DEFAULT 1"),
                    ("is_read", "BOOLEAN NOT NULL DEFAULT 0"),
                    ("reply_to_id", "INTEGER"),
                    ("created_at", "DATETIME"),
                ]
                for name, ddl in required:
                    if name not in col_names:
                        conn.execute(text(f"ALTER TABLE support_messages ADD COLUMN {name} {ddl}"))


def migrate_schedule_templates(engine) -> None:
    """
    Creates schedule templates/rules/exceptions and adds generation metadata columns to time_slots.
    """
    dialect = engine.dialect.name
    with engine.begin() as conn:
        if dialect.startswith("postgres"):
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS schedule_templates (
                        id SERIAL PRIMARY KEY,
                        business_id INTEGER NOT NULL DEFAULT 1,
                        name VARCHAR(255) NOT NULL,
                        is_active BOOLEAN NOT NULL DEFAULT TRUE,
                        created_at TIMESTAMP NOT NULL DEFAULT NOW()
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS template_rules (
                        id SERIAL PRIMARY KEY,
                        template_id INTEGER NOT NULL REFERENCES schedule_templates(id) ON DELETE CASCADE,
                        day_of_week INTEGER NOT NULL,
                        start_time VARCHAR(5) NOT NULL,
                        end_time VARCHAR(5) NOT NULL,
                        slot_duration INTEGER NOT NULL,
                        break_start VARCHAR(5) NULL,
                        break_end VARCHAR(5) NULL,
                        service_id INTEGER NULL,
                        created_at TIMESTAMP NOT NULL DEFAULT NOW()
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS schedule_exceptions (
                        id SERIAL PRIMARY KEY,
                        business_id INTEGER NOT NULL DEFAULT 1,
                        exception_date VARCHAR(10) NOT NULL,
                        exception_type VARCHAR(20) NOT NULL,
                        start_time VARCHAR(5) NULL,
                        end_time VARCHAR(5) NULL,
                        slot_duration INTEGER NULL,
                        service_id INTEGER NULL,
                        reason VARCHAR(255) NULL,
                        created_at TIMESTAMP NOT NULL DEFAULT NOW()
                    )
                    """
                )
            )
            conn.execute(text("ALTER TABLE time_slots ADD COLUMN IF NOT EXISTS generated_from_template_id INTEGER"))
            conn.execute(text("ALTER TABLE time_slots ADD COLUMN IF NOT EXISTS generated_from_rule_id INTEGER"))
            conn.execute(text("ALTER TABLE time_slots ADD COLUMN IF NOT EXISTS is_exception BOOLEAN NOT NULL DEFAULT FALSE"))
            return

        if dialect == "sqlite":
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS schedule_templates (
                        id INTEGER NOT NULL PRIMARY KEY,
                        business_id INTEGER NOT NULL DEFAULT 1,
                        name VARCHAR(255) NOT NULL,
                        is_active BOOLEAN NOT NULL DEFAULT 1,
                        created_at DATETIME NOT NULL DEFAULT (CURRENT_TIMESTAMP)
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS template_rules (
                        id INTEGER NOT NULL PRIMARY KEY,
                        template_id INTEGER NOT NULL,
                        day_of_week INTEGER NOT NULL,
                        start_time VARCHAR(5) NOT NULL,
                        end_time VARCHAR(5) NOT NULL,
                        slot_duration INTEGER NOT NULL,
                        break_start VARCHAR(5) NULL,
                        break_end VARCHAR(5) NULL,
                        service_id INTEGER NULL,
                        created_at DATETIME NOT NULL DEFAULT (CURRENT_TIMESTAMP),
                        FOREIGN KEY(template_id) REFERENCES schedule_templates (id) ON DELETE CASCADE
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS schedule_exceptions (
                        id INTEGER NOT NULL PRIMARY KEY,
                        business_id INTEGER NOT NULL DEFAULT 1,
                        exception_date VARCHAR(10) NOT NULL,
                        exception_type VARCHAR(20) NOT NULL,
                        start_time VARCHAR(5) NULL,
                        end_time VARCHAR(5) NULL,
                        slot_duration INTEGER NULL,
                        service_id INTEGER NULL,
                        reason VARCHAR(255) NULL,
                        created_at DATETIME NOT NULL DEFAULT (CURRENT_TIMESTAMP)
                    )
                    """
                )
            )
            if not _has_column_sqlite(conn, "time_slots", "generated_from_template_id"):
                conn.execute(text("ALTER TABLE time_slots ADD COLUMN generated_from_template_id INTEGER"))
            if not _has_column_sqlite(conn, "time_slots", "generated_from_rule_id"):
                conn.execute(text("ALTER TABLE time_slots ADD COLUMN generated_from_rule_id INTEGER"))
            if not _has_column_sqlite(conn, "time_slots", "is_exception"):
                conn.execute(text("ALTER TABLE time_slots ADD COLUMN is_exception BOOLEAN NOT NULL DEFAULT 0"))


def migrate_template_rules_break_minutes(engine) -> None:
    """
    Adds break_minutes column to template_rules:
    - break_minutes: optional minutes to add between consecutive slots (buffer/cleanup time).
    """
    dialect = engine.dialect.name
    with engine.begin() as conn:
        if dialect.startswith("postgres"):
            conn.execute(text("ALTER TABLE template_rules ADD COLUMN IF NOT EXISTS break_minutes INTEGER"))
            return

        if dialect == "sqlite":
            if _has_column_sqlite(conn, "template_rules", "break_minutes"):
                return
            conn.execute(text("ALTER TABLE template_rules ADD COLUMN break_minutes INTEGER"))
