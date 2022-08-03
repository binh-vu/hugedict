export PYTHONPATH=$(pwd)/benchmarks

for i in {1..20}; do
    echo $i
    # python benchmarks/wdentity/read_speed.py --name default --option default
    # python benchmarks/wdentity/read_speed.py --name default --option compress-1
    # python benchmarks/wdentity/read_speed.py --name default --option compress-2
    # python benchmarks/wdentity/read_speed.py --name default --option compress-3
    # python benchmarks/wdentity/read_speed.py --name default --option compress-4
    # python benchmarks/wdentity/read_speed.py --name default --option compress-5
    # python benchmarks/wdentity/read_speed.py --name default --option compress-6
    # python benchmarks/wdentity/read_speed.py --name default --option compress-7
    # python benchmarks/wdentity/read_speed.py --name default --option compress-8
    # python benchmarks/wdentity/read_speed.py --name default --option compress-9
    # python benchmarks/wdentity/read_speed.py --name default --option compress-10
    # python benchmarks/wdentity/read_speed.py --name default --option compress-11
    # python benchmarks/wdentity/read_speed.py --name default --option compress-12
    python benchmarks/wdentity/read_speed.py --name zstd-6 --option default
done