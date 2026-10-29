const fs=require('node:fs');const path=require('node:path');
const {test,expect}=require('@playwright/test');
const source=fs.readFileSync(path.resolve(__dirname,'../../..','apps/deckcraft-web/src/recovery.js'),'utf8');
async function fixture(page){
 await page.route('**/recovery-fixture',route=>route.fulfill({contentType:'text/html',body:'<!doctype html><title>Recovery test</title>'}));
 await page.route('**/recovery-module.js',route=>route.fulfill({contentType:'text/javascript',body:source}));
 await page.goto('/recovery-fixture');
 return page.evaluate(async()=>{window.drafts=await import('/recovery-module.js');return window.drafts.recoveryInit();});
}
test('IndexedDB sessions survive reopening and cannot be claimed by two live tabs',async({page,context})=>{
 expect(await fixture(page)).toBe('');
 const snapshot=JSON.stringify({version:1,active:0,documents:[{name:'Workshop',data:'native bytes'}]});
 await page.evaluate(s=>window.drafts.recoverySave(s),snapshot);
 const other=await context.newPage();expect(await fixture(other)).toBe('');
 const otherSnapshot=JSON.stringify({version:1,active:0,documents:[{name:'Talk',data:'other native bytes'}]});
 await other.evaluate(s=>window.drafts.recoverySave(s),otherSnapshot);
 await page.close();
 const reopened=await context.newPage();expect(await fixture(reopened)).toBe(snapshot);
 await reopened.evaluate(()=>window.drafts.recoverySave(JSON.stringify({version:1,active:null,documents:[]})));
 await reopened.close();
 const empty=await context.newPage();expect(await fixture(empty)).toBe('');
 await other.close();await empty.close();
});
test('Serialized writes cannot resurrect an explicitly closed document',async({page})=>{
 await fixture(page);
 await page.evaluate(async()=>{
  const earlier=window.drafts.recoverySave(JSON.stringify({version:1,active:0,documents:[{name:'Old',data:'x'}]}));
  const closed=window.drafts.recoverySave(JSON.stringify({version:1,active:null,documents:[]}));
  await Promise.all([earlier,closed]);
 });
 await page.reload();
 const restored=await page.evaluate(async()=>{window.drafts=await import('/recovery-module.js');return window.drafts.recoveryInit();});
 expect(restored).toBe('');
});
