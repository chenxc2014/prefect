const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve('vendor/prefect/ui-v2');
const ts = require(path.join(root, 'node_modules/typescript'));
const dictionary = {};
const compiled = ts.transpileModule(fs.readFileSync(path.join(root,'localization/dictionary.ts'),'utf8'), {compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
vm.runInNewContext(compiled, {exports:dictionary, Map});
const known = new Set(Object.keys(dictionary.chinese).map(x=>x.toLowerCase()));
const missing = new Map();
let matched = 0;
function scan(directory) {
  for(const entry of fs.readdirSync(directory,{withFileTypes:true})) {
    const filename = path.join(directory,entry.name);
    if(entry.isDirectory()) { scan(filename); continue; }
    if(!filename.endsWith('.tsx') || /\.(test|stories)\.tsx$/.test(filename)) continue;
    const file = ts.createSourceFile(filename,fs.readFileSync(filename,'utf8'),ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX);
    function visit(node) {
      let value;
      if(ts.isJsxText(node)) value=node.text.replace(/\s+/g,' ').trim();
      else if(ts.isStringLiteral(node) && ts.isJsxAttribute(node.parent) && ['placeholder','title','aria-label','alt'].includes(node.parent.name.getText())) value=node.text;
      else if(ts.isStringLiteral(node) && ts.isPropertyAssignment(node.parent) && node.parent.initializer===node && ['label','title','description','header'].includes(node.parent.name.getText())) value=node.text;
      if(value && /[a-zA-Z]/.test(value) && !value.startsWith('http') && value.length>1) {
        if(known.has(value.toLowerCase())) matched++;
        else { const info=missing.get(value)||{count:0,files:[]}; info.count++;info.files.push(path.relative(root,filename));missing.set(value,info); }
      }
      ts.forEachChild(node,visit);
    }
    visit(file);
  }
}
scan(path.join(root,'src/components')); scan(path.join(root,'src/routes'));
const sorted=[...missing.entries()].sort((a,b)=>b[1].count-a[1].count);
fs.writeFileSync('.tmp/ui-missing.json',JSON.stringify(sorted,null,2));
console.log(JSON.stringify({known:Object.keys(dictionary.chinese).length,matched,missing:sorted.length,top:sorted.slice(0,95).map(([text,v])=>({text,count:v.count}))},null,2));
