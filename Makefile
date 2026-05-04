ARCHIVE_DIR := storage/archives
PROJECT_NAME := ntrx

# Date-based archive naming: codebase-MM-DD-YYYY-NN.tar.gz
DATE_STAMP := $(shell date +%m-%d-%Y)

# Calculate next sequence number for today
NEXT_SEQ := $(shell \
	last=$$(ls -1 $(ARCHIVE_DIR)/codebase-$(DATE_STAMP)-*.tar.gz 2>/dev/null \
		| sed 's/.*-\([0-9]*\)\.tar\.gz/\1/' \
		| sort -n | tail -1); \
	if [ -z "$$last" ]; then echo "01"; \
	else printf "%02d" $$(( $$last + 1 )); fi \
)

ARCHIVE_BASE := codebase-$(DATE_STAMP)-$(NEXT_SEQ)
ARCHIVE_NAME := $(ARCHIVE_BASE).tar.gz
ARCHIVE_PATH := $(ARCHIVE_DIR)/$(ARCHIVE_NAME)

.PHONY: help clean archive archive-clean

help:
	@echo "Available commands:"
	@echo "  make clean         - Clean Python cache"
	@echo "  make archive       - Create codebase archive and extract it"
	@echo "  make archive-clean - Remove all archives and extracted folders"
	@echo "  make help          - Show this help message"

clean:
	./scripts/clean_pycache.sh

archive:
	@mkdir -p $(ARCHIVE_DIR)
	@echo "Creating archive: $(ARCHIVE_PATH)"
	@tar czf $(ARCHIVE_PATH) \
		--transform 's,^\./,$(ARCHIVE_BASE)/,' \
		--exclude='./$(ARCHIVE_DIR)' \
		--exclude='./storage/logs' \
		--exclude='./venv' \
		--exclude='./.venv' \
		--exclude='./env' \
		--exclude='./.git' \
		--exclude='./.agent' \
		--exclude='./.continue' \
		--exclude='./.pytest_cache' \
		--exclude='./.mypy_cache' \
		--exclude='./.idea' \
		--exclude='./.vscode' \
		--exclude='./.history' \
		--exclude='./build' \
		--exclude='./dist' \
		--exclude='./__pycache__' \
		--exclude='./__hack' \
		--exclude='./.env' \
		--exclude='*.py[cod]' \
		--exclude='*$py.class' \
		--exclude='*.so' \
		--exclude='*.egg-info' \
		--exclude='.coverage' \
		--exclude='.coverage.*' \
		--exclude='*.log' \
		--exclude='.DS_Store' \
		--exclude='Thumbs.db' \
		--exclude='*.bak' \
		--exclude='*.swp' \
		--exclude='*~' \
		-C . .
	@SIZE=$$(du -h $(ARCHIVE_PATH) | cut -f1); \
	echo "Done: $(ARCHIVE_PATH) ($$SIZE)"
	@echo "Extracting archive to $(ARCHIVE_DIR)/$(ARCHIVE_BASE)..."
	@tar xzf $(ARCHIVE_PATH) -C $(ARCHIVE_DIR)
	@echo "Extraction complete."

archive-clean:
	@echo "Cleaning archives in $(ARCHIVE_DIR)..."
	@find $(ARCHIVE_DIR) -type f ! -name '.gitkeep' -delete
	@find $(ARCHIVE_DIR) -type d ! -path $(ARCHIVE_DIR) -exec rm -rf {} +
	@echo "Clean complete."
