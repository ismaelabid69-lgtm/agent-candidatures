@echo off
cd /d "%~dp0"
echo Installation...
python -m pip install -r requirements.txt
echo.
echo Recherche des entreprises (quelques minutes)...
python collect.py
echo.
echo Apercu des mails (rien n'est envoye) :
python send.py --apercu --nombre 3
pause
