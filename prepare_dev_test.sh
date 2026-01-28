#!/bin/bash

mkdir ../test_OakCreek_ATS_2D_cleaned
cd ../test_OakCreek_ATS_2D_cleaned

# prepare folder notebooks
mkdir notebooks
cd notebooks
cp ../../OakCreek_ATS_2D_cleaned/notebooks/*.ipynb ./
cp ../../OakCreek_ATS_2D_cleaned/notebooks/config.json ./
cp ../../OakCreek_ATS_2D_cleaned/notebooks/caseflow-steadystate-template.ats1.5.xml ./
cp ../../OakCreek_ATS_2D_cleaned/notebooks/caseflow-cyclic_steadystate-template.ats1.5.xml ./
cp ../../OakCreek_ATS_2D_cleaned/notebooks/caseflow-transient-template.ats1.5.xml ./

ln -s ../../OakCreek_ATS_2D_cleaned/notebooks/data ./data
ln -s ../../OakCreek_ATS_2D_cleaned/notebooks/MODIS_raw ./MODIS_raw
ln -s ../../OakCreek_ATS_2D_cleaned/notebooks/OakCreek_from_sundar ./OakCreek_from_sundar
ln -s ../../OakCreek_ATS_2D_cleaned/notebooks/ELM_from_huilin ./ELM_from_huilin

cd ..
# prepare folders for case ats-flow run0/1/2
cp -r ../OakCreek_ATS_2D_cleaned/caseflow-run0 ./
cp -r ../OakCreek_ATS_2D_cleaned/caseflow-run1 ./
cp -r ../OakCreek_ATS_2D_cleaned/caseflow-run2 ./

# prepare folders for case ats-pflotran run1/run2
cp -r ../OakCreek_ATS_2D_cleaned/casecybernetic-run1 ./
cp -r ../OakCreek_ATS_2D_cleaned/casecybernetic-run2 ./

# copy atspflotranutils
cp -r ../OakCreek_ATS_2D_cleaned/atspflotranutils ./

# copy processed data from ELM-BGC
mkdir data-processed
cd data-processed
cp -r ../notebooks/ELM_from_huilin/*.h5 ./