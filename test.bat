Set COUNTER=1
:x


echo %Counter%
if "%Counter%"=="32" (
    echo "END!"
) else (
    start cmd.exe /c "python testarpegio.py %Counter%"
    set /A COUNTER+=1
    goto x
)


