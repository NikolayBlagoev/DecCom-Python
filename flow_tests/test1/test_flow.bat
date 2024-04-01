Set COUNTER=2
:x


echo %Counter%
if "%Counter%"=="38" (
    echo "END!"
) else (
    timeout /t 1
    start cmd.exe /c "python flow_run.py %Counter%"
    set /A COUNTER+=1
    goto x
)


