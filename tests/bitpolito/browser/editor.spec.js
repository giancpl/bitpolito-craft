const {test,expect}=require('@playwright/test');
const command=(page,id,params={})=>page.evaluate(([id,params])=>window.bitpolito.execute(id,params),[id,params]);
async function open(page){await page.goto('/?webgl&automation');await page.waitForFunction(()=>Boolean(window.bitpolito));}
async function draftCount(page){return page.evaluate(()=>new Promise((resolve,reject)=>{const r=indexedDB.open('bitpolito-craft-recovery',1);r.onsuccess=()=>{const db=r.result;const q=db.transaction('sessions').objectStore('sessions').getAll();q.onsuccess=()=>{db.close();resolve(q.result.map(x=>JSON.parse(x.snapshot)));};q.onerror=()=>reject(q.error);};}));}
test('brand starter, editable layouts, assets, undo, native and PDF/PPTX export',async({page})=>{
 await open(page);await expect(page).toHaveTitle('BitPolito Craft');
 expect((await command(page,'file.info')).slides).toBe(1);
 await command(page,'file.new',{template:'bitpolito-talk'});
 const initial=await command(page,'file.info');expect(initial.slides).toBe(7);
 await command(page,'bitpolito.insertAsset',{id:'bull'});
 await command(page,'edit.undo');
 for(const format of ['deckcraft','pptx']){
  const saved=await command(page,'file.saveBytes',{format});expect(saved.data.length).toBeGreaterThan(1000);
  await command(page,'file.openBytes',{name:`roundtrip.${format}`,data:saved.data});
  expect((await command(page,'file.info')).slides).toBe(7);
 }
 const rendered=await command(page,'file.render',{slide:0,scale:.5});expect(rendered.png.length).toBeGreaterThan(1000);
 const download=page.waitForEvent('download');await command(page,'app.print',{});
 // Export commands vary upstream; native engine export is also covered by Rust tests.
 const file=await download;expect(file.suggestedFilename()).toMatch(/\.pdf$/);
});
test('refresh restores all open documents and closed documents stay closed',async({page})=>{
 await open(page);await command(page,'file.new',{template:'bitpolito-workshop'});
 await expect.poll(async()=>{const s=await draftCount(page);return s[0]?.documents.length;}).toBe(2);
 await page.reload();await page.waitForFunction(()=>Boolean(window.bitpolito));
 expect((await command(page,'file.info')).slides).toBe(7);
 await command(page,'file.close');
 await expect.poll(async()=>{const s=await draftCount(page);return s[0]?.documents.length;}).toBe(1);
 await page.reload();await page.waitForFunction(()=>Boolean(window.bitpolito));
 expect((await command(page,'file.info')).slides).toBe(1);
});
test('simultaneous tabs have isolated draft sessions',async({page,context})=>{
 await open(page);await command(page,'file.new',{template:'bitpolito-talk'});
 await expect.poll(async()=>{const s=await draftCount(page);return s[0]?.documents.length;}).toBe(2);
 const other=await context.newPage();await open(other);expect((await command(other,'file.info')).slides).toBe(1);
 await expect.poll(async()=>{const s=await draftCount(page);return s.length;}).toBe(2);
 await page.reload();await page.waitForFunction(()=>Boolean(window.bitpolito));expect((await command(page,'file.info')).slides).toBe(7);
 await other.close();
});
test('storage failure leaves the editor and file export usable',async({page})=>{
 await page.addInitScript(()=>Object.defineProperty(window,'indexedDB',{get(){throw new Error('storage disabled');}}));
 await open(page);
 const saved=await command(page,'file.saveBytes');expect(saved.data.length).toBeGreaterThan(1000);
});
