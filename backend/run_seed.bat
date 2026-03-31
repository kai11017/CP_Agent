@echo off
python -u scripts\seed_benchmarks.py > seed_output.log 2>&1
echo Done >> seed_output.log
