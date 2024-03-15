#!/bin/bash
for ((i=1; i<64; i=i+1))
do 
    gnome-terminal -- source ~/Documents/Nick/venv/bin/activate; python3.10 testarpegio.py $i

done