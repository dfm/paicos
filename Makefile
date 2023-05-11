SHELL=bash

python:
	python3 setup.py build_ext --inplace

clean:
	python3 setup.py clean
	rm -rf paicos/cython/*.{c,so,html}
	rm -rf paicos/__pycache__ paicos/cython/__pycache__

cleanup:
	rm -rf test_data
	rm -f data/very_small_snap_247.hdf5
	rm -f data/reduced_snap2_247.hdf5

checks:
	make cleanup
	pytest tests/comoving
	pytest tests/non-comoving
	flake8 ./
	pylint --errors-only --ignored-modules=astropy.units,astropy.constants  --disable=E0611,E0401,E1101 paicos