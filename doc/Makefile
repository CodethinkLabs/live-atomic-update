all: abi-safe-deps.png abi-unsafe-deps.png

%.png: %.dot
	dot -Tpng $< -o $@
