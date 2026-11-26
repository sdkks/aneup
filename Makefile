SHELL := /bin/bash
.DEFAULT_GOAL := help

# Virtualenv lives on an APFS volume (exFAT/FAT repos cannot hold .venv).
# Override with: make test UVENV=~/.venvs/my-aneup
UVENV ?= $(HOME)/.venvs/aneup
export UV_PROJECT_ENVIRONMENT := $(UVENV)

.PHONY: help install-hooks version bump-version release test build clean

help: ## Show developer commands
	@awk 'BEGIN {FS = ":.*## "} /^[a-z-]+:.*## / {printf "  %-16s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install-hooks: ## Activate tracked .githooks (gitleaks secret/PII scan)
	@git config core.hooksPath .githooks
	@printf 'hooksPath set to .githooks\n'

version: ## Print the package version from pyproject.toml
	@printf 'aneup %s\n' "$$(sed -n 's/^version[ \t]*=[ \t]*\"\([^\"]*\)\"/\1/p' pyproject.toml | head -1)"

bump-version: ## Bump version + CHANGELOG (BUMP=major|minor|patch or VERSION=x.y.z; never commits)
	@bash scripts/bump-version.sh "$(BUMP)" "$(VERSION)"

release: ## One-shot: bump, test, commit, tag vX.Y.Z (BUMP/VERSION as bump-version; never pushes)
	@bash scripts/release.sh "$(BUMP)" "$(VERSION)"

test: ## Run the test suite (model-inference tests need macOS)
	uv run --group test pytest -q

build: ## Build sdist + wheel into dist/ (mirrors to APFS temp: fskit exFAT AppleDouble sidecars break in-place sdist)
	@tmp=$$(mktemp -d /tmp/aneup-build.XXXXXX) && \
	tar --exclude='./.git' --exclude='./testdata' --exclude='./out' --exclude='./dist' --exclude='._*' -cf - . | (cd $$tmp && tar -xf -) && \
	find $$tmp -name '._*' -delete; \
	(cd $$tmp && uv build) && mkdir -p dist && cp $$tmp/dist/* dist/ && rm -rf $$tmp && \
	printf 'built: %s\n' dist/*

clean: ## Remove build artifacts
	rm -rf dist build src/*.egg-info
