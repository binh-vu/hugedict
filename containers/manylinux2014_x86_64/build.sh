pip install maturin

if [ ! -f "/home/builder/venvs/hugedict/bin/activate" ]; then
    python -m venv /home/builder/venvs/hugedict
fi
source /home/builder/venvs/hugedict/bin/activate

rm hugedict/hugedict*.so

maturin develop -r