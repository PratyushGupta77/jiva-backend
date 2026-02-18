@echo off
echo ============================================================
echo CLEANING UP DEBUG FILES FROM JIVA PROJECT
echo ============================================================
echo.

echo Deleting debug and test files...
echo.

del /F debug_models.py 2>nul && echo [OK] Deleted debug_models.py || echo [SKIP] debug_models.py not found
del /F fix_jiva.py 2>nul && echo [OK] Deleted fix_jiva.py || echo [SKIP] fix_jiva.py not found
del /F list_models.py 2>nul && echo [OK] Deleted list_models.py || echo [SKIP] list_models.py not found
del /F quick_key_test.py 2>nul && echo [OK] Deleted quick_key_test.py || echo [SKIP] quick_key_test.py not found
del /F test_new_key.py 2>nul && echo [OK] Deleted test_new_key.py || echo [SKIP] test_new_key.py not found
del /F test_brain.py 2>nul && echo [OK] Deleted test_brain.py || echo [SKIP] test_brain.py not found
del /F test_print.py 2>nul && echo [OK] Deleted test_print.py || echo [SKIP] test_print.py not found
del /F test_conversation_quality.py 2>nul && echo [OK] Deleted test_conversation_quality.py || echo [SKIP] test_conversation_quality.py not found
del /F test_reminder_local.py 2>nul && echo [OK] Deleted test_reminder_local.py || echo [SKIP] test_reminder_local.py not found
del /F available_models.txt 2>nul && echo [OK] Deleted available_models.txt || echo [SKIP] available_models.txt not found

echo.
echo ============================================================
echo CLEANUP COMPLETE!
echo ============================================================
echo.
echo Files KEPT (Essential):
echo   - main.py (Main application)
echo   - requirements.txt (Dependencies)
echo   - .env (Configuration)
echo   - test_jiva.py (Main test file)
echo.
echo Files DELETED (Debug/temporary):
echo   - All debug_*.py files
echo   - All test_*.py files (except test_jiva.py)
echo   - All temporary output files
echo.
pause
