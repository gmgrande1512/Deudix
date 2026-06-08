import subprocess
import sys
import os

PYTHON = "C:/Users/gmgra/AppData/Local/Python/bin/python.exe"
ROOT   = os.path.dirname(os.path.abspath(__file__))
TESTS  = os.path.join(ROOT, "tests")

print()
print("=" * 50)
print("  DEUDIX - Suite de tests de regresion")
print("=" * 50)
print()
print("Python  :", PYTHON)
print("Tests   :", TESTS)
print()

subprocess.run([PYTHON, "-m", "pip", "install", "pytest", "-q"], check=False)
print()
print("Corriendo tests...")
print("-" * 50)

result = subprocess.run(
    [PYTHON, "-m", "pytest", TESTS, "-v", "--tb=short", "--no-header"],
    cwd=ROOT,
)

print("-" * 50)
if result.returncode == 0:
    print("  OK - TODOS LOS TESTS PASARON")
else:
    print("  ERROR - HAY TESTS FALLANDO")
print("=" * 50)
input("Enter para cerrar...")
