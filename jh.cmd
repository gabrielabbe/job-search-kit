@echo off
rem Run the career-intelligence CLI from the project root:  jh doctor | jh shortlist | jh run ...
set PYTHONPATH=%~dp0src
python -m jobintel %*
