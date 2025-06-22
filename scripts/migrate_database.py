#!/usr/bin/env python3
"""
Comprehensive database migration script for SQLAlchemy models.

This script compares SQLAlchemy models defined in Python code with the actual database schema
and applies necessary migrations to keep them in sync.

Usage:
    python migrate_database.py --models-path bondable.bond.providers.metadata --db-url "sqlite:///bond.db"
    python migrate_database.py --models-path myapp.models --db-url "postgresql://user:pass@localhost/dbname"
"""

import argparse
import importlib
import sys
from typing import List, Dict, Any, Type
from sqlalchemy import create_engine, inspect, text, Column, Table, MetaData
from sqlalchemy.orm import declarative_base
from sqlalchemy.engine import Engine
from sqlalchemy.schema import CreateTable, AddConstraint, DropConstraint
from sqlalchemy.sql.ddl import DropTable
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DatabaseMigrator:
    """Handles database schema migrations by comparing code models with database schema."""
    
    def __init__(self, engine: Engine, base_class: Type):
        self.engine = engine
        self.base_class = base_class
        self.inspector = inspect(engine)
        self.metadata = MetaData()
        
    def get_code_tables(self) -> Dict[str, Table]:
        """Get all tables defined in the code models."""
        tables = {}
        for table_name, table in self.base_class.metadata.tables.items():
            tables[table_name] = table
        return tables
    
    def get_db_tables(self) -> List[str]:
        """Get all tables that exist in the database."""
        return self.inspector.get_table_names()
    
    def get_missing_tables(self) -> List[Table]:
        """Find tables that exist in code but not in database."""
        code_tables = self.get_code_tables()
        db_tables = self.get_db_tables()
        
        missing = []
        for table_name, table in code_tables.items():
            if table_name not in db_tables:
                missing.append(table)
        
        return missing
    
    def get_extra_tables(self) -> List[str]:
        """Find tables that exist in database but not in code."""
        code_tables = self.get_code_tables()
        db_tables = self.get_db_tables()
        
        extra = []
        for table_name in db_tables:
            if table_name not in code_tables:
                extra.append(table_name)
        
        return extra
    
    def get_column_differences(self, table_name: str) -> Dict[str, Any]:
        """Compare columns between code model and database for a specific table."""
        if table_name not in self.get_code_tables():
            return {}
        
        code_table = self.get_code_tables()[table_name]
        db_columns = {col['name']: col for col in self.inspector.get_columns(table_name)}
        
        differences = {
            'missing_columns': [],
            'extra_columns': [],
            'modified_columns': []
        }
        
        # Check for missing columns (in code but not in DB)
        for col_name, col in code_table.columns.items():
            if col_name not in db_columns:
                differences['missing_columns'].append(col)
        
        # Check for extra columns (in DB but not in code)
        for col_name in db_columns:
            if col_name not in code_table.columns:
                differences['extra_columns'].append(col_name)
        
        # Check for modified columns (type changes, nullable changes, etc.)
        for col_name, col in code_table.columns.items():
            if col_name in db_columns:
                db_col = db_columns[col_name]
                code_nullable = col.nullable if col.nullable is not None else True
                db_nullable = db_col['nullable']
                
                if code_nullable != db_nullable:
                    differences['modified_columns'].append({
                        'column': col,
                        'change': f'nullable: {db_nullable} -> {code_nullable}'
                    })
        
        return differences
    
    def create_table(self, table: Table) -> None:
        """Create a new table in the database."""
        logger.info(f"Creating table: {table.name}")
        table.create(self.engine)
    
    def add_column(self, table_name: str, column: Column) -> None:
        """Add a new column to an existing table."""
        logger.info(f"Adding column {column.name} to table {table_name}")
        
        # Build ALTER TABLE ADD COLUMN statement
        column_type = column.type.compile(self.engine.dialect)
        nullable = "NULL" if column.nullable else "NOT NULL"
        default = ""
        
        if column.default is not None:
            if hasattr(column.default, 'arg'):
                # Handle literal defaults
                default_value = column.default.arg
                if isinstance(default_value, str):
                    default = f" DEFAULT '{default_value}'"
                elif isinstance(default_value, bool):
                    # Handle boolean values based on the database dialect
                    if self.engine.dialect.name == 'postgresql':
                        default = f" DEFAULT {str(default_value).lower()}"
                    elif self.engine.dialect.name == 'sqlite':
                        default = f" DEFAULT {1 if default_value else 0}"
                    else:
                        default = f" DEFAULT {default_value}"
                else:
                    default = f" DEFAULT {default_value}"
        
        sql = f"ALTER TABLE {table_name} ADD COLUMN {column.name} {column_type} {nullable}{default}"
        
        with self.engine.connect() as conn:
            conn.execute(text(sql))
            conn.commit()
    
    def drop_column(self, table_name: str, column_name: str) -> None:
        """Drop a column from a table (if supported by the database)."""
        logger.info(f"Dropping column {column_name} from table {table_name}")
        
        if self.engine.dialect.name == 'sqlite':
            logger.warning("SQLite doesn't support dropping columns. Skipping.")
            return
        
        sql = f"ALTER TABLE {table_name} DROP COLUMN {column_name}"
        
        with self.engine.connect() as conn:
            conn.execute(text(sql))
            conn.commit()
    
    def migrate(self, dry_run: bool = False) -> None:
        """Run the migration process."""
        logger.info("Starting database migration...")
        
        # Check for missing tables
        missing_tables = self.get_missing_tables()
        for table in missing_tables:
            if dry_run:
                logger.info(f"[DRY RUN] Would create table: {table.name}")
            else:
                self.create_table(table)
        
        # Check for extra tables
        extra_tables = self.get_extra_tables()
        for table_name in extra_tables:
            logger.warning(f"Table {table_name} exists in database but not in code. Consider removing it manually.")
        
        # Check for column differences in existing tables
        code_tables = self.get_code_tables()
        db_tables = self.get_db_tables()
        
        for table_name in code_tables:
            if table_name in db_tables:
                differences = self.get_column_differences(table_name)
                
                # Add missing columns
                for column in differences['missing_columns']:
                    if dry_run:
                        logger.info(f"[DRY RUN] Would add column {column.name} to table {table_name}")
                    else:
                        self.add_column(table_name, column)
                
                # Report extra columns
                for column_name in differences['extra_columns']:
                    logger.warning(f"Column {column_name} exists in table {table_name} but not in code.")
                    if dry_run:
                        logger.info(f"[DRY RUN] Would drop column {column_name} from table {table_name}")
                    else:
                        if self.engine.dialect.name != 'sqlite':
                            self.drop_column(table_name, column_name)
                
                # Report modified columns
                for mod in differences['modified_columns']:
                    logger.warning(f"Column {mod['column'].name} in table {table_name} has changed: {mod['change']}")
                    logger.warning("Manual intervention may be required for column modifications.")
        
        logger.info("Migration completed.")


def load_models(module_path: str) -> Type:
    """Dynamically load the models module and return the Base class."""
    try:
        # Add the current directory to Python path
        sys.path.insert(0, '.')
        
        # Import the module
        module = importlib.import_module(module_path)
        
        # Look for the Base class
        base_class = None
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if hasattr(attr, 'metadata') and hasattr(attr, '__subclasses__'):
                # This looks like a declarative base
                base_class = attr
                break
        
        if base_class is None:
            raise ValueError(f"Could not find SQLAlchemy Base class in {module_path}")
        
        return base_class
    
    except ImportError as e:
        raise ValueError(f"Could not import module {module_path}: {e}")


def main():
    parser = argparse.ArgumentParser(description='Migrate SQLAlchemy database schema')
    parser.add_argument('--models-path', required=True,
                      help='Python module path containing SQLAlchemy models (e.g., myapp.models)')
    parser.add_argument('--db-url', required=True,
                      help='SQLAlchemy database URL (e.g., sqlite:///db.sqlite or postgresql://user:pass@host/db)')
    parser.add_argument('--dry-run', action='store_true',
                      help='Show what would be done without actually making changes')
    
    args = parser.parse_args()
    
    try:
        # Load the models
        logger.info(f"Loading models from {args.models_path}")
        base_class = load_models(args.models_path)
        
        # Create engine
        logger.info(f"Connecting to database: {args.db_url}")
        engine = create_engine(args.db_url)
        
        # Run migration
        migrator = DatabaseMigrator(engine, base_class)
        migrator.migrate(dry_run=args.dry_run)
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()