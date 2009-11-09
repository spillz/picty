import logging
import os

import settings

# create logger
log = logging.getLogger("phraymd core")
log.setLevel(logging.DEBUG)
# create console handler and set level to debug
ch = logging.StreamHandler()
ch.setLevel(logging.ERROR)

fh = logging.FileHandler(os.path.join(settings.settings_dir,'log'))
fh.setLevel(logging.DEBUG)

# create formatter
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s\n%(message)s\n")
# add formatter to ch
ch.setFormatter(formatter)
fh.setFormatter(formatter)
# add ch to logger
log.addHandler(ch)
log.addHandler(fh)
