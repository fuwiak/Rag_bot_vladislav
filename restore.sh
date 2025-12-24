#!/bin/bash

# ============================================
# RAG Bot - Database Restore Script
# ============================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
COMPOSE_FILE="docker-compose.prod.yml"
POSTGRES_USER="${POSTGRES_USER:-ragbot}"
POSTGRES_DB="${POSTGRES_DB:-rag_bot}"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}RAG Bot Database Restore${NC}"
echo -e "${GREEN}========================================${NC}"

# Check if backup file is provided
if [ -z "$1" ]; then
    echo -e "${RED}Error: Backup file not specified!${NC}"
    echo -e "${YELLOW}Usage: $0 <backup_file.sql.gz>${NC}"
    echo -e "${YELLOW}Example: $0 backups/ragbot_backup_20240101_120000.sql.gz${NC}"
    exit 1
fi

BACKUP_FILE="$1"

# Check if backup file exists
if [ ! -f "$BACKUP_FILE" ]; then
    echo -e "${RED}Error: Backup file not found: $BACKUP_FILE${NC}"
    exit 1
fi

# Check if PostgreSQL container is running
if ! docker compose -f "$COMPOSE_FILE" ps postgres | grep -q "Up"; then
    echo -e "${RED}Error: PostgreSQL container is not running!${NC}"
    exit 1
fi

# Confirm restore
echo -e "${RED}WARNING: This will replace all data in the database!${NC}"
read -p "Are you sure you want to continue? (yes/no) " -r
if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
    echo -e "${YELLOW}Restore cancelled.${NC}"
    exit 0
fi

# Create backup before restore
echo -e "${YELLOW}Creating backup before restore...${NC}"
./backup.sh || echo -e "${YELLOW}Warning: Pre-restore backup failed${NC}"

# Decompress if needed
if [[ "$BACKUP_FILE" == *.gz ]]; then
    echo -e "${YELLOW}Decompressing backup...${NC}"
    TEMP_FILE="${BACKUP_FILE%.gz}"
    gunzip -c "$BACKUP_FILE" > "$TEMP_FILE"
    BACKUP_FILE="$TEMP_FILE"
    CLEANUP_TEMP=true
else
    CLEANUP_TEMP=false
fi

# Drop and recreate database
echo -e "${YELLOW}Dropping existing database...${NC}"
docker compose -f "$COMPOSE_FILE" exec -T postgres psql -U "$POSTGRES_USER" -c "DROP DATABASE IF EXISTS $POSTGRES_DB;" || true
docker compose -f "$COMPOSE_FILE" exec -T postgres psql -U "$POSTGRES_USER" -c "CREATE DATABASE $POSTGRES_DB;"

# Restore database
echo -e "${YELLOW}Restoring database...${NC}"
docker compose -f "$COMPOSE_FILE" exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" < "$BACKUP_FILE"

# Cleanup temp file
if [ "$CLEANUP_TEMP" = true ]; then
    rm -f "$BACKUP_FILE"
fi

echo -e "${GREEN}✓ Database restored successfully!${NC}"
echo -e "${YELLOW}Note: You may need to restart backend and admin-panel containers${NC}"
echo -e "${YELLOW}Command: docker compose -f $COMPOSE_FILE restart backend admin-panel${NC}"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Restore completed!${NC}"
echo -e "${GREEN}========================================${NC}"



