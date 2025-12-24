#!/bin/bash

# ============================================
# RAG Bot - Database Backup Script
# ============================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
COMPOSE_FILE="docker-compose.prod.yml"
BACKUP_DIR="./backups"
POSTGRES_USER="${POSTGRES_USER:-ragbot}"
POSTGRES_DB="${POSTGRES_DB:-rag_bot}"

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

# Generate backup filename with timestamp
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="$BACKUP_DIR/ragbot_backup_$TIMESTAMP.sql"
BACKUP_FILE_COMPRESSED="$BACKUP_FILE.gz"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}RAG Bot Database Backup${NC}"
echo -e "${GREEN}========================================${NC}"

# Check if PostgreSQL container is running
if ! docker compose -f "$COMPOSE_FILE" ps postgres | grep -q "Up"; then
    echo -e "${RED}Error: PostgreSQL container is not running!${NC}"
    exit 1
fi

# Create backup
echo -e "${YELLOW}Creating backup...${NC}"
docker compose -f "$COMPOSE_FILE" exec -T postgres pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" > "$BACKUP_FILE"

# Compress backup
echo -e "${YELLOW}Compressing backup...${NC}"
gzip "$BACKUP_FILE"

# Get backup size
BACKUP_SIZE=$(du -h "$BACKUP_FILE_COMPRESSED" | cut -f1)

echo -e "${GREEN}✓ Backup created successfully!${NC}"
echo -e "${GREEN}  File: $BACKUP_FILE_COMPRESSED${NC}"
echo -e "${GREEN}  Size: $BACKUP_SIZE${NC}"

# Cleanup old backups (keep last 7 days)
echo -e "${YELLOW}Cleaning up old backups (keeping last 7 days)...${NC}"
find "$BACKUP_DIR" -name "ragbot_backup_*.sql.gz" -mtime +7 -delete

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Backup completed!${NC}"
echo -e "${GREEN}========================================${NC}"




