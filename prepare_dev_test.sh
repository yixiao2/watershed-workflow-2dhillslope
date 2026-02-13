#!/bin/bash

mkdir ../test_Naches_ATS_2D_cleaned
cd ../test_Naches_ATS_2D_cleaned

# prepare folder notebooks
mkdir notebooks
cd notebooks
cp ../../Naches_ATS_2D_cleaned/notebooks/*.ipynb ./
cp ../../Naches_ATS_2D_cleaned/notebooks/config.json ./
cp ../../Naches_ATS_2D_cleaned/notebooks/caseflow-steadystate-template.ats1.5.xml ./
cp ../../Naches_ATS_2D_cleaned/notebooks/caseflow-cyclic_steadystate-template.ats1.5.xml ./
cp ../../Naches_ATS_2D_cleaned/notebooks/caseflow-transient-template.ats1.5.xml ./

#ln -s ../../Naches_ATS_2D_cleaned/notebooks/data ./data
cp ../../Naches_ATS_2D_cleaned/notebooks/data ./data
#ln -s ../../Naches_ATS_2D_cleaned/notebooks/MODIS_raw ./MODIS_raw
cp ../../Naches_ATS_2D_cleaned/notebooks/MODIS_raw ./MODIS_raw
#ln -s ../../Naches_ATS_2D_cleaned/notebooks/Naches_from_sundar ./Naches_from_sundar
#ln -s ../../Naches_ATS_2D_cleaned/notebooks/ELM_from_huilin ./ELM_from_huilin
cp -r ../../Naches_ATS_2D_cleaned/notebooks/ELM_outputs_process ./ELM_outputs_process

cd ..
# prepare folders for case ats-flow run0/1/2
cp -r ../Naches_ATS_2D_cleaned/caseflow-run0 ./
cp -r ../Naches_ATS_2D_cleaned/caseflow-run1 ./
cp -r ../Naches_ATS_2D_cleaned/caseflow-run2 ./

# prepare folders for case ats-pflotran run1/run2
cp -r ../Naches_ATS_2D_cleaned/casecybernetic-run1 ./
cp -r ../Naches_ATS_2D_cleaned/casecybernetic-run2 ./

# copy atspflotranutils
cp -r ../Naches_ATS_2D_cleaned/atspflotranutils ./

# copy processed data from ELM-BGC
#mkdir data-processed
#cd data-processed
#cp -r ../notebooks/ELM_from_huilin/*.h5 ./
