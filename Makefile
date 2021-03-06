
SHELL=/usr/bin/env bash

ENV_PREFIX=export LD_LIBRARY_PATH=/usr/local/cuda/lib64/:$$LD_LIBRARY_PATH

NTHREADS=16
FLAGS=
HIDDEN_SIZE=512

SITE_SERVER=goto
SITE_DIR=~alexss/proverbot9001-site
SITE_PATH=$(SITE_SERVER):$(SITE_DIR)

ifeq ($(NUM_FILES),)
HEAD_CMD=cat
else
HEAD_CMD=head -n $(NUM_FILES)
endif

ifneq ($(MESSAGE),)
FLAGS+=-m "$(MESSAGE)"
endif
REPORT="report"
TESTFILES=$(patsubst %, CompCert/%, $(shell cat data/compcert-test-files.txt))
TESTSCRAPES=$(patsubst %,%.scrape,$(TESTFILES))

.PHONY: scrape report setup static-report dynamic-report search-report

all: scrape report

setup:
	./src/setup.sh && $(MAKE) publish-depv

scrape:
	cp data/scrape.txt data/scrape.bkp 2>/dev/null || true
	cd src && \
	cat ../data/compcert-train-files.txt | $(HEAD_CMD) | \
	xargs python3.7 scrape.py $(FLAGS) -v -c -j $(NTHREADS) --output ../data/scrape.txt \
				        		 --prelude ../CompCert
data/scrape-test.txt: $(TESTSCRAPES)
	cat $(TESTSCRAPES) > $@
CompCert/%.scrape: CompCert/%
	python3.7 src/scrape.py $(FLAGS) -v -c -j 1 --prelude=./CompCert $* > /dev/null

report: $(TESTSCRAPES)
	($(ENV_PREFIX) ; cat data/compcert-test-files.txt | $(HEAD_CMD) | \
	xargs ./src/proverbot9001.py static-report -j $(NTHREADS) --weightsfile=data/polyarg-weights.dat --prelude ./CompCert $(FLAGS))

train:
	./src/proverbot9001.py train polyarg data/scrape.txt data/polyarg-weights.dat --load-tokens=tokens.pickle --save-tokens=tokens.pickle --context-filter="(goal-args+((tactic:induction+tactic:destruct)%numeric-args)+hyp-args)%maxargs:1%default" $(FLAGS) #--hidden-size $(HIDDEN_SIZE)

static-report: $(TESTSCRAPES)
	($(ENV_PREFIX) ; cat data/compcert-test-files.txt | $(HEAD_CMD) | \
	xargs ./src/proverbot9001.py static-report -j $(NTHREADS) --weightsfile=data/polyarg-weights.dat --context-filter="goal-changes" --prelude=./CompCert $(FLAGS))

dynamic-report:
	($(ENV_PREFIX) ; cat data/compcert-test-files.txt | $(HEAD_CMD) | \
	xargs ./src/proverbot9001.py dynamic-report -j $(NTHREADS) --weightsfile=data/polyarg-weights.dat --context-filter="goal-changes" --prelude=./CompCert $(FLAGS))

search-report:
	($(ENV_PREFIX) ; cat data/compcert-test-files.txt | $(HEAD_CMD) | \
	xargs ./src/proverbot9001.py search-report -j $(NTHREADS) --weightsfile=data/polyarg-weights.dat --prelude=./CompCert --search-depth=5 --search-width=5 -P $(FLAGS))

search-test:
	./src/proverbot9001.py search-report -j $(NTHREADS) --weightsfile=data/polyarg-weights.dat --prelude=./CompCert --search-depth=5 --search-width=5 -P --use-hammer -o=test-report --debug ./backend/Locations.v $(FLAGS)

scrape-test:
	cp data/scrape.txt data/scrape.bkp 2>/dev/null || true
	cat data/coqgym-demo-files.txt | $(HEAD_CMD) | \
	xargs python3 src/scrape.py $(FLAGS) -v -c -j $(NTHREADS) --output data/scrape-test.txt \
				        		 --prelude=./coq-projects/zfc

INDEX_FILES=index.js index.css build-index.py

reports/index.css: reports/index.scss
	sass $^ $@

update-index: $(addprefix reports/, $(INDEX_FILES))
	rsync -avz $(addprefix reports/, $(INDEX_FILES)) $(SITE_PATH)/reports/
	ssh goto 'cd $(SITE_DIR)/reports && \
		  python3 build-index.py'

publish:
	$(eval REPORT_NAME := $(shell ./reports/get-report-name.py $(REPORT)/))
	mv $(REPORT) $(REPORT_NAME)
	chmod +rx $(REPORT_NAME)
	tar czf report.tar.gz $(REPORT_NAME)
	rsync -avz report.tar.gz $(SITE_PATH)/reports/
	ssh goto 'cd ~alexss/proverbot9001-site/reports && \
                  tar xzf report.tar.gz && \
                  rm report.tar.gz && \
		  chgrp -Rf proverbot9001 $(REPORT_NAME) $(INDEX_FILES) && \
		  chmod -Rf g+rw $(REPORT_NAME) $(INDEX_FILES) || true'
	mv $(REPORT_NAME) $(REPORT)
	$(MAKE) update-index

publish-weights:
	tar czf data/pytorch-weights.tar.gz data/*.dat
	rsync -avzP data/pytorch-weights.tar.gz goto:proverbot9001-site/downloads/weights-`date -I`.tar.gz
	ssh goto ln -f proverbot9001-site/downloads/weights-`date -I`.tar.gz proverbot9001-site/downloads/weights-latest.tar.gz

download-weights:
	curl -o data/pytorch-weights.tar.gz proverbot9001.ucsd.edu/downloads/weights-latest.tar.gz
	tar xzf data/pytorch-weights.tar.gz

publish-depv:
	opam info -f name,version menhir ocamlfind ppx_deriving ppx_import cmdliner core_kernel sexplib ppx_sexp_conv camlp5 | awk '{print; print ""}' > known-good-dependency-versions.md

clean:
	rm -rf report-*
	rm -f log*.txt

clean-progress:
	fd '.*\.v\.lin' CompCert | xargs rm -f
	fd '.*\.scrape' CompCert | xargs rm -f
