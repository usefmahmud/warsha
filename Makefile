.PHONY: help up down build ps logs

help:
	@echo "make build   — بناء صور كل التطبيقات"
	@echo "make ps      — حالة الحاويات"
	@echo "make logs    — آخر اللوجز"

build:
	@for app in atlas todo whiteboard; do echo "→ $$app"; (cd apps/$$app && docker compose build); done

ps:
	@docker ps --filter name=atlas --filter name=todo --filter name=whiteboard \
	  --format "{{.Names}}\t{{.Status}}\t{{.Ports}}"

logs:
	@for c in atlas todo whiteboard; do echo "=== $$c ==="; docker logs --tail 15 $$c 2>&1; done
