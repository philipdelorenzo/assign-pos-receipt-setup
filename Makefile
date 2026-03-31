# NOTE: make help uses a special comment format to group targets.
# If you'd like your target to show up use the following:
#
# my_target: ##@category_name sample description for my_target

default: help

.PHONY: install

install: ##@repo Installs needed prerequisites and software to develop in the SRE space
	$(info ********** Installing SRE Repo Prerequisites **********)
	@bash bin/install -a
	@bash bin/install -p
	@.python/bin/pip install -r src/requirements.txt
	@asdf reshim

run: ##@repo Run the server to manage JIRA tickets
	@./.python/bin/python src/jira_watcher.py

format: ##@repo Format code
	$(info ********** Formatting Code **********)
	@.python/bin/python -m black . --exclude=\.python
	@.python/bin/python -m isort --skip .python .

run-tests: ##@repo Run tests
	$(info ********** Running Tests **********)
	@bash test/run_tests.sh -u

jira-watcher-install: ##@repo Install the Service to Mac System
	@echo "[INFO] - Preparing installation directory..."
	@mkdir -p ${HOME}/.pgz/jira_watcher
	
	@echo "[INFO] - Syncing source files..."
	@rsync -avz --delete src/jira_watcher.py ${HOME}/.pgz/jira_watcher/jira_watcher.py
	@rsync -avz --delete src/print_jira.py ${HOME}/.pgz/jira_watcher/print_jira.py
	@rsync -avz --delete src/config.ini ${HOME}/.pgz/jira_watcher/config.ini
	@rsync -avz --delete src/test_printer.py ${HOME}/.pgz/jira_watcher/test_printer.py
	@rsync -avz --delete src/jira_watcher ${HOME}/.pgz/jira_watcher/jira_watcher
	
	@echo "[INFO] - Setting up Python environment..."
	@bash bin/install-launcher -p
	
	@echo "[INFO] - Fixing macOS binary permissions and signing..."
	@pkill -9 -f jira_watcher || true
	@sudo xattr -c "${HOME}/.pgz/jira_watcher/.python/bin/python"
	@sudo codesign --force -s - "${HOME}/.pgz/jira_watcher/.python/bin/python"
	
	@echo "[INFO] - Installing binaries and plists..."
	@sudo chmod +x ${HOME}/.pgz/jira_watcher/jira_watcher
	@cp src/jira_watcher.plist ~/Library/LaunchAgents/com.user.jirawatcher.plist
	
	@echo "[INFO] - Restarting LaunchAgent..."
	-@launchctl bootout gui/$(shell id -u) ~/Library/LaunchAgents/com.user.jirawatcher.plist 2>/dev/null
	@launchctl bootstrap gui/$(shell id -u) ~/Library/LaunchAgents/com.user.jirawatcher.plist
	@launchctl kickstart -k gui/$(shell id -u)/com.user.jirawatcher
	@echo "[SUCCESS] - jira-watcher is running."

############# Development Section #############
help: ##@misc Show this help.
	@echo $(MAKEFILE_LIST)
	@perl -e '$(HELP_FUNC)' $(MAKEFILE_LIST)

# helper function for printing target annotations
# ripped from https://gist.github.com/prwhite/8168133
HELP_FUNC = \
	%help; \
	while(<>) { \
		if(/^([a-z0-9_-]+):.*\#\#(?:@(\w+))?\s(.*)$$/) { \
			push(@{$$help{$$2}}, [$$1, $$3]); \
		} \
	}; \
	print "usage: make [target]\n\n"; \
	for ( sort keys %help ) { \
		print "$$_:\n"; \
		printf("  %-20s %s\n", $$_->[0], $$_->[1]) for @{$$help{$$_}}; \
		print "\n"; \
	}
