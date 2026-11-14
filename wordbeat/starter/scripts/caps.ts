// Writes out/caps.json, the captions as the picture shows them, for caption_check.py --caps.
import {mkdirSync, writeFileSync} from 'node:fs';
import {captionTimes} from '../src/comp/Caption';

mkdirSync('out', {recursive: true});
const caps = captionTimes();
writeFileSync('out/caps.json', JSON.stringify(caps, null, 1));
console.log(`wrote ${caps.length} captions to out/caps.json`);
