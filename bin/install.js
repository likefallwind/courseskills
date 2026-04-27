#!/usr/bin/env node

const fs = require('fs');
const path = require('path');
const os = require('os');

const SKILLS = {
  codex2course: path.join(__dirname, '..', 'skills', 'codex2course', 'SKILL.md'),
  pdf2video: path.join(__dirname, '..', 'skills', 'pdf2video', 'SKILL.md'),
};

const skillsDir = path.join(os.homedir(), '.claude', 'skills');

function install(name) {
  const src = SKILLS[name];
  if (!src) {
    console.error(`Unknown skill: ${name}. Available: ${Object.keys(SKILLS).join(', ')}`);
    process.exit(1);
  }
  fs.mkdirSync(skillsDir, { recursive: true });
  const dest = path.join(skillsDir, `${name}.md`);
  fs.copyFileSync(src, dest);
  console.log(`Installed ${name} → ${dest}`);
}

const args = process.argv.slice(2);

if (args.length === 0) {
  // install both by default
  Object.keys(SKILLS).forEach(install);
} else {
  args.forEach(install);
}
