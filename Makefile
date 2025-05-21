.PHONY: help clean

help:
	@echo "Available commands:"
	@echo "  make clean - Clean Python cache"
	@echo "  make help - Show this help message"

clean:
	./scripts/clean_pycache.sh

.PHONY: help clean
