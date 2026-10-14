.DEFAULT_GOAL := help

help:  ## Show the targets
	@awk 'BEGIN {FS = ":.*##"} /^##@/ {printf "\n%s\n", substr($$0, 5)} /^[a-z-]+:.*##/ {printf "  %-14s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

##@ Wiki
# openwiki/ is a generated code wiki (OpenWiki): every claim is pinned to the source lines it came from,
# and --update rewrites only pages whose evidence changed. Edit openwiki/INSTRUCTIONS.md, never a page.
# Provider is set explicitly so OpenWiki never falls back to another key it finds in the environment.
# ANTHROPIC_API_KEY comes from the shell, or from a root .env (gitignored) if one exists.
OPENWIKI = OPENWIKI_PROVIDER=anthropic OPENWIKI_MODEL_ID=claude-sonnet-5-5 OPENWIKI_TELEMETRY_DISABLED=1 \
	OPENWIKI_PAGE_CONCURRENCY=2 npx -y openwiki@0.7.2 code
WIKI_ENV = set -a; [ -f .env ] && . ./.env; set +a; \
	test -n "$$ANTHROPIC_API_KEY" || { echo 'ANTHROPIC_API_KEY is not set'; exit 2; };

wiki:  ## Generate openwiki/ from scratch (COSTS MONEY; Sonnet reads the repo)
	@$(WIKI_ENV) $(OPENWIKI) --init --print; rm -f openwiki/.run.json

wiki-update:  ## Refresh openwiki/ pages whose source changed (no model call when nothing did)
	@$(WIKI_ENV) $(OPENWIKI) --update --print; rm -f openwiki/.run.json

# --update reacts to code changes only; an INSTRUCTIONS.md edit alone rewrites nothing. A wrong page
# is fixed by asking OpenWiki's agent, so the page and its claims are edited by the same tool.
wiki-fix:  ## Ask OpenWiki to correct pages: make wiki-fix MSG="what is wrong, and where"
	@test -n "$(MSG)" || { echo 'usage: make wiki-fix MSG="..."'; exit 2; }
	@$(WIKI_ENV) $(OPENWIKI) --print "$(MSG)"; rm -f openwiki/.run.json

.PHONY: help wiki wiki-update wiki-fix
