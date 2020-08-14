
pylint:
	# We have to disable these for now because pylint does not understand databind and nr.stream.
	pylint src/shut -E --disable=unsubscriptable-object,no-value-for-parameter,no-name-in-module,no-member

mypy:
	mypy src/shut
