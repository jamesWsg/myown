#
# $Id: Makefile 382 2010-10-07 06:32:16Z wjg57 $
#
all:

sdist: all
	rm -rf dist
	./localbuild.sh -S

upload: all
	rm -rf dist
	./localbuild.sh -U

dist: all
	rm -rf dist
	./localbuild.sh

clean:
	rm -rf dist

# Update manual pages with the new version number
updman:
	for i in `ls docs/man`; do \
		sed -i -e '/^\.TH/s/[0-9]\.[0-9]\.[0-9]/'`cat VERSION`'/' docs/man/$$i; \
		echo $$i updated.; \
	done
