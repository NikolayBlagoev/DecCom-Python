Set COUNTER=1
:x


echo %Counter%
if "%Counter%"=="33" (
    echo "END!"
) else (
    timeout /t 1
    start cmd.exe /c "python flow_run.py %Counter%"
    set /A COUNTER+=1
    goto x
)


