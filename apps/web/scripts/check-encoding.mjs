// Tourismo frontend Unicode guard. No packages or network access required.
// Prevent build output containing UTF-8-decoded-as-Windows-1252 characters.
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join, resolve, relative } from 'node:path'
import { TextDecoder } from 'node:util'

const webRoot = resolve(import.meta.dirname, '..')
const utf8 = new TextDecoder('utf-8', { fatal: true })
const cp1252 = new TextDecoder('windows-1252')
const extensions = new Set(['.ts', '.tsx', '.css', '.js', '.mjs', '.html'])
const supported = [0x00B0, 0x00B7, 0x00A9, 0x00AE, 0x00D7, 0x2013, 0x2014,
  0x2018, 0x2019, 0x201C, 0x201D, 0x2022, 0x2026, 0x2190, 0x2192, 0x2713, 0x2714,
  ...Array.from({ length: 128 }, (_, i) => 0x0B80 + i),
  ...Array.from({ length: 128 }, (_, i) => 0x0D80 + i)]
const corruptTokens = new Set()
for (const point of supported) {
  const symbol = String.fromCodePoint(point)
  const bad = cp1252.decode(Buffer.from(symbol, 'utf8'))
  if (bad !== symbol && bad.length >= 2 && !bad.includes('\uFFFD')) {
    corruptTokens.add(bad)
    const double = cp1252.decode(Buffer.from(bad, 'utf8'))
    if (!double.includes('\uFFFD')) corruptTokens.add(double)
  }
}

function *walk(dir) {
  for (const item of readdirSync(dir)) {
    const filename = join(dir, item)
    if (statSync(filename).isDirectory()) yield *walk(filename)
    else if ([...extensions].some(ext => filename.endsWith(ext))) yield filename
  }
}
let checked = 0
let problems = 0
for (const file of [join(webRoot, 'index.html'), ...walk(join(webRoot, 'src'))]) {
  checked++
  let content
  try { content = utf8.decode(readFileSync(file)) }
  catch (error) {
    console.error(`INVALID UTF-8: ${relative(webRoot, file)}: ${error.message}`)
    problems++
    continue
  }
  let found = null
  for (const token of corruptTokens) {
    if (content.includes(token)) { found = token; break }
  }
  if (found || content.includes('\uFFFD')) {
    console.error(`ENCODING ERROR: ${relative(webRoot, file)}: ${JSON.stringify(found || '\uFFFD')}`)
    problems++
  }
}
if (problems) {
  console.error(`${problems} affected source file(s). Run scripts/repair-tourismo-text.py --fix from the project root.`)
  process.exit(1)
}
console.log(`Tourismo UTF-8 guard: ${checked} files verified.`)
