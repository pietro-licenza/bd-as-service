# Instruções para Restaurar Versão Anterior

Se precisar reverter as alterações, siga estes passos:

## 1. Restaurar app/api/__init__.py
```bash
copy backup\api_init_backup.py app\api\__init__.py
```

## 2. Restaurar app/validation/__init__.py
```bash
copy backup\validation_init_backup.py app\validation\__init__.py
```

## 3. Remover app/grouping/__init__.py (arquivo novo)
```bash
del app\grouping\__init__.py
```

## Ou via Python:
```python
import shutil
import os

# Restaurar arquivos
shutil.copy('backup/api_init_backup.py', 'app/api/__init__.py')
shutil.copy('backup/validation_init_backup.py', 'app/validation/__init__.py')

# Remover novo arquivo
if os.path.exists('app/grouping/__init__.py'):
    os.remove('app/grouping/__init__.py')
```

Depois reinicie o servidor.
