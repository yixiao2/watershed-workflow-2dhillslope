#!bin/bash

cd caseflow-run0
JOBID_0=$(sbatch --parsable job.compass.atsvphong.1n2c.sh)
echo "Submitted Job 0 with ID: $JOBID_0"

cd ../caseflow-run1
JOBID_1=$(sbatch --parsable --dependency=afterany:$JOBID_0 job.compass.atsvphong.1n2c.sh)
echo "Submitted Job 1 with ID: $JOBID_1"

cd ../casecybernetic-run1-365d
JOBID_2=$(sbatch --parsable --dependency=afterany:$JOBID_1 job.compass.atsvphong.1n2c.sh)
echo "Submitted Job 2 with ID: $JOBID_2"


