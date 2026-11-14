// Writes out/cues.json (the sound cues) and out/clips.json (recorded sounds) for mix.py.
import {mkdirSync, writeFileSync} from 'node:fs';
import {CLIPS, CUES} from '../src/beats';

mkdirSync('out', {recursive: true});
writeFileSync('out/cues.json', JSON.stringify(CUES.slice().sort((a, b) => a.t - b.t), null, 1));
writeFileSync('out/clips.json', JSON.stringify(CLIPS, null, 1));
console.log(`wrote ${CUES.length} cues to out/cues.json and ${CLIPS.length} clips to out/clips.json`);
