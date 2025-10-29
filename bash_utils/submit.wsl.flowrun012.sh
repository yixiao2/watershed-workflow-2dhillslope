#!bin/bash

cd caseflow-run0
sh job.wsl.v1.5vphong.run0.n8.sh
echo "Submitted caseflow-run0"

cd ../caseflow-run1
sh job.wsl.v1.5vphong.run0.n8.sh
echo "Submitted caseflow-run1"

cd ../caseflow-run2
sh job.wsl.v1.5phong.n8.sh
echo "Submitted caseflow-run2"


