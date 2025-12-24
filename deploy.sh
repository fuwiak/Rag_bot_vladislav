#!/bin/bash

# ============================================
# RAG Bot - Deployment Script for REG.RU VPS
# ============================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
COMPOSE_FILE="docker-compose.prod.yml"
ENV_FILE=".env"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}RAG Bot Deployment Script${NC}"
echo -e "${GREEN}========================================${NC}"

# Check if .env file exists
if [ ! -f "$ENV_FILE" ]; then
    echo -e "${RED}Error: .env file not found!${NC}"
    echo -e "${YELLOW}Please create .env file from .env.example${NC}"
    echo -e "${YELLOW}Command: cp .env.example .env${NC}"
    exit 1
fi

# Check if docker-compose.prod.yml exists
if [ ! -f "$COMPOSE_FILE" ]; then
    echo -e "${RED}Error: $COMPOSE_FILE not found!${NC}"
    exit 1
fi

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}Error: Docker is not running!${NC}"
    exit 1
fi

# Pull latest changes from git (optional)
read -p "Pull latest changes from git? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Pulling latest changes...${NC}"
    git pull || echo -e "${YELLOW}Warning: git pull failed, continuing...${NC}"
fi

# Stop existing containers
echo -e "${YELLOW}Stopping existing containers...${NC}"
docker compose -f "$COMPOSE_FILE" down || true

# Build and start containers
echo -e "${YELLOW}Building and starting containers...${NC}"
docker compose -f "$COMPOSE_FILE" up -d --build

# Wait for services to be healthy
echo -e "${YELLOW}Waiting for services to be healthy...${NC}"
sleep 10

# Check service health
echo -e "${YELLOW}Checking service health...${NC}"

# Check PostgreSQL
if docker compose -f "$COMPOSE_FILE" exec -T postgres pg_isready -U ragbot > /dev/null 2>&1; then
    echo -e "${GREEN}✓ PostgreSQL is healthy${NC}"
else
    echo -e "${RED}✗ PostgreSQL is not healthy${NC}"
fi

# Check Backend
if curl -f http://localhost:8000/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Backend is healthy${NC}"
else
    echo -e "${RED}✗ Backend is not healthy${NC}"
fi

# Check Frontend
if curl -f http://localhost:3000/api/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Frontend is healthy${NC}"
else
    echo -e "${YELLOW}⚠ Frontend health check failed (may need more time)${NC}"
fi

# Show container status
echo -e "${YELLOW}Container status:${NC}"
docker compose -f "$COMPOSE_FILE" ps

# Show logs
echo -e "${YELLOW}Recent logs:${NC}"
docker compose -f "$COMPOSE_FILE" logs --tail=20

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Deployment completed!${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "${YELLOW}Next steps:${NC}"
echo -e "1. Create admin user: docker compose -f $COMPOSE_FILE exec backend python create_admin.py"
echo -e "2. Check logs: docker compose -f $COMPOSE_FILE logs -f"
echo -e "3. Verify services:"
echo -e "   - Backend: http://localhost:8000/health"
echo -e "   - Frontend: http://localhost:3000"




