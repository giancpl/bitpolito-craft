const {defineConfig}=require('@playwright/test');
module.exports=defineConfig({
 testDir:'.',timeout:90000,globalTimeout:600000,maxFailures:1,
 expect:{timeout:15000},workers:1,retries:0,
 use:{baseURL:process.env.BASE_URL||'http://127.0.0.1:8768',viewport:{width:1440,height:1000},trace:'retain-on-failure',screenshot:'only-on-failure'},
 projects:[
  {name:'chromium',use:{browserName:'chromium',launchOptions:{args:['--enable-unsafe-swiftshader']}}},
  {name:'firefox',use:{browserName:'firefox'}}
 ],reporter:'list'
});
