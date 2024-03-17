#!/bin/bash
for ((i=1; i<12; i=i+1))
do 
    gnome-terminal -- /bin/sh -c "source ../venv/bin/activate; python3.10 swarmtrainer.py $i"

done