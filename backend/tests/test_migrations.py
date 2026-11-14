"""Tests for Alembic migration configuration and metadata discovery."""

import os
import subprocess
import sys
from pathlib import Path
from textwrap import dedent

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import Boolean, create_engine, inspect, text

# Add backend to path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.core.database import Base
from app.core.config import settings


class TestAlembicConfiguration:
    """Tests for Alembic configuration correctness."""

    def test_alembic_ini_exists(self):
        """alembic.ini exists in backend directory."""
        alembic_ini = backend_dir / "alembic.ini"
        assert alembic_ini.exists(), "alembic.ini not found"

    def test_alembic_env_py_exists(self):
        """alembic/env.py exists."""
        env_py = backend_dir / "alembic" / "env.py"
        assert env_py.exists(), "alembic/env.py not found"

    def test_alembic_versions_dir_exists(self):
        """alembic/versions directory exists."""
        versions_dir = backend_dir / "alembic" / "versions"
        assert versions_dir.exists(), "alembic/versions directory not found"
        assert versions_dir.is_dir()

    def test_alembic_config_loads(self):
        """Alembic config loads without error."""
        config = Config(str(backend_dir / "alembic.ini"))
        script_location = config.get_main_option("script_location")
        assert script_location.endswith("alembic") or script_location == "alembic"

    def test_alembic_script_directory_loads(self):
        """ScriptDirectory loads migration scripts."""
        config = Config(str(backend_dir / "alembic.ini"))
        script_dir = ScriptDirectory.from_config(config)
        revisions = list(script_dir.walk_revisions())
        # Expected chain (7 migrations):
        # baseline -> fix_is_active -> owner_id -> refresh_tokens -> password_reset_tokens -> login_attempts -> session_fields
        assert len(revisions) == 7, f"Expected 7 migrations, got {len(revisions)}: {[r.revision for r in revisions]}"

        # walk_revisions returns newest first (head -> base)
        # revisions[0] = session_fields (head)
        # revisions[1] = login_attempts
        # revisions[2] = password_reset_tokens
        # revisions[3] = refresh_tokens
        # revisions[4] = owner_id
        # revisions[5] = fix_is_active
        # revisions[6] = baseline (base)

        # Check session_fields migration (newest head)
        session_rev = revisions[0]
        assert "session" in session_rev.doc.lower()

        # Check login_attempts migration
        login_rev = revisions[1]
        assert "login" in login_rev.doc.lower() or "attempt" in login_rev.doc.lower()

        # Check password_reset_tokens migration
        reset_rev = revisions[2]
        assert "password_reset" in reset_rev.doc.lower() or "reset_token" in reset_rev.doc.lower()

        # Check refresh_tokens migration
        refresh_rev = revisions[3]
        assert "refresh_token" in refresh_rev.doc.lower()

        # Check owner_id migration
        owner_rev = revisions[4]
        assert "owner_id" in owner_rev.doc.lower() or "ownership" in owner_rev.doc.lower()

        # Check fix migration (is_active varchar -> boolean)
        fix_rev = revisions[5]
        assert "fix" in fix_rev.doc.lower() or "is_active" in fix_rev.doc.lower()

        # Check baseline migration (oldest/base)
        baseline = revisions[6]
        assert "baseline" in baseline.doc.lower() or "baseline" in baseline.revision

        # Verify linear chain (each revision's down_revision matches previous)
        for i in range(len(revisions) - 1):
            assert revisions[i].down_revision == revisions[i + 1].revision, \
                f"Chain broken: {revisions[i].revision} -> {revisions[i].down_revision} != {revisions[i + 1].revision}"

    def test_target_metadata_is_base_metadata(self):
        """env.py target_metadata is set to Base.metadata."""
        # Read env.py and verify target_metadata assignment
        env_py = (backend_dir / "alembic" / "env.py").read_text()
        assert "target_metadata = Base.metadata" in env_py

    def test_full_migration_chain_upgrade_downgrade(self, tmp_path):
        """Full migration chain from base to head upgrades and downgrades correctly."""
        test_db_url = f"sqlite:///{tmp_path}/test.db"
        config = Config(str(backend_dir / "alembic.ini"))
        config.set_main_option("sqlalchemy.url", test_db_url)

        # Upgrade to head
        command.upgrade(config, "head")

        engine = create_engine(test_db_url)
        inspector = inspect(engine)

        # Verify all tables exist
        tables = inspector.get_table_names()
        assert "farms" in tables
        assert "users" in tables
        assert "refresh_tokens" in tables
        assert "password_reset_tokens" in tables
        assert "alembic_version" in tables

        # Verify refresh_tokens table structure (includes session fields from latest migration)
        refresh_cols = {col["name"] for col in inspector.get_columns("refresh_tokens")}
        expected_refresh_cols = {
            "id", "user_id", "token_hash", "is_revoked", "created_at", "revoked_at", "expires_at",
            "session_id", "device_info", "ip_address", "last_used_at"
        }
        assert refresh_cols == expected_refresh_cols

        # Verify password_reset_tokens table structure
        reset_cols = {col["name"] for col in inspector.get_columns("password_reset_tokens")}
        expected_reset_cols = {
            "id", "user_id", "token_hash", "is_used", "created_at", "used_at", "expires_at"
        }
        assert reset_cols == expected_reset_cols

        # Verify foreign keys
        refresh_fks = inspector.get_foreign_keys("refresh_tokens")
        # SQLite may not name FK constraints, just verify they exist and point to users.id
        assert len(refresh_fks) >= 1
        for fk in refresh_fks:
            assert fk["referred_table"] == "users"
            assert fk["constrained_columns"] == ["user_id"]
            assert fk["referred_columns"] == ["id"]

        reset_fks = inspector.get_foreign_keys("password_reset_tokens")
        assert len(reset_fks) >= 1
        for fk in reset_fks:
            assert fk["referred_table"] == "users"
            assert fk["constrained_columns"] == ["user_id"]
            assert fk["referred_columns"] == ["id"]

        # Downgrade one step (remove password_reset_tokens)
        command.downgrade(config, "f02b56625eab")

        inspector = inspect(engine)
        tables = inspector.get_table_names()
        assert "password_reset_tokens" not in tables
        assert "refresh_tokens" in tables

        # Downgrade one step (remove refresh_tokens)
        command.downgrade(config, "21ff1745e9fa")

        inspector = inspect(engine)
        tables = inspector.get_table_names()
        assert "refresh_tokens" not in tables

        # Downgrade to base (remove owner_id, fix, baseline)
        command.downgrade(config, "base")

        inspector = inspect(engine)
        tables = inspector.get_table_names()
        assert "farms" not in tables
        assert "users" not in tables


class TestMigrationMetadata:
    """Tests for model metadata discovery."""

    def test_farm_model_in_metadata(self):
        """Farm model is registered in Base.metadata."""
        assert "farms" in Base.metadata.tables
        farm_table = Base.metadata.tables["farms"]
        assert farm_table.columns["id"].primary_key
        assert farm_table.columns["name"].nullable is False
        assert farm_table.columns["latitude"].nullable is False
        assert farm_table.columns["longitude"].nullable is False

    def test_user_model_in_metadata(self):
        """User model is registered in Base.metadata."""
        assert "users" in Base.metadata.tables
        user_table = Base.metadata.tables["users"]
        assert user_table.columns["id"].primary_key
        assert user_table.columns["email"].unique is True
        assert user_table.columns["hashed_password"].nullable is False
        # is_active should be Boolean in model
        assert isinstance(user_table.columns["is_active"].type, Boolean)

    def test_indexes_defined(self):
        """Expected indexes are defined in metadata."""
        farm_table = Base.metadata.tables["farms"]
        index_names = {idx.name for idx in farm_table.indexes}
        assert "ix_farms_name" in index_names
        assert "ix_farms_farmer_name" in index_names
        assert "ix_farms_region" in index_names

        user_table = Base.metadata.tables["users"]
        user_index_names = {idx.name for idx in user_table.indexes}
        assert "ix_users_email" in user_index_names
        assert "ix_users_id" in user_index_names


class TestDatabaseState:
    """Tests for actual database state (using test database)."""

    @pytest.fixture
    def test_db_url(self, tmp_path):
        """Create a temporary file-based SQLite database for testing."""
        db_file = tmp_path / "test.db"
        return f"sqlite:///{db_file}"

    def test_baseline_migration_creates_tables(self, test_db_url):
        """Baseline migration creates both tables."""
        config = Config(str(backend_dir / "alembic.ini"))
        config.set_main_option("sqlalchemy.url", test_db_url)

        # Run baseline migration
        command.upgrade(config, "63e13e54603a")

        # Verify tables created - use same URL
        engine = create_engine(test_db_url)
        inspector = inspect(engine)
        tables = inspector.get_table_names()

        assert "farms" in tables
        assert "users" in tables
        assert "alembic_version" in tables

        # Check farms columns
        farms_cols = {col["name"] for col in inspector.get_columns("farms")}
        expected_farms_cols = {
            "id", "name", "farmer_name", "latitude", "longitude", "elevation_m",
            "region", "country", "total_area_hectares", "soil_type", "soil_ph",
            "organic_matter_pct", "primary_irrigation", "current_crop",
            "current_crop_planting_date", "previous_crops", "created_at", "updated_at"
        }
        assert farms_cols == expected_farms_cols

        # Check users columns (baseline has VARCHAR(5) for is_active)
        users_cols = {col["name"] for col in inspector.get_columns("users")}
        expected_users_cols = {
            "id", "email", "hashed_password", "role", "is_active", "created_at", "updated_at"
        }
        assert users_cols == expected_users_cols

        # Verify is_active is VARCHAR in baseline
        is_active_col = next(c for c in inspector.get_columns("users") if c["name"] == "is_active")
        assert "VARCHAR" in str(is_active_col["type"]).upper()

    def test_fix_migration_changes_is_active_to_boolean(self, test_db_url):
        """Fix migration changes is_active from VARCHAR to Boolean."""
        config = Config(str(backend_dir / "alembic.ini"))
        config.set_main_option("sqlalchemy.url", test_db_url)

        # Run both migrations
        command.upgrade(config, "head")

        # Verify is_active is now Boolean (SQLite stores as INTEGER)
        engine = create_engine(test_db_url)
        inspector = inspect(engine)
        is_active_col = next(c for c in inspector.get_columns("users") if c["name"] == "is_active")

        # SQLite Boolean is stored as INTEGER
        col_type = str(is_active_col["type"]).upper()
        assert "INTEGER" in col_type or "BOOLEAN" in col_type
        assert "VARCHAR" not in col_type

    def test_downgrade_works(self, test_db_url):
        """Downgrade from head to base works."""
        config = Config(str(backend_dir / "alembic.ini"))
        config.set_main_option("sqlalchemy.url", test_db_url)

        # Upgrade to head
        command.upgrade(config, "head")

        # Downgrade to base
        command.downgrade(config, "base")

        # Verify tables dropped
        engine = create_engine(test_db_url)
        inspector = inspect(engine)
        tables = inspector.get_table_names()

        assert "farms" not in tables
        assert "users" not in tables
        # alembic_version may or may not exist after downgrade to base

    def test_owner_id_column_added(self, test_db_url):
        """Owner_id column is added to farms table after migration."""
        config = Config(str(backend_dir / "alembic.ini"))
        config.set_main_option("sqlalchemy.url", test_db_url)
        command.upgrade(config, "head")

        engine = create_engine(test_db_url)
        inspector = inspect(engine)
        farms_cols = {col["name"] for col in inspector.get_columns("farms")}
        assert "owner_id" in farms_cols

        # Verify owner_id is nullable
        owner_id_col = next(c for c in inspector.get_columns("farms") if c["name"] == "owner_id")
        assert owner_id_col["nullable"] is True

    def test_owner_id_index_created(self, test_db_url):
        """Index on owner_id is created."""
        config = Config(str(backend_dir / "alembic.ini"))
        config.set_main_option("sqlalchemy.url", test_db_url)
        command.upgrade(config, "head")

        engine = create_engine(test_db_url)
        inspector = inspect(engine)
        index_names = {idx["name"] for idx in inspector.get_indexes("farms")}
        assert "ix_farms_owner_id" in index_names

    def test_owner_id_foreign_key_created(self, test_db_url):
        """Foreign key from farms.owner_id to users.id is created."""
        config = Config(str(backend_dir / "alembic.ini"))
        config.set_main_option("sqlalchemy.url", test_db_url)
        command.upgrade(config, "head")

        engine = create_engine(test_db_url)
        inspector = inspect(engine)
        fks = inspector.get_foreign_keys("farms")
        fk_names = {fk["name"] for fk in fks}
        assert "fk_farms_owner_id_users" in fk_names

        # Verify it points to users.id
        fk = next(fk for fk in fks if fk["name"] == "fk_farms_owner_id_users")
        assert fk["referred_table"] == "users"
        assert fk["constrained_columns"] == ["owner_id"]
        assert fk["referred_columns"] == ["id"]

    def test_new_farm_can_store_owner_id(self, test_db_url):
        """New farms can store an owner ID referencing a user."""
        config = Config(str(backend_dir / "alembic.ini"))
        config.set_main_option("sqlalchemy.url", test_db_url)
        command.upgrade(config, "head")

        engine = create_engine(test_db_url)
        from sqlalchemy import text

        with engine.connect() as conn:
            # Create a user
            user_id = "test-user-123"
            conn.execute(text("""
                INSERT INTO users (id, email, hashed_password, role, is_active, created_at, updated_at)
                VALUES (:id, :email, :hp, :role, :active, :created, :updated)
            """), {
                "id": user_id,
                "email": "test@example.com",
                "hp": "hashed",
                "role": "user",
                "active": 1,
                "created": "2024-01-01 00:00:00",
                "updated": "2024-01-01 00:00:00"
            })

            # Create a farm with owner_id
            farm_id = "test-farm-123"
            conn.execute(text("""
                INSERT INTO farms (id, name, farmer_name, latitude, longitude, elevation_m, region, country,
                                   total_area_hectares, soil_type, soil_ph, organic_matter_pct,
                                   primary_irrigation, current_crop, current_crop_planting_date,
                                   previous_crops, created_at, updated_at, owner_id)
                VALUES (:id, :name, :fn, :lat, :lon, :elev, :region, :country,
                        :area, :stype, :ph, :om, :irrig, :crop, :cpd, :pc, :created, :updated, :oid)
            """), {
                "id": farm_id,
                "name": "Test Farm",
                "fn": "Farmer",
                "lat": 10.0,
                "lon": 20.0,
                "elev": 100.0,
                "region": "Region",
                "country": "Country",
                "area": 50.0,
                "stype": "loam",
                "ph": 6.5,
                "om": 3.0,
                "irrig": "rainfed",
                "crop": "wheat",
                "cpd": "2024-01-01",
                "pc": "[]",
                "created": "2024-01-01 00:00:00",
                "updated": "2024-01-01 00:00:00",
                "oid": user_id
            })
            conn.commit()

            # Verify farm has owner_id
            result = conn.execute(text("SELECT owner_id FROM farms WHERE id = :id"), {"id": farm_id})
            assert result.scalar() == user_id

    def test_legacy_farm_retains_null_owner_id(self, test_db_url):
        """Legacy farms can retain a NULL owner_id."""
        config = Config(str(backend_dir / "alembic.ini"))
        config.set_main_option("sqlalchemy.url", test_db_url)
        command.upgrade(config, "head")

        engine = create_engine(test_db_url)
        from sqlalchemy import text

        with engine.connect() as conn:
            # Create a farm WITHOUT owner_id (legacy)
            farm_id = "legacy-farm-123"
            conn.execute(text("""
                INSERT INTO farms (id, name, farmer_name, latitude, longitude, elevation_m, region, country,
                                   total_area_hectares, soil_type, soil_ph, organic_matter_pct,
                                   primary_irrigation, current_crop, current_crop_planting_date,
                                   previous_crops, created_at, updated_at, owner_id)
                VALUES (:id, :name, :fn, :lat, :lon, :elev, :region, :country,
                        :area, :stype, :ph, :om, :irrig, :crop, :cpd, :pc, :created, :updated, NULL)
            """), {
                "id": farm_id,
                "name": "Legacy Farm",
                "fn": "Old Farmer",
                "lat": 10.0,
                "lon": 20.0,
                "elev": 100.0,
                "region": "Region",
                "country": "Country",
                "area": 50.0,
                "stype": "loam",
                "ph": 6.5,
                "om": 3.0,
                "irrig": "rainfed",
                "crop": "wheat",
                "cpd": "2024-01-01",
                "pc": "[]",
                "created": "2024-01-01 00:00:00",
                "updated": "2024-01-01 00:00:00"
            })
            conn.commit()

            # Verify farm has NULL owner_id
            result = conn.execute(text("SELECT owner_id FROM farms WHERE id = :id"), {"id": farm_id})
            assert result.scalar() is None

    def test_migration_preserves_existing_farm_data(self, test_db_url):
        """Existing farm data remains intact after migration."""
        config = Config(str(backend_dir / "alembic.ini"))
        config.set_main_option("sqlalchemy.url", test_db_url)

        # Run baseline migration first
        command.upgrade(config, "63e13e54603a")

        # Insert some farms before owner_id migration
        engine = create_engine(test_db_url)
        from sqlalchemy import text

        with engine.connect() as conn:
            for i in range(3):
                conn.execute(text("""
                    INSERT INTO farms (id, name, farmer_name, latitude, longitude, elevation_m, region, country,
                                       total_area_hectares, soil_type, soil_ph, organic_matter_pct,
                                       primary_irrigation, current_crop, current_crop_planting_date,
                                       previous_crops, created_at, updated_at)
                    VALUES (:id, :name, :fn, :lat, :lon, :elev, :region, :country,
                            :area, :stype, :ph, :om, :irrig, :crop, :cpd, :pc, :created, :updated)
                """), {
                    "id": f"farm-{i}",
                    "name": f"Farm {i}",
                    "fn": f"Farmer {i}",
                    "lat": 10.0 + i,
                    "lon": 20.0 + i,
                    "elev": 100.0,
                    "region": "Region",
                    "country": "Country",
                    "area": 50.0,
                    "stype": "loam",
                    "ph": 6.5,
                    "om": 3.0,
                    "irrig": "rainfed",
                    "crop": "wheat",
                    "cpd": "2024-01-01",
                    "pc": "[]",
                    "created": "2024-01-01 00:00:00",
                    "updated": "2024-01-01 00:00:00"
                })
            conn.commit()

            # Verify 3 farms exist
            result = conn.execute(text("SELECT COUNT(*) FROM farms"))
            assert result.scalar() == 3

        # Now run the owner_id migration
        command.upgrade(config, "head")

        # Verify farms still exist with same data
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM farms"))
            assert result.scalar() == 3

            result = conn.execute(text("SELECT name FROM farms ORDER BY id"))
            names = [row[0] for row in result]
            assert names == ["Farm 0", "Farm 1", "Farm 2"]

            # Verify owner_id is NULL for all
            result = conn.execute(text("SELECT owner_id FROM farms"))
            owner_ids = [row[0] for row in result]
            assert all(oid is None for oid in owner_ids)

    def test_migration_upgrade_downgrade_cycle(self, test_db_url):
        """Migration upgrade and downgrade behave correctly."""
        config = Config(str(backend_dir / "alembic.ini"))
        config.set_main_option("sqlalchemy.url", test_db_url)

        # Upgrade to head
        command.upgrade(config, "head")

        engine = create_engine(test_db_url)
        inspector = inspect(engine)

        # Verify owner_id column exists
        farms_cols = {col["name"] for col in inspector.get_columns("farms")}
        assert "owner_id" in farms_cols

        # Verify index exists
        index_names = {idx["name"] for idx in inspector.get_indexes("farms")}
        assert "ix_farms_owner_id" in index_names

        # Verify foreign key exists
        fks = inspector.get_foreign_keys("farms")
        fk_names = {fk["name"] for fk in fks}
        assert "fk_farms_owner_id_users" in fk_names

        # Downgrade one step (remove owner_id)
        command.downgrade(config, "dddcbfadde78")

        # Create new inspector to reflect downgraded schema
        inspector = inspect(engine)

        # Verify owner_id column removed
        farms_cols = {col["name"] for col in inspector.get_columns("farms")}
        assert "owner_id" not in farms_cols

        # Verify index removed
        index_names = {idx["name"] for idx in inspector.get_indexes("farms")}
        assert "ix_farms_owner_id" not in index_names

        # Verify foreign key removed
        fks = inspector.get_foreign_keys("farms")
        fk_names = {fk["name"] for fk in fks}
        assert "fk_farms_owner_id_users" not in fk_names


class TestExistingDatabasePreservation:
    """Tests that existing database is preserved and compatible."""

    def test_existing_database_has_alembic_version(self):
        """Existing database has alembic_version table with correct revision."""
        db_path = backend_dir / "data" / "agroverse.db"
        if not db_path.exists():
            pytest.skip("Development database not found")

        engine = create_engine(f"sqlite:///{db_path}")
        inspector = inspect(engine)
        tables = inspector.get_table_names()

        assert "alembic_version" in tables

        # Check current revision using text() for SQLAlchemy 2.0
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version_num FROM alembic_version"))
            version = result.scalar()
            # Head revision is now the session_fields migration
            assert version == "846343d05df3", f"Expected head revision, got {version}"

    def test_existing_database_tables_match_models(self):
        """Existing database tables are compatible with current models."""
        db_path = backend_dir / "data" / "agroverse.db"
        if not db_path.exists():
            pytest.skip("Development database not found")

        engine = create_engine(f"sqlite:///{db_path}")
        inspector = inspect(engine)

        # Check farms table exists with expected columns
        assert "farms" in inspector.get_table_names()
        farms_cols = {col["name"] for col in inspector.get_columns("farms")}
        expected_farms_cols = {
            "id", "name", "farmer_name", "latitude", "longitude", "elevation_m",
            "region", "country", "total_area_hectares", "soil_type", "soil_ph",
            "organic_matter_pct", "primary_irrigation", "current_crop",
            "current_crop_planting_date", "previous_crops", "created_at", "updated_at",
            "owner_id"
        }
        assert farms_cols == expected_farms_cols

        # Check users table exists
        assert "users" in inspector.get_table_names()
        users_cols = {col["name"] for col in inspector.get_columns("users")}
        expected_users_cols = {
            "id", "email", "hashed_password", "role", "is_active", "created_at", "updated_at"
        }
        assert users_cols == expected_users_cols

    def test_no_destructive_changes_in_migrations(self):
        """Migrations do not contain DROP TABLE or destructive operations on existing tables in upgrade()."""
        versions_dir = backend_dir / "alembic" / "versions"
        migration_files = list(versions_dir.glob("*.py"))

        for migration_file in migration_files:
            content = migration_file.read_text()
            # Check upgrade() function doesn't have destructive ops
            # (downgrade() can have them)
            in_upgrade = False
            in_downgrade = False
            for line in content.split('\n'):
                stripped = line.strip()
                if stripped.startswith('def upgrade'):
                    in_upgrade = True
                    in_downgrade = False
                elif stripped.startswith('def downgrade'):
                    in_upgrade = False
                    in_downgrade = True
                elif stripped == '"""' or stripped == "'''":
                    continue
                elif in_upgrade and not in_downgrade:
                    # In upgrade function - check for destructive ops
                    if 'op.drop_table' in stripped and 'alembic_version' not in stripped:
                        # Allow drop_table only in comments or strings
                        if not stripped.startswith('#') and '"""' not in stripped:
                            pytest.fail(f"Destructive op.drop_table in upgrade() of {migration_file.name}")
                    if 'op.drop_column' in stripped:
                        if not stripped.startswith('#') and '"""' not in stripped:
                            pytest.fail(f"Destructive op.drop_column in upgrade() of {migration_file.name}")


class TestGitIgnore:
    """Tests for .gitignore coverage."""

    def test_backend_gitignore_exists(self):
        """Backend .gitignore exists."""
        gitignore = backend_dir / ".gitignore"
        assert gitignore.exists(), "backend/.gitignore not found"

    def test_gitignore_covers_env_files(self):
        """.gitignore covers .env files."""
        gitignore = backend_dir / ".gitignore"
        content = gitignore.read_text()
        assert ".env" in content

    def test_gitignore_covers_database_files(self):
        """.gitignore covers local database files."""
        gitignore = backend_dir / ".gitignore"
        content = gitignore.read_text()
        assert "*.db" in content or "data/*.db" in content

    def test_gitignore_covers_venv(self):
        """.gitignore covers virtual environment (check root .gitignore too)."""
        # Check backend .gitignore
        backend_gitignore = backend_dir / ".gitignore"
        backend_content = backend_gitignore.read_text()
        # Check root .gitignore
        root_gitignore = backend_dir.parent / ".gitignore"
        root_content = root_gitignore.read_text() if root_gitignore.exists() else ""
        combined = backend_content + "\n" + root_content
        assert ".venv" in combined or "venv/" in combined

    def test_gitignore_covers_pycache(self):
        """.gitignore covers Python cache."""
        gitignore = backend_dir / ".gitignore"
        content = gitignore.read_text()
        assert "__pycache__" in content or "*.pyc" in content

    def test_sensitive_files_not_tracked(self):
        """Sensitive files are not tracked by git."""
        # Check .env
        result = subprocess.run(
            ["git", "ls-files", "backend/.env"],
            capture_output=True, text=True, cwd=backend_dir.parent
        )
        assert result.stdout.strip() == "", ".env is tracked by git!"

        # Check database
        result = subprocess.run(
            ["git", "ls-files", "backend/data/agroverse.db"],
            capture_output=True, text=True, cwd=backend_dir.parent
        )
        assert result.stdout.strip() == "", "Database file is tracked by git!"