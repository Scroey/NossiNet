# from NossiPack.RollbackImporter import RollbackImporter
import sys
from NossiSite import app, socketio
# print(os.getcwd()) this is where the database will be, allowing for multiple servers to run on different databases
try:
    port = int(sys.argv[1])
except:
    port = 5000

socketio.run(app, "0.0.0.0", debug=False, port=port)
