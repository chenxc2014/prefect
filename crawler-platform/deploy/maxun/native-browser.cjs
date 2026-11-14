// 浏览器服务使用与 Maxun 后端相同的 Playwright 协议版本。
const {chromium}=require('playwright-core');
const fs=require('fs');
const http=require('http');
const config=JSON.parse(fs.readFileSync('/etc/crawler-dev/easyspider.json','utf8'));
(async()=>{
  const server=await chromium.launchServer({executablePath:config.browser,headless:true,chromiumSandbox:true,host:'172.17.0.1',port:13001,args:['--disable-dev-shm-usage']});
  http.createServer((req,res)=>{
    if(req.url!='/health'){res.writeHead(404);res.end();return}
    res.setHeader('Content-Type','application/json');
    res.end(JSON.stringify({status:'healthy',wsEndpoint:server.wsEndpoint().replace('172.17.0.1','host.docker.internal')}));
  }).listen(13002,'172.17.0.1');
  for(const signal of ['SIGINT','SIGTERM'])process.on(signal,async()=>{await server.close();process.exit(0)});
  console.log('Maxun 浏览器服务已就绪');
})().catch(error=>{console.error(error.message);process.exit(1)});
