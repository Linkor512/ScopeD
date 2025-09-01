import sys
import os
import types
import collections
import collections.abc
import certifi

print("ЗАПУЩЕН КРЮК ВРЕМЕНИ 'runtime_fix.py'...")

if 'cgi' not in sys.modules:
 sys.modules['cgi'] = types.ModuleType('cgi')
 print("Магия: Модуль 'cgi' воскрешен из пепла.")

if not hasattr(collections, 'Mapping'):
 collections.Mapping = collections.abc.Mapping
 print("Магия: 'Mapping' перенесен сквозь время и пространство.")

if not hasattr(collections, 'MutableMapping'):
 collections.MutableMapping = collections.abc.MutableMapping
 print("Магия: 'MutableMapping' вытащен из могилы вслед за братом.")

if getattr(sys, 'frozen', False):
 # Для скомпилированного .exe путь будет другим
 ca_path = os.path.join(sys._MEIPASS, 'certifi', 'cacert.pem')
else:
 ca_path = certifi.where()

os.environ['SSL_CERT_FILE'] = ca_path
os.environ['REQUESTS_CA_BUNDLE'] = ca_path
print("Магия: Врата в интернет принудительно открыты.")
