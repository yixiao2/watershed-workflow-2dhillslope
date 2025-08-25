#!/bin/bash

mkdir ../test_OakCreek_ATS_2D_cleaned
cd ../test_OakCreek_ATS_2D_cleaned
mkdir notebooks
cd notebooks
cp ../../OakCreek_ATS_2D_cleaned/notebooks/*.ipynb ./
cp ../../OakCreek_ATS_2D_cleaned/notebooks/config.json ./
cp ../../OakCreek_ATS_2D_cleaned/notebooks/caseflow-steadystate-template.ats1.5.xml ./

ln -s ../../OakCreek_ATS_2D_cleaned/notebooks/data ./data
ln -s ../../OakCreek_ATS_2D_cleaned/notebooks/MODIS_raw ./MODIS_raw
ln -s ../../OakCreek_ATS_2D_cleaned/notebooks/OakCreek_from_sundar ./OakCreek_from_sundar