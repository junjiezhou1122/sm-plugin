import json
from pathlib import Path
import shutil
import subprocess
import tempfile

from sm_plugin import Preset, Skill, bundle, codex_session

with tempfile.TemporaryDirectory(prefix='sm-plugin-verify-') as temporary:
    root = Path(temporary)
    source = root / 'source'
    source.mkdir()
    (source / 'SKILL.md').write_text('---\nname: sm-plugin-probe\ndescription: Temporary discovery verification fixture.\n---\nRead this fixture when asked to verify discovery.\n')
    preset = Preset('runtime-probe', 'Runtime probe', (Skill('sm-plugin-probe', source),))
    directory = bundle(preset, root / 'bundles')
    subprocess.run([shutil.which('claude'), 'plugin', 'validate', '--json', str(directory)], check=True)
    codex_session(shutil.which('codex'), directory, root, [], smoke=True)
    print(json.dumps({'claude': 'plugin structure validated', 'codex': 'nonempty preset discovered', 'model_turns': 0}))
